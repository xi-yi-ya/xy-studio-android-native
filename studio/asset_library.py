"""Read-only inventory of project originals, including all saved generations.

Derived preview caches are excluded. Inventory IDs are wire identities, not new
Project IDs; no metadata or project file is rewritten by a query.
"""
import hashlib
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import av
from PIL import Image
from .storage import LIBRARY_TARGET

IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp'}
VIDEO_SUFFIXES = {'.mp4', '.webm', '.mkv'}
SOURCES = {'all', 'imported', 'generated', 'project'}
OWNERS = {'all', 'characters', 'scenes', 'shots', 'unassigned', 'deleted'}


@lru_cache(maxsize=512)
def _metadata(path, size, mtime):
    if Path(path).suffix.lower() in IMAGE_SUFFIXES:
        with Image.open(path) as image:
            return {'width': image.width, 'height': image.height, 'duration': None}
    with av.open(path) as container:
        stream = container.streams.video[0]
        duration = container.duration / av.time_base if container.duration is not None else float(stream.duration * stream.time_base) if stream.duration is not None else None
        return {'width': stream.width, 'height': stream.height, 'duration': duration}


class AssetLibrary:
    def __init__(self, project):
        self.project = project

    def inventory(self, include_trash=False):
        p, records = self.project, {}
        items = {item['id']: (kind, item) for kind in ('characters', 'scenes', 'shots') for item in p.data[kind]}
        def entry(relative):
            if not isinstance(relative, str) or not relative or relative.startswith('previews/'):
                return None
            try:
                file = p.file(relative)
                relative = file.relative_to(p.root).as_posix()
            except (ValueError, OSError):
                return None
            kind = 'image' if file.suffix.lower() in IMAGE_SUFFIXES else 'video' if file.suffix.lower() in VIDEO_SUFFIXES else None
            if not kind or relative.startswith('previews/'):
                return None
            if not include_trash and relative in p.data.get('media_trash', {}): return None
            if relative not in records:
                try: exists = file.is_file(); stat = file.stat() if exists else None
                except OSError: exists = False; stat = None
                records[relative] = {'id': 'media-'+hashlib.sha256(relative.encode()).hexdigest()[:24], 'file': relative, 'kind': kind,
                    'name': '未关联图片' if kind == 'image' else '未关联视频', 'source': 'imported' if relative.startswith('assets/') else 'generated' if relative.startswith('outputs/') else 'project',
                    'owners': [], 'jobs': [], 'versionIds': [], 'current': False, 'deletedOwner': False, 'prompt': '', 'time': datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat() if stat else '',
                    'exists': exists, 'bytes': stat.st_size if stat else None}
            return records[relative]
        for kind, item in items.values():
            for index, v in enumerate(item.get('versions', []), 1):
                r = entry(v.get('file'))
                if r is None: continue
                if not r['owners']:
                    r.update(name=f"{item['name']} · 版本 {index}", prompt=v.get('intent', ''), time=v.get('time') or r['time'])
                if v.get('id'): r['versionIds'].append(v['id'])
                if v.get('job'): r['jobs'].append(v['job']); r['source'] = 'generated'
                owner = {'id': item['id'], 'name': item['name'], 'kind': kind}
                if owner not in r['owners']: r['owners'].append(owner)
            for media in ('image', 'video'):
                r = entry(item.get(media))
                if r is None: continue
                r['current'] = True
                owner = {'id': item['id'], 'name': item['name'], 'kind': kind}
                if owner not in r['owners']: r['owners'].append(owner)
                if r['name'].startswith('未关联'): r['name'] = item['name']+' · 当前版本'
        for job in p.data['jobs']:
            for relative in job.get('outputs', []):
                r = entry(relative)
                if r is None: continue
                r['source'] = 'generated'
                if job['id'] not in r['jobs']: r['jobs'].append(job['id'])
                r['prompt'] = r['prompt'] or job.get('generation', {}).get('prompt', '')
                target = items.get(job.get('target')) if not job.get('library_only') else None
                if target:
                    owner = {'id': target[1]['id'], 'name': target[1]['name'], 'kind': target[0]}
                    if owner not in r['owners']: r['owners'].append(owner)
                    if r['name'].startswith('未关联'): r['name'] = owner['name']+' · 生成结果'
                elif job.get('target') != LIBRARY_TARGET and not job.get('library_only'):
                    r['deletedOwner'] = True
                    if r['name'].startswith('未关联'): r['name'] = '已删除条目的生成结果'
                if job.get('target') == LIBRARY_TARGET or job.get('library_only'):
                    r['name'] = job.get('name') or ('视频' if r['kind']=='video' else '图片')
                    if len(job.get('outputs', [])) > 1:
                        r['name'] += ' · '+str(job['outputs'].index(relative)+1)
        # Imported references may never have been assigned to a card. Retained
        # outputs may outlive their original item or version index.
        for name in ('assets', 'outputs'):
            base = p.root/name
            if not base.is_dir() or base.is_symlink() or os.path.isjunction(base): continue
            for folder, dirs, files in os.walk(base, followlinks=False):
                dirs[:] = [d for d in dirs if not (Path(folder)/d).is_symlink() and not os.path.isjunction(Path(folder)/d)]
                for name in sorted(files):
                    entry((Path(folder)/name).relative_to(p.root).as_posix())
        if include_trash:
            for relative in p.data.get('media_trash', {}): entry(relative)
        counts = {}
        for r in sorted(records.values(), key=lambda r:r['file']):
            if r['file'] in p.data.get('media_names', {}):
                r['name'] = p.data['media_names'][r['file']]
            if r['name'] in ('未关联图片','未关联视频','已删除条目的生成结果'):
                label = r['name']; counts[label] = counts.get(label, 0)+1
                r['name'] = label+' '+str(counts[label])
        return list(records.values())

    def query(self, kind, query='', source='all', owner='all', offset=0, limit=24, sort='newest', trash=False):
        if type(trash) is not bool: raise ValueError('回收站查询条件无效')
        if kind not in ('image', 'video') or source not in SOURCES or owner not in OWNERS or sort not in ('newest', 'oldest', 'name'):
            raise ValueError('素材查询条件无效')
        if not isinstance(query, str) or len(query) > 1000:
            raise ValueError('搜索文字过长或格式无效')
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 100:
            raise ValueError('素材分页范围无效')
        all_records = [r for r in self.inventory(include_trash=trash) if r['kind'] == kind and (not trash or r['file'] in self.project.data.get('media_trash', {}))]
        stats = {s: sum(r['source'] == s for r in all_records) for s in ('imported', 'generated', 'project')}
        stats.update(all=len(all_records), missing=sum(not r['exists'] for r in all_records))
        needle = query.strip().casefold()
        matches = [r for r in all_records if (source == 'all' or r['source'] == source)
            and (owner == 'all' or owner == 'unassigned' and not r['owners'] and not r['deletedOwner'] or owner == 'deleted' and r['deletedOwner'] or any(o['kind'] == owner for o in r['owners']))
            and (not needle or needle in (' '.join([r['name'], r['prompt'], r['file'], *(o['name'] for o in r['owners'])])).casefold())]
        matches.sort(key=lambda r: (r['name'].casefold(), r['file']) if sort == 'name' else (r['time'], r['file']), reverse=sort == 'newest')
        page = []
        for record in matches[offset:offset+limit]:
            r = dict(record, width=None, height=None, duration=None, error='')
            if r['exists']:
                try:
                    file = self.project.file(r['file']); stat = file.stat()
                    r.update(_metadata(str(file), stat.st_size, stat.st_mtime_ns))
                except (OSError, ValueError, av.error.FFmpegError, IndexError) as e:
                    r['error'] = '素材读取失败：'+str(e)
            else: r['error'] = '原文件缺失，请检查项目文件夹'
            page.append(r)
        return {'kind': kind, 'total': len(matches), 'offset': offset, 'limit': limit, 'hasMore': offset+limit < len(matches), 'stats': stats, 'items': page}

    def get(self, relative):
        if relative in self.project.data.get('media_trash', {}):
            raise ValueError('该素材已移入回收站，请先在素材库恢复')
        record = next((r for r in self.inventory() if r['file'] == relative), None)
        if not record or not record['exists']:
            raise ValueError('该素材不存在或不属于当前项目素材库')
        try:
            file=self.project.file(record['file']);stat=file.stat()
            _metadata(str(file),stat.st_size,stat.st_mtime_ns)
        except (OSError,ValueError,av.error.FFmpegError,IndexError) as e:
            raise ValueError('素材无法读取，请检查原文件或重新导入') from e
        return record
