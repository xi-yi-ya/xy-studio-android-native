"""Desktop controller extracted from ui.py; existing domain modules remain authoritative.

Only the Qt owner thread mutates Project. Network workers use snapshots and emit
events. The wire DTO is presentation data, never the on-disk project schema.
"""
import copy
import json
import threading
from dataclasses import asdict
from pathlib import Path
from urllib.parse import quote, urlsplit

import keyring
from PIL import Image
from PySide6.QtCore import QObject, QSettings, Signal, Slot, QLockFile, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog

from . import __version__
from .storage import Project, atomic_json, uid, now, LIBRARY_TARGET
from .workflows import Generation, MODES, RATIOS, STYLES, resolution, frames, new_seed, default_steps
from .comfy import Comfy, execute
from .deepseek import chat, list_models, DEFAULT_MODELS, validate_action
from .action_targets import resolve_target
from .research import safe_link
from .media import video_poster, video_duration
from .skill_library import CATALOG
from .video_preview import PreviewCache
from .presentation import display_chat_text, public_status
from .asset_library import AssetLibrary, IMAGE_SUFFIXES, VIDEO_SUFFIXES, _metadata


class Events(QObject):
    completed = Signal(str, object)
    progress = Signal(str, object)


class StudioService(QObject):
    changed = Signal(str)
    notification = Signal(str)
    exit_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings('XiYi', 'AIStoryStudio')
        self.project = None
        self.project_lock = None
        self.selected = None
        self.context_ids = []
        self.media_context = []
        self.active = None
        self.workers = {}
        self.events = Events(self)
        self.events.completed.connect(self._completed)
        self.events.progress.connect(self._progress)
        self.stopping = threading.Event()
        self.closing = False
        self.status = ''
        self.batch = None
        self.pending = None
        self.rounds = 0
        self.media_base = ''
        self.media_token = uid()
        try:
            self.recent = json.loads(self.settings.value('recent_projects', '[]'))
        except (ValueError, TypeError):
            self.recent = []
        self.last_error = ''
        self.previews = PreviewCache(self)
        self.previews.ready.connect(self.publish)

    def publish(self):
        if not self.closing:
            self.changed.emit(json.dumps(self.snapshot(), ensure_ascii=False))

    def notify(self, text):
        self.notification.emit(str(text))

    def busy(self):
        return bool(self.active or self.workers or self.pending or self.batch)

    def require_project(self):
        if not self.project:
            raise ValueError('请先打开或创建项目')
        return self.project

    def save(self):
        self.require_project().save()
        self.publish()

    def _spawn(self, kind, fn):
        if kind in self.workers:
            raise ValueError('该操作仍在进行，请等待')
        def run():
            try:
                result = {'ok': True, 'value': fn()}
            except Exception as e:
                result = {'ok': False, 'error': str(e)}
            if not self.closing:
                self.events.completed.emit(kind, result)
        thread = threading.Thread(target=run, name='xy-'+kind, daemon=True)
        self.workers[kind] = thread
        thread.start()

    @Slot(str, object)
    def _progress(self, kind, value):
        if self.closing:
            return
        if kind == 'job' and self.active:
            self.active.update(value)
            self.project.save()
        else:
            self.status = str(value)
        self.publish()

    @Slot(str, object)
    def _completed(self, kind, result):
        self.workers.pop(kind, None)
        if self.closing:
            return
        if kind == 'job':
            j = self.active
            if result['ok']:
                snapshot, outputs = result['value']
                j.update(snapshot)
                if j.get('cancelled_by_user') and not outputs:
                    j['status'] = 'cancelled'
                    atomic_json(self.project.file('jobs/'+j['id']+'.json'), j)
                for relative in outputs:
                    self.project.attach_output(j, relative)
                if outputs:
                    self.notify('已保存到'+('视频库' if j['generation']['mode'].startswith('h3') else '图片库')+'，请选择满意的结果添加到资产或分镜。')
            else:
                journal = self.project.file('jobs/'+j['id']+'.json')
                if journal.exists():
                    j.update(json.loads(journal.read_text(encoding='utf-8')))
                self.last_error = result['error']
                self.notify(result['error'])
            self.project.save()
            self.active = None
            self.start_next()
        elif kind == 'chat':
            if result['ok']:
                self._accept_message(result['value'], continuation=True)
            else:
                self.status = 'AI 请求失败'
                self.last_error = result['error']
                self.notify(result['error'])
        elif kind == 'models':
            if result['ok']:
                models = result['value']
                self.settings.setValue('model_list', models)
                if self.settings.value('model', DEFAULT_MODELS[0]) not in models:
                    self.settings.setValue('model', models[0])
                self.status = '账户模型列表已更新'
            else:
                self.last_error = result['error']
                self.notify(result['error'])
        elif kind == 'cancel':
            if result['ok']:
                ident, state = result['value']
                j = next(j for j in self.project.data['jobs'] if j['id'] == ident)
                if state == 'cancelled':
                    j['cancelled_by_user'] = True
                    j['status'] = 'cancelled'
                    if self.active and self.active['id'] == ident:
                        self.job_stop.set()
                    else:
                        atomic_json(self.project.file('jobs/'+ident+'.json'), j)
                elif state == 'cancel_requested':
                    j['status'] = state
                else:
                    self.notify('任务已不在后端队列，请使用恢复查询核对结果')
                self.project.save()
            else:
                self.last_error = result['error']
                self.notify(result['error'])
        self.publish()

    def load(self, path, create=False, title=''):
        if self.busy():
            raise ValueError('任务或审阅进行中，请先完成再切换项目')
        root = Path(path).resolve()
        if root.name == 'project.json':
            root = root.parent
        if self.project and root == self.project.root.resolve():
            return str(root)
        root.mkdir(parents=True, exist_ok=True) if create else None
        lock = QLockFile(str(root/'project.xy-studio.lock'))
        lock.setStaleLockTime(0)
        if not lock.tryLock(0):
            raise ValueError('该项目已由另一个 XY Studio 实例打开')
        try:
            p = Project(root, create)
            if create and title.strip():
                p.data['title'] = title.strip()
                p.save()
            for j in p.data['jobs']:
                journal = p.file('jobs/'+j['id']+'.json')
                if journal.exists():
                    j.update(json.loads(journal.read_text(encoding='utf-8')))
                if j.get('status') == 'completed':
                    for f in j.get('outputs', []):
                        p.attach_output(j, f)
        except Exception:
            lock.unlock()
            raise
        if self.project_lock:
            self.project_lock.unlock()
        self.project_lock = lock
        self.project = p
        self.media_token = uid()
        self.selected = None
        self.context_ids = []
        self.media_context = []
        self.last_error = ''
        self.recent = [{'path': str(root), 'title': p.data['title']}] + [r for r in self.recent if r['path'] != str(root)]
        self.recent = self.recent[:12]
        self.settings.setValue('recent_projects', json.dumps(self.recent, ensure_ascii=False))
        self.publish()
        # Existing pending jobs require explicit resume; never auto-submit at open.
        return str(root)

    def media_url(self, relative):
        if not relative or not self.project:
            return ''
        self.project.file(relative)
        return self.media_base+'/project-media/'+self.media_token+'/'+quote(relative, safe='/')

    @staticmethod
    def wire_generation(value):
        result = copy.deepcopy(value)
        result['seed'] = str(result.get('seed', 42))
        return result

    @staticmethod
    def parse_generation(value):
        value = copy.deepcopy(value)
        seed = value.get('seed', 42)
        if isinstance(seed, bool) or not str(seed).isdigit():
            raise ValueError('种子必须为整数')
        value['seed'] = int(seed)
        return Generation(**value)

    def _version(self, v):
        poster = v['file']
        error = ''
        viewing = v['file']
        if v['kind'] == 'video':
            try:
                poster = video_poster(self.project, v['file'])
                viewing, error = self.previews.request(self.project, v['file'])
            except Exception as e:
                poster = ''; error = str(e)
                viewing = ''
        job = next((j for j in self.project.data['jobs'] if j['id'] == v.get('job')), None)
        return {'id': v['id'], 'media': self.media_url(poster), 'url': self.media_url(viewing), 'file': v['file'], 'kind': v['kind'], 'prompt': v.get('intent', ''), 'time': v['time'], 'label': '生成版本' if job else '导入版本', 'generation': self.wire_generation(dict(job['generation'],edit_follow_source=job.get('edit_follow_source',False))) if job else None, 'materials': v.get('materials', []), 'error': error}

    def snapshot(self):
        models = self.settings.value('model_list', DEFAULT_MODELS, type=list)
        model = self.settings.value('model', DEFAULT_MODELS[0])
        if model not in models:
            models.append(model)
        config = {'comfy': self.settings.value('comfy', 'http://127.0.0.1:8188'), 'model': model, 'models': models, 'online': self.settings.value('online_search', True, type=bool), 'keySet': bool(keyring.get_password('AIStoryStudio', 'deepseek'))}
        attachments = []
        for media in self.media_context:
            attachments.append(dict(media, media=self.media_url(media['file']) if media['kind']=='image' else ''))
        state = {'version': __version__, 'config': config, 'catalog': {'modes': MODES, 'ratios': RATIOS, 'styles': STYLES, 'skills': CATALOG}, 'recent': self.recent, 'selectedId': self.selected, 'contextIds': list(self.context_ids), 'mediaContext': attachments, 'activeJob': self.active['id'] if self.active else None, 'busy': bool('chat' in self.workers or self.batch or self.pending), 'modelsBusy': 'models' in self.workers, 'status': public_status(self.status), 'error': self.last_error, 'review': self.pending, 'project': None}
        if not self.project:
            return state
        p = self.project
        assets, shots = [], []
        for kind in ('characters', 'scenes', 'shots'):
            for item in p.data[kind]:
                versions = [self._version(v) for v in reversed(item['versions'])]
                # Historical projects may have a current image without a version.
                for media in ('image', 'video'):
                    relative = item.get(media, '')
                    if relative and not any(v['file'] == relative for v in versions):
                        versions.append(self._version({'id': 'current-'+item['id']+'-'+media, 'file': relative, 'kind': media, 'time': '', 'intent': '项目当前文件'}))
                current_image = next((v['id'] for v in versions if v['kind'] == 'image' and v['file'] == item['image']), '')
                current_video = next((v['id'] for v in versions if v['kind'] == 'video' and v['file'] == item['video']), '')
                value = {'id': item['id'], 'name': item['name'], 'description': item['description'], 'versions': versions, 'needsReview': item.get('needs_review', False), 'imageFile': item['image'], 'videoFile': item['video']}
                if kind == 'shots':
                    duration, duration_label = 0, '时长待定'
                    if item['video']:
                        try:
                            duration = video_duration(p.file(item['video']))
                            duration_label = f'{duration:.2f} 秒'
                        except Exception as e:
                            duration_label = '时长读取失败：'+str(e)
                    else:
                        previous = [j for j in p.data['jobs'] if j['target'] == item['id'] and j['generation']['mode'].startswith('h3')]
                        if previous:
                            duration = frames(previous[-1]['generation']['seconds'])/24
                            duration_label = f'预计 {duration:.2f} 秒'
                    jobs = [j for j in p.data['jobs'] if j['target'] == item['id']]
                    refs = jobs[-1]['generation'].get('references', []) if jobs else []
                    custom = item.get('original_name', '')
                    value.update(name=custom if custom and custom!='未命名' else item['name'], numberName=item['name'], duration=duration, durationLabel=duration_label, assetIds=item['materials'], imageVersion=current_image or None, videoVersion=current_video or None, references=[{'file':r, 'url':self.media_url(r)} for r in refs])
                    shots.append(value)
                else:
                    value.update(kind=kind, current=current_image, tags=[])
                    assets.append(value)
        messages = []
        for i, m in enumerate(p.data['chat']):
            role = m['role']
            if role not in ('user', 'assistant', 'tool'):
                continue
            text = display_chat_text(m)
            messages.append({'id': 'chat-'+str(i), 'role': role, 'text': text, 'time': '', 'activity': m.get('_activity', [])})
        tasks = []
        versions_by_file = {v['file']: v for item in assets + shots for v in item['versions']}
        for j in p.data['jobs']:
            try:
                target_name = p.get(j['target'])['name']
            except ValueError:
                target_name = j.get('name', '素材库生成') if j.get('target')==LIBRARY_TARGET else '已删除条目'
            progress = j.get('progress')
            results = []
            for index, relative in enumerate(j.get('outputs', [])):
                version = versions_by_file.get(relative)
                if not version:
                    kind = 'video' if Path(relative).suffix.lower() in ('.mp4', '.webm', '.mkv') else 'image'
                    version = self._version({'id':f"result-{j['id']}-{index}", 'job':j['id'], 'file':relative, 'kind':kind, 'time':j.get('created',''), 'intent':j['generation']['prompt']})
                results.append(version)
            tasks.append({'id': j['id'], 'targetId': j['target'], 'targetName': target_name, 'kind': 'video' if j['generation']['mode'].startswith('h3') else 'image', 'status': j['status'], 'progress': progress['value']/progress['max']*100 if progress and progress.get('max') else None, 'node': j.get('node'), 'steps': progress, 'prompt': j['generation']['prompt'], 'time': j.get('created', ''), 'error': j.get('error'), 'generation': self.wire_generation(dict(j['generation'],edit_follow_source=j.get('edit_follow_source',False))), 'outputs': [self.media_url(r) for r in j.get('outputs', [])], 'results':results, 'raw': j})
        state['project'] = {'id': p.data['id'], 'name': p.data['title'], 'root': str(p.root), 'story': p.data['story'], 'updated': p.data.get('updated', ''), 'assets': assets, 'shots': shots, 'tasks': tasks, 'chat': messages, 'paused': p.data.get('queue_paused', False)}
        return state

    def _generation(self, target, value):
        self.require_project()
        item = self.project.get(target) if target and target != LIBRARY_TARGET else None
        g = self.parse_generation(value)
        if g.mode in ('qwen', 'krea', 'h3_t2v'):
            g.references = []
        g.validate()
        for r in g.references:
            if r in self.project.data.get('media_trash', {}):
                raise ValueError('参考图片已移入回收站，请先恢复：'+Path(r).name)
            if not self.project.file(r).is_file():
                raise ValueError('参考图不存在：'+r)
            if Path(r).suffix.lower() not in IMAGE_SUFFIXES:
                raise ValueError('此工作流只支持图片参考，视频不能作为参考图')
        return item, g

    def defaults(self, target=None, mode=None, kind='image'):
        p = self.require_project()
        item = p.get(target) if target and target != LIBRARY_TARGET else None
        history = [j for j in reversed(p.data['jobs']) if (j['generation']['mode'].startswith('h3') == (kind=='video'))]
        if mode is None:
            mode = ('qwen_edit' if item['image'] else 'qwen') if item else history[0]['generation']['mode'] if history else 'h3_i2v' if kind=='video' else 'qwen'
        previous = next((j for j in reversed(p.data['jobs']) if j['generation']['mode']==mode and (not item or j.get('origin_target',j['target'])==target)), None)
        if previous:
            g = dict(previous['generation'], edit_follow_source=previous.get('edit_follow_source',False), seed=new_seed())
            return self.wire_generation(g)
        refs = [item['image']] if item and item['image'] and mode in ('h3_i2v', 'upscale', 'quad', 'qwen_edit') else []
        return self.wire_generation(asdict(Generation(mode=mode, prompt=item['description'] if item else '', references=refs, seed=new_seed(), steps=default_steps(mode), megapixels=.2 if mode.startswith('h3') else 6.6 if mode=='qwen' else 1, seconds=2 if mode.startswith('h3') else 5, qwen_int8=mode=='qwen_edit')))

    def submit(self, target, generation, name=''):
        item, g = self._generation(target, generation)
        # Resolve the legacy 0 sentinel before journaling. Do not re-randomize
        # reviewed seeds here: retries and recovery must reproduce this request.
        g.steps = g.steps or default_steps(g.mode)
        parameters = asdict(g)
        parameters.pop('edit_follow_source')
        kind = '视频' if g.mode.startswith('h3') else '图片'
        number = 1+sum(j.get('target')==LIBRARY_TARGET and j['generation']['mode'].startswith('h3')==g.mode.startswith('h3') for j in self.project.data['jobs'])
        j = {'id': uid(), 'target': LIBRARY_TARGET, 'name': name.strip()[:100] or f'{kind} {number}', 'generation': parameters, 'materials': [], 'status': 'new', 'created': now()}
        if item: j['origin_target'] = item['id']
        if g.mode=='qwen_edit': j['edit_follow_source'] = g.edit_follow_source
        self.project.data['jobs'].append(j)
        self.save()
        self.start_next()
        return j['id']

    def start_next(self):
        if self.closing or self.active or not self.project or self.project.data.get('queue_paused'):
            return
        job = next((j for j in self.project.data['jobs'] if j['status'] == 'new'), None)
        if job:
            self.start_job(job)

    def start_job(self, job):
        if self.active:
            raise ValueError('已有任务在查询或生成中')
        self.active = job
        self.job_stop = threading.Event()
        # Resuming an unfinished old job also follows explicit adoption. Its
        # existing ID/target are retained as provenance, not a write destination.
        if job.get('target') != LIBRARY_TARGET:
            job['library_only'] = True
            self.project.save()
        p = Project(self.project.root)
        snapshot = copy.deepcopy(job)
        client = Comfy(self.settings.value('comfy', 'http://127.0.0.1:8188'))
        def run():
            outputs = execute(client, p, snapshot, lambda _: self.events.progress.emit('job', copy.deepcopy(snapshot)) if not self.closing else None, lambda: self.stopping.is_set() or self.job_stop.is_set())
            return snapshot, outputs
        self._spawn('job', run)
        self.publish()

    def _start_chat(self):
        key = keyring.get_password('AIStoryStudio', 'deepseek')
        if not key:
            raise ValueError('请先在设置中填写 DeepSeek API Key')
        p = self.require_project()
        self.rounds += 1
        context = copy.deepcopy({k:p.data[k] for k in ('id', 'title', 'story', 'characters', 'scenes', 'shots')})
        context['selected_ids'] = list(dict.fromkeys(([self.selected] if self.selected else [])+self.context_ids))
        context['media_attachments'] = copy.deepcopy(self.media_context)
        # Queries use this round's detached project snapshot, never a mutable
        # UI-owned Project from a network worker. Files are read-only inputs.
        query_project = object.__new__(Project)
        query_project.root, query_project.data = p.root, copy.deepcopy(p.data)
        library = AssetLibrary(query_project)
        history = copy.deepcopy(p.data['chat'])
        model = self.settings.value('model', DEFAULT_MODELS[0])
        online = self.settings.value('online_search', True, type=bool)
        self.status = 'AI 正在处理请求'
        self._spawn('chat', lambda: chat(key, model, history, context, online=online, notify=lambda value:self.events.progress.emit('chat', value) if not self.closing else None, asset_query=library.query))
        self.publish()

    def _accept_message(self, msg, continuation=False):
        self.project.data['chat'].append(msg)
        self.batch = {'calls': msg.get('tool_calls', []), 'index': 0, 'created': {}, 'all_applied': bool(msg.get('tool_calls')), 'generated': False, 'continuation': continuation}
        self._next_review()

    def _next_review(self):
        b = self.batch
        while b['index'] < len(b['calls']):
            call = b['calls'][b['index']]
            try:
                name = call['function']['name']
                args = json.loads(call['function']['arguments'])
                validate_action(name, args)
                if name != 'generate':
                    args = resolve_target(name, args, b['calls'], b['created'], self.project.data['characters']+self.project.data['scenes']+self.project.data['shots'])
                if name not in ('add_item', 'update_item', 'set_story', 'generate'):
                    raise ValueError('此工具不是可执行项目操作')
                pending = {'id': uid(), 'name': name, 'args': args, 'title': {'add_item':'添加条目', 'update_item':'修改条目', 'set_story':'保存故事', 'generate':'生成视频' if args.get('mode','').startswith('h3') else '生成图片'}[name]}
                if name == 'generate':
                    if args.get('target','').startswith('@') and any(c['function']['name']=='add_item' for c in b['calls']):
                        # Legacy dependent suggestions still respect a rejected
                        # creation, although approved output now goes to the library.
                        resolve_target(name, args, b['calls'], b['created'])
                    g = self.parse_generation(self.defaults(mode=args['mode']))
                    g.prompt, g.references = args['prompt'], args['references']
                    self._generation(None, asdict(g))
                    pending.update(targetId=LIBRARY_TARGET, targetName='视频库' if g.mode.startswith('h3') else '图片库', generation=self.wire_generation(asdict(g)))
                elif name == 'add_item' and args['kind'] != 'shots':
                    if not args.get('file'): raise ValueError('添加角色或场景需要先选择已有图片；生成新图片请使用生图操作')
                    record = AssetLibrary(self.project).get(args.get('file',''))
                    if record['kind'] != 'image': raise ValueError('角色和场景请从图片库选择图片')
                    pending['media'] = {'file':record['file'], 'name':record['name'], 'url':self.media_url(record['file'])}
                self.pending = pending
                self.status = '等待审阅：'+pending['title']
                self.save()
                return
            except Exception as e:
                self.project.data['chat'].append({'role':'tool', 'tool_call_id':call['id'], 'content':'操作未执行：'+str(e)})
                self.notify(str(e))
                b['all_applied'] = False
                b['index'] += 1
        follow = b['continuation'] and b['all_applied'] and not b['generated']
        self.batch = None
        self.pending = None
        self.save()
        if follow and self.rounds < 4:
            self._start_chat()
        else:
            self.status = '达到连续操作上限，请继续对话' if follow else '本轮结束 · 请查看操作结果'

    def review(self, ident, accepted, generation=None):
        if not self.pending or self.pending['id'] != ident:
            raise ValueError('该审阅已失效或已处理，未重复执行')
        b, pending = self.batch, self.pending
        call = b['calls'][b['index']]
        args, name = pending['args'], pending['name']
        result = '用户取消本次操作，未执行'
        if accepted:
            if name == 'generate':
                job = self.submit(None, generation or pending['generation'])
                result = '已加入队列：'+pending['targetName']+'，任务 '+job+'；尚未完成生成'
                b['generated'] = True
            elif name == 'add_item':
                record = AssetLibrary(self.project).get(args['file']) if args['kind'] != 'shots' else None
                item = self.project.add(args['kind'], args['name'] or (record['name'] if record else ''), args['description'] if args['kind']=='shots' else '')
                if record: self.project.use_media(item['id'], record)
                result = json.dumps(item, ensure_ascii=False)
                b['created'][call['id']] = item['id']
                matches = [c for c in b['calls'] if c['function']['name']=='add_item' and json.loads(c['function']['arguments']).get('name') == args['name']]
                if args['name'] and len(matches) == 1:
                    b['created'][args['name']] = item['id']
            elif name == 'update_item':
                item = self.project.get(args['id'])
                if 'materials' in args:
                    self.link(item['id'], args['materials'])
                item['description'] = args['description']
                self.project.mark_dependents(item['id'])
                result = '条目已更新'
            elif name == 'set_story':
                self.project.data['story'] = args['text']
                result = '故事已保存'
        else:
            b['all_applied'] = False
        display = '已创建：'+args['name'] if name=='add_item' and accepted else result
        if name=='generate' and accepted:
            display = '已加入生成队列，完成后保存到'+pending['targetName']+'，再由你选择使用。'
        self.project.data['chat'].append({'role':'tool', 'tool_call_id':call['id'], 'content':result, '_display': display})
        b['index'] += 1
        self.pending = None
        self._next_review()
        self.publish()

    def link(self, ident, ids):
        item = self.project.get(ident)
        if not any(s['id'] == ident for s in self.project.data['shots']):
            raise ValueError('只有分镜可以关联素材')
        valid = {a['id'] for a in self.project.data['characters']+self.project.data['scenes']}
        if any(i not in valid for i in ids):
            raise ValueError('分镜只能关联已有角色和场景')
        item['materials'] = list(dict.fromkeys(ids))

    def dispatch(self, command, a):
        if self.closing:
            raise ValueError('应用正在退出')
        if command == 'bootstrap':
            return self.snapshot()
        if command == 'error.clear':
            self.last_error = ''; self.publish(); return True
        if command in ('project.open', 'project.new'):
            path = a.get('path')
            if not path:
                if command == 'project.new':
                    path = QFileDialog.getExistingDirectory(self.parent(), '选择新项目文件夹')
                else:
                    path = QFileDialog.getOpenFileName(self.parent(), '打开项目', '', '项目 (project.json)')[0]
            return self.load(path, command == 'project.new', a.get('title', '')) if path else None
        if command == 'settings.save':
            url = a.get('comfy', self.settings.value('comfy', 'http://127.0.0.1:8188')).strip()
            if urlsplit(url).scheme not in ('http', 'https') or not urlsplit(url).hostname:
                raise ValueError('ComfyUI 地址必须为有效 HTTP 地址')
            if a.get('key', '').strip():
                keyring.set_password('AIStoryStudio', 'deepseek', a['key'].strip())
            self.settings.setValue('comfy', url.rstrip('/'))
            if 'model' in a:
                self.settings.setValue('model', a['model'])
            if 'online' in a:
                self.settings.setValue('online_search', bool(a['online']))
            self.settings.sync(); self.publish(); return True
        if command == 'models.refresh':
            key = keyring.get_password('AIStoryStudio', 'deepseek')
            if not key:
                raise ValueError('请先保存 DeepSeek API Key')
            self._spawn('models', lambda:list_models(key)); self.publish(); return True
        if command == 'link.open':
            if not safe_link(a['url']):
                raise ValueError('链接协议不安全')
            QDesktopServices.openUrl(QUrl(a['url'])); return True
        if command == 'app.close':
            self.exit_requested.emit(); return True
        p = self.require_project()
        if command == 'project.save':
            self.save(); return True
        if command == 'project.story':
            p.data['story'] = a['text']; self.save(); return True
        if command == 'project.folder':
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.root))); return True
        if command == 'library.query':
            allowed = {'kind', 'query', 'source', 'owner', 'offset', 'limit', 'sort', 'trash'}
            if set(a)-allowed: raise ValueError('未知素材查询条件')
            result = AssetLibrary(p).query(**a)
            for r in result['items']:
                r['media'] = ''
                if r['exists'] and not r['error']:
                    try: r['media'] = self.media_url(video_poster(p, r['file']) if r['kind']=='video' else r['file'])
                    except Exception as e: r['error'] = '预览读取失败：'+str(e)
            return result
        if command == 'library.preview':
            r = AssetLibrary(p).get(a['file'])
            return self._version({'id':r['id'], 'file':r['file'], 'kind':r['kind'], 'time':r['time'], 'intent':r['prompt'], 'job':r['jobs'][0] if r['jobs'] else None})
        if command == 'library.delete':
            if self.pending or self.batch or 'chat' in self.workers: raise ValueError('请先完成或取消当前 AI 对话与审阅，再删除素材')
            record = next((r for r in AssetLibrary(p).inventory() if r['file']==a['file']), None)
            if record is None: raise ValueError('素材已删除或不属于当前项目')
            current = [item['name'] for kind in ('characters','scenes','shots') for item in p.data[kind] if record['file'] in (item.get('image'),item.get('video'))]
            if current: raise ValueError('素材正在被使用，请先替换或移除这些条目的图片/视频：'+'、'.join(current))
            unfinished = {'new','submitting','queued','running','downloading','cancel_requested','unknown','detached'}
            if any(j.get('status') in unfinished and record['file'] in j.get('generation',{}).get('references',[]) for j in p.data['jobs']):
                raise ValueError('素材正被未完成的生成任务引用，请先完成或取消任务')
            p.data.setdefault('media_trash', {})[record['file']] = {'name':record['name'],'kind':record['kind'],'time':now()}
            self.media_context = [m for m in self.media_context if m['file']!=record['file']]
            self.save(); return True
        if command == 'library.restore':
            if a['file'] not in p.data.get('media_trash', {}): raise ValueError('回收站中没有这份素材')
            if not p.file(a['file']).is_file(): raise ValueError('原文件缺失，无法恢复，请检查项目文件夹')
            del p.data['media_trash'][a['file']]
            self.save(); return True
        if command == 'references.describe':
            files = a['files']
            if not isinstance(files,list) or len(files)>16 or any(not isinstance(f,str) for f in files): raise ValueError('参考素材列表无效')
            records = {r['file']:r for r in AssetLibrary(p).inventory()}
            result = []
            for file in files:
                original = p.file(file)
                r = records.get(file)
                trashed = file in p.data.get('media_trash', {})
                exists = original.is_file() and original.suffix.lower() in IMAGE_SUFFIXES and not trashed
                result.append({'file':file,'name':r['name'] if r else original.name,'media':self.media_url(file) if exists else '', 'exists':exists,'trashed':trashed})
            return result
        if command == 'library.import':
            kind = a['kind']
            if kind not in ('image','video','auto'): raise ValueError('素材类型无效')
            paths = a.get('paths')
            if paths is None:
                paths = QFileDialog.getOpenFileNames(self.parent(),'导入图片' if kind=='image' else '导入视频','','图片 (*.png *.jpg *.jpeg *.webp)' if kind=='image' else '视频 (*.mp4 *.webm *.mkv)')[0]
            if not isinstance(paths,list) or any(not isinstance(f,str) for f in paths): raise ValueError('请选择有效的素材文件')
            for source in paths:
                file=Path(source)
                suffixes = IMAGE_SUFFIXES if kind=='image' else VIDEO_SUFFIXES if kind=='video' else IMAGE_SUFFIXES|VIDEO_SUFFIXES
                if not file.is_file() or file.suffix.lower() not in suffixes: raise ValueError('素材不存在或格式不受支持，请导入图片或视频原文件')
                stat=file.stat()
                _metadata(str(file.resolve()),stat.st_size,stat.st_mtime_ns)
            imported=[p.import_file(source) for source in paths]
            self.save(); return imported
        if command == 'asset.from_media':
            if a['kind'] not in ('characters','scenes'): raise ValueError('请选择角色或场景')
            record = AssetLibrary(p).get(a['file'])
            if record['kind'] != 'image': raise ValueError('角色和场景请选用图片')
            item = p.add(a['kind'], a.get('name','').strip() or record['name'])
            p.use_media(item['id'], record)
            self.save(); return item['id']
        if command == 'asset.use_media':
            item = p.get(a['id'])
            record = AssetLibrary(p).get(a['file'])
            if record['kind']=='video' and item not in p.data['shots']: raise ValueError('视频请添加到分镜')
            version = p.use_media(item['id'], record)
            self.save(); return version
        if command == 'asset.rename':
            item = p.get(a['id'])
            name = a.get('name','').strip()
            if not name:
                try: name = AssetLibrary(p).get(item['image'])['name']
                except ValueError: name = item['name']
            item['name'] = name[:100]
            p.mark_dependents(item['id']); self.save(); return True
        if command == 'context.add_media':
            r = AssetLibrary(p).get(a['file'])
            if not any(c['file']==r['file'] for c in self.media_context):
                self.media_context.append({'file':r['file'], 'name':r['name'], 'kind':r['kind']})
            self.publish(); return True
        if command == 'context.remove':
            if bool(a.get('id')) == bool(a.get('file')): raise ValueError('请选择一个要取消的引用')
            if a.get('id'):
                self.context_ids = [i for i in self.context_ids if i != a['id']]
                if self.selected == a['id']: self.selected = None
            else:
                self.media_context = [c for c in self.media_context if c['file'] != a['file']]
            self.publish(); return True
        if command == 'context.clear':
            self.selected = None; self.context_ids = []; self.media_context = []
            self.publish(); return True
        if command == 'selection':
            ident = a.get('id')
            if ident: p.get(ident)
            # Toggle against authoritative state so rapid clicks cannot race
            # a Vue render. Navigation/pinning remain explicit selections.
            self.selected = None if a.get('toggle') and self.selected == ident else ident
            if a.get('pin') and ident and ident not in self.context_ids:
                self.context_ids.append(ident)
            if a.get('clear'): self.context_ids = []; self.media_context = []
            self.publish(); return True
        if command == 'asset.add':
            name = a.get('name', '') or (f"分镜 {len(p.data['shots'])+1}" if a['kind']=='shots' else '')
            item = p.add(a['kind'], name, a.get('description', '')); self.publish(); return item['id']
        if command == 'asset.update':
            item = p.get(a['id'])
            kind = next(k for k in ('characters','scenes','shots') if item in p.data[k])
            item['original_name' if kind=='shots' else 'name'] = a['name'] or ('' if kind=='shots' else '未命名')
            item['description'] = a['description']; p.mark_dependents(item['id']); self.save(); return True
        if command == 'asset.link':
            self.link(a['id'], a['ids']); self.save(); return True
        if command == 'asset.delete':
            if any(j['target']==a['id'] and j['status'] in ('new','submitting','queued','running','downloading','cancel_requested') for j in p.data['jobs']):
                raise ValueError('此条目仍有任务，请先完成或取消')
            p.delete(a['id'], detach=True)
            if self.selected == a['id']: self.selected = None
            self.context_ids = [i for i in self.context_ids if i != a['id']]
            self.publish(); return True
        if command == 'asset.reviewed':
            p.get(a['id'])['needs_review'] = False; self.save(); return True
        if command in ('asset.import', 'references.import'):
            paths = a.get('paths')
            if paths is None:
                paths = QFileDialog.getOpenFileNames(self.parent(), '导入参考图片', '', '图片 (*.png *.jpg *.jpeg *.webp)')[0]
            imported = []
            for path in paths:
                if Path(path).suffix.lower() not in ('.png','.jpg','.jpeg','.webp'): raise ValueError('只接受图片素材')
                with Image.open(path) as im: im.verify()
                imported.append(p.import_file(path))
            if command == 'asset.import' and imported:
                item = p.get(a['id']); item['image'] = imported[-1]
                for r in imported: item['versions'].append({'id':uid(),'time':now(),'kind':'image','file':r,'intent':'导入图片'})
                p.mark_dependents(item['id'])
            self.save(); return imported
        if command == 'version.use':
            item = p.get(a['id']); v = next((v for v in item['versions'] if v['id']==a['version']), None)
            if not v and a['version'] in ('current-'+item['id']+'-image', 'current-'+item['id']+'-video'):
                return True
            if not v: raise ValueError('该版本不存在')
            if v['file'] in p.data.get('media_trash', {}): raise ValueError('该版本已移入回收站，请先在素材库恢复')
            if not p.file(v['file']).is_file(): raise ValueError('版本文件不存在')
            item[v['kind']] = v['file']; p.mark_dependents(item['id']); self.save(); return True
        if command == 'media.open':
            file = p.file(a['file'])
            if not file.is_file(): raise ValueError('文件不存在')
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(file))); return True
        if command == 'generation.defaults':
            return self.defaults(a.get('target'), a.get('mode'), a.get('kind','image'))
        if command == 'generation.seed':
            return str(new_seed())
        if command == 'generation.preview':
            g = self.parse_generation(a['generation'])
            if type(g.steps) is not int or not 0 <= g.steps <= 100:
                raise ValueError('采样步数必须为 0–100 的整数')
            w, h = resolution(g.ratio, g.megapixels, 32 if g.mode.startswith('h3') or g.mode=='qwen_edit' else 8)
            if g.mode=='qwen':
                # The approved selector uses 8 px. Qwen's 16 px VAE then rounds
                # the empty latent spatial size again in fix_empty_latent_channels.
                w,h=max(16,round(w/16)*16),max(16,round(h/16)*16)
            if g.mode=='upscale' and g.references:
                with Image.open(p.file(g.references[0])) as im: w, h = int(im.width*g.scale), int(im.height*g.scale)
            if g.mode=='qwen_edit' and g.edit_follow_source and g.references:
                with Image.open(p.file(g.references[0])) as im: w, h = max(32,round(im.width/32)*32), max(32,round(im.height/32)*32)
            return {'width':w,'height':h,'frames':frames(g.seconds),'seconds':frames(g.seconds)/24,'steps':g.steps or default_steps(g.mode)}
        if command == 'generation.submit':
            return self.submit(a.get('target'), a['generation'], a.get('name',''))
        if command == 'queue.toggle':
            p.data['queue_paused'] = not p.data.get('queue_paused', False); self.save(); self.start_next(); return True
        if command == 'task.cancel':
            j = next(j for j in p.data['jobs'] if j['id']==a['id'])
            if j['status']=='new': j['status']='cancelled'; self.save(); return True
            if not j.get('prompt_id') or j['status'] not in ('queued','running','cancel_requested'):
                raise ValueError('此任务当前不能取消，请先恢复查询核对后端')
            client = Comfy(self.settings.value('comfy','http://127.0.0.1:8188'))
            self._spawn('cancel', lambda:(j['id'],client.cancel(j['prompt_id']))); return True
        if command == 'task.resume':
            j = next(j for j in p.data['jobs'] if j['id']==a['id'])
            if not j.get('prompt_id'):
                raise ValueError('没有后端任务 ID，无法恢复；请人工核对，未自动重交')
            self.start_job(j); return True
        if command == 'chat.send':
            if 'chat' in self.workers or self.batch: raise ValueError('请等待本轮完成或处理待审阅操作')
            if not keyring.get_password('AIStoryStudio','deepseek'): raise ValueError('请先保存 DeepSeek API Key')
            text = a['text'].strip()
            if not text: return False
            self._finish_unanswered()
            p.data['chat'].append({'role':'user','content':text}); p.save(); self.rounds=0; self._start_chat(); return True
        if command == 'review.respond':
            return self.review(a['id'], a['accepted'], a.get('generation'))
        if command == 'agent.import':
            if self.busy(): raise ValueError('请先完成当前任务或审阅')
            path = a.get('path') or QFileDialog.getOpenFileName(self.parent(),'导入 AI 操作建议','','建议 (*.json)')[0]
            if not path: return None
            bundle=json.loads(Path(path).read_text(encoding='utf-8'))
            if bundle.get('project_id')!=p.data['id']: raise ValueError('建议属于其他项目')
            msg=copy.deepcopy(bundle['message'])
            if msg.get('role')!='assistant': raise ValueError('建议消息格式错误')
            for c in msg.get('tool_calls',[]): validate_action(c['function']['name'],json.loads(c['function']['arguments']))
            msg['content']='[导入建议：'+str(bundle.get('provider','未知'))+']\n'+(msg.get('content') or '')
            self._accept_message(msg); return True
        raise ValueError('未知桌面接口：'+command)

    def _finish_unanswered(self):
        messages = self.project.data['chat']
        answered = {m.get('tool_call_id') for m in messages if m['role']=='tool'}
        for m in list(messages):
            for c in m.get('tool_calls', []):
                if c['id'] not in answered:
                    messages.append({'role':'tool','tool_call_id':c['id'],'content':'前次审阅未完成，未执行此操作'})
                    answered.add(c['id'])

    def shutdown(self):
        if self.project:
            self._finish_unanswered()
            self.project.save()
        self.closing = True
        self.stopping.set()
        self.previews.close()
        if self.project_lock:
            self.project_lock.unlock()
        # Network threads are daemon threads in this process, never a sidecar.
        # execute() persists prompt_id before polling; recovery reads its journal.
