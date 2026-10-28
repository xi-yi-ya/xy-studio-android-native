import json
import os
import shutil
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path
from .workflows import is_video

def uid(): return uuid.uuid4().hex
def now(): return datetime.now(timezone.utc).isoformat()
LIBRARY_TARGET = '__library__'
def atomic_json(path, data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+uid()+'.tmp')
    try:
        with tmp.open('w',encoding='utf-8') as f:
            json.dump(data,f,ensure_ascii=False,indent=2); f.flush(); os.fsync(f.fileno())
        for attempt in range(20):
            try:
                os.replace(tmp,path);break
            except PermissionError:
                # Windows readers briefly deny replacement of the open journal.
                if attempt==19:raise
                time.sleep(.025)
    finally:
        if tmp.exists():tmp.unlink()

class Project:
    def __init__(self, root, create=False):
        self.root=Path(root).resolve(); self.path=self.root/'project.json'
        if create:
            if self.path.exists(): raise ValueError('该文件夹已有项目，请打开它')
            self.data={'schema':1,'id':uid(),'title':self.root.name,'story':'','characters':[], 'scenes':[], 'shots':[], 'jobs':[], 'chat':[]}
            self.save()
        else:
            self.data=json.loads(self.path.read_text(encoding='utf-8'))
            if self.data.get('schema')!=1: raise ValueError('不支持的项目版本')
        for folder in ('assets','outputs','jobs'): (self.root/folder).mkdir(exist_ok=True)
        self.number_shots()

    def number_shots(self):
        for i,shot in enumerate(self.data['shots'],1):
            name=f'分镜 {i}'
            if shot['name']!=name:
                shot.setdefault('original_name',shot['name'])
                shot['name']=name

    def save(self):
        self.number_shots()
        self.data['updated']=now()
        atomic_json(self.path,self.data)

    def file(self,relative):
        p=(self.root/relative).resolve()
        if not p.is_relative_to(self.root): raise ValueError('项目文件路径越界')
        return p

    def import_file(self,path):
        path=Path(path).resolve()
        if not path.is_file(): raise ValueError('素材不存在')
        dest=self.root/'assets'/f'{uid()}{path.suffix.lower()}'
        shutil.copy2(path,dest)
        relative = dest.relative_to(self.root).as_posix()
        self.data.setdefault('media_names', {})[relative] = path.stem
        return relative

    def add(self,kind,name,description='',image=''):
        if kind not in ('characters','scenes','shots'): raise ValueError('未知素材类型')
        item={'id':uid(),'name':name.strip() or '未命名','description':description,'image':image,'video':'','materials':[], 'versions':[]}
        self.data[kind].append(item); self.save(); return item

    def get(self,ident):
        for kind in ('characters','scenes','shots'):
            for item in self.data[kind]:
                if item['id']==ident: return item
        raise ValueError('素材或分镜不存在')

    def last_prompt(self,ident,mode):
        item=self.get(ident)
        if mode in item.get('last_prompts',{}):return item['last_prompts'][mode]
        for job in reversed(self.data['jobs']):
            if job['target']==ident and job['generation']['mode']==mode:return job['generation']['prompt']
        return ''

    def delete(self,ident,detach=False):
        affected=[s['name'] for s in self.data['shots'] if ident in s['materials']]
        if affected and not detach: raise ValueError('仍被分镜引用，请先解除引用：'+', '.join(affected))
        if detach:
            for shot in self.data['shots']:
                if ident in shot['materials']:
                    shot['materials'].remove(ident);shot['needs_review']=True
        for kind in ('characters','scenes','shots'):
            self.data[kind]=[x for x in self.data[kind] if x['id']!=ident]
        # Files and generation history retained for recoverability.
        self.save()

    def mark_dependents(self,ident):
        for shot in self.data['shots']:
            if ident in shot['materials']:
                shot['needs_review']=True
        self.save()

    def attach_output(self,job,relative):
        if relative in self.data.get('media_trash', {}): return
        # New requests belong to the library. Legacy jobs retain their original
        # associations during replay so opening old projects remains lossless.
        if job.get('target') == LIBRARY_TARGET or job.get('library_only'): return
        try: item=self.get(job['target'])
        except ValueError: return
        if any(v.get('job')==job['id'] and v['file']==relative for v in item['versions']): return
        media='video' if is_video(job['generation']['mode']) else 'image'
        version={'id':uid(),'time':now(),'job':job['id'],'kind':media,'file':relative,
                 'intent':job['generation']['prompt'],'materials':job.get('materials',[])}
        item['versions'].append(version); item[media]=relative
        self.mark_dependents(item['id'])
        self.save()

    def use_media(self, ident, record):
        """Adopt a library original without copying or changing its identity."""
        item = self.get(ident)
        media, relative = record['kind'], record['file']
        if not self.file(relative).is_file(): raise ValueError('素材原文件不存在')
        version = next((v for v in item['versions'] if v['file'] == relative and v['kind'] == media), None)
        if version is None:
            job = next((j for j in self.data['jobs'] if j['id'] in record['jobs']), None)
            version = {'id':uid(), 'time':now(), 'kind':media, 'file':relative,
                       'intent':record.get('prompt') or '选用素材库图片', 'materials':[], 'adopted':True}
            if job: version['job'] = job['id']
            item['versions'].append(version)
        item[media] = relative
        self.mark_dependents(ident)
        return version['id']
