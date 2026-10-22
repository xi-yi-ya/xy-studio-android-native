"""Qt-thread capability boundary. Never expose StudioService.dispatch wholesale."""
import copy
import hashlib
import json
import secrets
import time
from concurrent.futures import Future
from pathlib import Path
from urllib.parse import quote, unquote

from PySide6.QtCore import QObject, Signal, Slot, Qt
from ..media_server import MEDIA_SUFFIXES
from ..storage import uid

# Explicit field allowlist prevents paths, desktop dialogs, keys and future commands
# from silently becoming remote capabilities.
FIELDS = {
    'bootstrap': set(), 'error.clear': set(), 'project.save': set(),
    'project.open': {'path'}, 'project.new': {'title'}, 'project.story': {'text'},
    'settings.save': {'model', 'online'}, 'models.refresh': set(),
    'library.query': {'kind','query','source','owner','offset','limit','sort','trash'},
    'library.preview': {'file'}, 'library.delete': {'file'}, 'library.restore': {'file'},
    'references.describe': {'files'}, 'asset.from_media': {'kind','file','name'},
    'asset.use_media': {'id','file'}, 'asset.rename': {'id','name'},
    'context.add_media': {'file'}, 'context.remove': {'id','file'}, 'context.clear': set(),
    'selection': {'id','toggle','pin','clear'}, 'asset.add': {'kind','name','description'},
    'asset.update': {'id','name','description'}, 'asset.link': {'id','ids'},
    'asset.delete': {'id'}, 'asset.reviewed': {'id'}, 'version.use': {'id','version'},
    'generation.defaults': {'target','mode','kind'}, 'generation.seed': set(),
    'generation.preview': {'generation'}, 'generation.submit': {'target','generation','name'},
    'queue.toggle': set(), 'task.cancel': {'id'}, 'task.resume': {'id'},
    'chat.send': {'text'}, 'review.respond': {'id','accepted','generation'},
}
CONFLICT_CHECK = {'project.story', 'asset.update', 'asset.rename', 'asset.link',
                  'asset.use_media', 'version.use', 'asset.delete'}


class Host(QObject):
    requested = Signal(object)
    changed = Signal()
    notice = Signal(str)

    def __init__(self, service, project_home):
        super().__init__()
        self.service = service
        self.project_home = Path(project_home).resolve()
        self.allowed = {}
        self.revision = 0
        self.document = ''
        self.media = {}
        self.requested.connect(self._execute, Qt.QueuedConnection)
        service.changed.connect(self._changed)
        service.notification.connect(self.notice)

    def authorize(self, path):
        root = Path(path).resolve()
        if root.name == 'project.json': root = root.parent
        data = json.loads((root/'project.json').read_text(encoding='utf-8'))
        if data.get('schema') != 1: raise ValueError('不支持的项目格式')
        ident = next((i for i, p in self.allowed.items() if p == root), None) or uid()
        self.allowed[ident] = root
        self._changed()
        return ident

    def current_allowed(self):
        return self.service.project and self.service.project.root in self.allowed.values()

    def _changed(self, *_):
        # Only editable document fields count. Progress and chat do not invalidate
        # a text editor while a render is running.
        p = self.service.project
        doc = json.dumps({k:p.data.get(k) for k in ('id','story','characters','scenes','shots')}, sort_keys=True) if p else ''
        digest = hashlib.sha256(doc.encode()).hexdigest()
        if digest != self.document:
            self.document = digest
            self.revision += 1
        self.changed.emit()

    def call(self, action, payload=None):
        future = Future()
        self.requested.emit((future, action, payload))
        return future

    @Slot(object)
    def _execute(self, request):
        future, action, payload = request
        if not future.set_running_or_notify_cancel(): return
        try:
            if action == 'state': result = self.state()
            elif action == 'media': result = self.resolve_media(payload)
            elif action == 'upload': result = self.upload(payload)
            else: result = self.command(payload)
            future.set_result(result)
        except Exception as exc:
            future.set_exception(exc)

    def sanitize(self, value):
        if isinstance(value, dict):
            result = {k:self.sanitize(v) for k,v in value.items()}
            # Native Android can decode the original MP4; Qt keeps its VP9 cache.
            if value.get('kind') == 'video' and value.get('file') and 'url' in value and self.current_allowed():
                result['originalUrl'] = self.sanitize(self.service.media_url(value['file']))
            return result
        if isinstance(value, list): return [self.sanitize(v) for v in value]
        prefix = self.service.media_base+'/project-media/'+self.service.media_token+'/'
        if isinstance(value, str) and value.startswith(prefix) and self.current_allowed():
            relative = unquote(value[len(prefix):])
            p = self.service.project
            target = p.file(relative)
            if target.suffix.lower() not in MEDIA_SUFFIXES: return ''
            # Opaque capability tied to this project, expires when switching project.
            ident = hashlib.sha256((self.service.media_token+relative).encode()).hexdigest()
            self.media[ident] = (p.root, relative, self.service.media_token)
            return '/media/'+ident
        return value

    def state(self):
        s = copy.deepcopy(self.service.snapshot())
        s['recent'] = []
        for ident, root in self.allowed.items():
            try:
                title = json.loads((root/'project.json').read_text(encoding='utf-8'))['title']
                s['recent'].append({'path': ident, 'title': title})
            except (OSError, ValueError, KeyError): pass
        if self.current_allowed():
            s['project']['root'] = 'PC 授权项目'
        else:
            for key in ('project','review','selectedId','activeJob'): s[key] = None
            s.update(contextIds=[], mediaContext=[], status='', error='')
        s['lanRevision'] = self.revision
        return self.sanitize(s)

    def command(self, envelope):
        command, a = envelope.get('command'), envelope.get('payload', {})
        if command not in FIELDS or not isinstance(a, dict) or set(a)-FIELDS[command]:
            raise PermissionError('此操作不允许通过 LAN 执行')
        if command == 'bootstrap': return self.state()
        if command == 'project.open':
            root = self.allowed.get(a.get('path'))
            if not root: raise PermissionError('请先在 PC 授权项目，再从列表选择')
            self.service.load(root)
            return True
        if command == 'project.new':
            title = str(a.get('title','')).strip()[:100]
            if not title: raise ValueError('请输入项目名称')
            root = self.project_home/uid()
            self.service.load(root, create=True, title=title)
            self.authorize(root)
            self.service.publish()
            return True
        if command in ('settings.save','models.refresh','error.clear'):
            return self.service.dispatch(command, a)
        if not self.current_allowed(): raise PermissionError('当前项目未授权')
        if envelope.get('projectId') != self.service.project.data['id']:
            raise ValueError('项目已切换，请刷新后重试；操作未执行')
        if command in CONFLICT_CHECK and envelope.get('revision') != self.revision:
            raise ValueError('项目已被其他操作更新，请刷新核对后重试；操作未执行')
        if command == 'review.respond' and type(a.get('accepted')) is not bool:
            raise ValueError('审阅决定必须为明确的同意或拒绝')
        result = self.service.dispatch(command, a)
        return self.sanitize(result)

    def resolve_media(self, ident):
        if not self.current_allowed() or ident not in self.media:
            raise PermissionError('素材未授权')
        root, relative, epoch = self.media[ident]
        if root != self.service.project.root or epoch != self.service.media_token:
            raise PermissionError('素材授权已失效')
        target = self.service.project.file(relative)
        if target.suffix.lower() not in MEDIA_SUFFIXES or not target.is_file():
            raise PermissionError('素材不可访问')
        return target

    def upload(self, value):
        path, project_id, command, args = value
        if not self.current_allowed() or self.service.project.data['id'] != project_id:
            raise PermissionError('项目已切换或未授权，未导入素材')
        if command not in ('library.import','references.import','asset.import'):
            raise PermissionError('未知导入操作')
        args = {k:v for k,v in args.items() if k in ('id','kind')}
        args['paths'] = [str(path)]
        return self.service.dispatch(command, args)
