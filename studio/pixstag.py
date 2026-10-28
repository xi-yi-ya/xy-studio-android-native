"""Pixstag V2 adapter. Keys stay on PC; POST is never automatically retried.

Contract checked against https://pixstag.com/docs/api on 2026-10-26.
Only this adapter knows the cloud request/response format. Project journals keep
the remote ID and safe metadata, never credentials, inline media or signed URLs.
"""
import base64
import hashlib
import io
import ipaddress
import re
import socket
import time
from pathlib import Path
from urllib.parse import quote, urlsplit, urljoin

import requests
from PIL import Image, ImageOps

from .storage import atomic_json, now
from .workflows import Generation

BASE = 'https://pixstag.com/api/v2'
STATUSES = {'queued', 'running', 'succeeded', 'failed', 'cancelled'}


def normalize_key(value):
    key = value.strip().strip('\"\'')
    if key.lower().startswith('bearer '): key = key[7:].strip()
    if not key or not key.isascii() or any(c.isspace() or not c.isprintable() for c in key):
        raise ValueError('Pixstag API Key 必须为有效的单行密钥')
    return key


def reference_bytes(project, relative, kind):
    """Validate relative capabilities; conversion only touches an in-memory copy."""
    source = project.file(relative)
    if relative in project.data.get('media_trash', {}) or not source.is_file():
        raise ValueError('参考素材不存在或已移入回收站：'+source.name)
    if kind == 'video':
        if source.suffix.lower() != '.mp4': raise ValueError('Pixstag 参考视频须为 MP4')
        if not 0 < source.stat().st_size <= 5*1024*1024:
            raise ValueError('Pixstag 单个参考视频不能超过 5 MB，请先裁剪或压缩副本')
        return source.read_bytes(), 'video/mp4', False
    if source.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
        raise ValueError('请选择 PNG、JPG 或 WebP 项目图片')
    with Image.open(source) as im:
        im.verify()
    if source.suffix.lower() != '.webp' and source.stat().st_size <= 3*1024*1024:
        return source.read_bytes(), 'image/png' if source.suffix.lower() == '.png' else 'image/jpeg', False
    with Image.open(source) as original:
        im = ImageOps.exif_transpose(original).convert('RGB')
        # Bound in-memory upload size without altering the project original.
        im.thumbnail((4096, 4096))
        for _ in range(5):
            for quality in (90, 75, 60):
                out = io.BytesIO(); im.save(out, format='JPEG', quality=quality)
                if out.tell() <= 3*1024*1024: return out.getvalue(), 'image/jpeg', True
            im.thumbnail((max(1, im.width//2), max(1, im.height//2)))
    raise ValueError('参考图片无法压缩到 API 的 3 MB 限制内')


def prepare(project, g):
    """Shared by preview and execution; preview does not make any API request."""
    g.validate()
    content = [{'type':'text', 'text':g.prompt.strip()}]
    audit = []
    for kind, refs in (('image', g.references), ('video', g.video_references)):
        for i, relative in enumerate(refs):
            data, mime, converted = reference_bytes(project, relative, kind)
            role = ('first_frame' if i == 0 else 'last_frame') if g.mode in ('pixstag_i2v', 'pixstag_fl2v') else 'reference_'+kind
            content.append({'type':kind+'_url', kind+'_url':{'url':'data:'+mime+';base64,'+base64.b64encode(data).decode('ascii')}, 'role':role})
            audit.append({'file':relative, 'kind':kind, 'role':role, 'bytes':len(data), 'converted':converted, 'sha256':hashlib.sha256(data).hexdigest()})
    payload = {'model':g.api_model, 'duration':int(g.seconds), 'ratio':g.ratio, 'resolution':g.api_resolution,
               'aigc_watermark':g.api_watermark, 'use_context_ir':g.api_context_ir,
               'return_last_frame':g.api_last_frame, 'content':content}
    return payload, audit


class Pixstag:
    def __init__(self, key):
        self.key = normalize_key(key)
        self.session = requests.Session()
        self.download_session = requests.Session()
        self.download_session.trust_env = False

    def clean_error(self, value):
        text = str(value).replace(self.key, '[密钥已隐藏]')
        text = re.sub(r'data:[^\s\"\']+', '[参考素材已隐藏]', text)
        text = re.sub(r'https?://[^\s\"\']+', '[链接已隐藏]', text)
        return text[:1500]

    def request(self, method, path, payload=None):
        try:
            r = self.session.request(method, BASE+path, json=payload,
                                     headers={'Authorization':'Bearer '+self.key}, timeout=(10,90), allow_redirects=False)
            if not 200 <= r.status_code < 300:
                raise RuntimeError(f'Pixstag HTTP {r.status_code}：'+self.clean_error(r.text))
            value = r.json()
        except requests.RequestException as exc:
            raise RuntimeError('Pixstag 网络请求失败（'+type(exc).__name__+'）；未自动重复提交') from None
        except ValueError:
            raise RuntimeError('Pixstag 返回无效 JSON；请核对任务，勿直接重复提交') from None
        if not isinstance(value, dict): raise RuntimeError('Pixstag 返回格式异常')
        if isinstance(value.get('data'), dict): value = value['data']
        return value

    def account(self):
        value = self.request('GET', '/user/me')
        if 'credit' not in value or 'status' not in value: raise RuntimeError('Pixstag 未返回账户信息，请检查 API Key')
        # Do not return the token or arbitrary server fields to the application.
        return {k:value[k] for k in ('user_id','credit','credit_frozen','credit_valid_time','status') if k in value}

    def submit(self, payload):
        value = self.request('POST', '/video_generation', payload)
        ident = value.get('task_id')
        if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', ident):
            raise RuntimeError('Pixstag 提交响应缺少有效任务 ID；可能已扣费，请在平台核对，勿重复提交')
        return ident

    def query(self, ident):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', ident): raise ValueError('Pixstag 任务 ID 无效')
        value = self.request('GET', '/query/video_generation/'+quote(ident, safe=''))
        task = value.get('task')
        if not isinstance(task, dict) or task.get('status') not in STATUSES:
            raise RuntimeError('Pixstag 查询响应缺少有效 task.status')
        return task

    @staticmethod
    def check_download_url(url):
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443):
            raise ValueError('Pixstag 结果必须来自公开 HTTPS 下载地址')
        addresses = socket.getaddrinfo(parsed.hostname,443,type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError('拒绝下载非公网地址的 API 结果')

    def download(self, url, target):
        """No Bearer header on CDN requests; validate every redirect and publish atomically."""
        target = Path(target); target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name+'.part')
        try:
            for _ in range(6):
                self.check_download_url(url)
                with self.download_session.get(url, stream=True, timeout=(15,120), allow_redirects=False) as r:
                    if r.status_code in (301,302,303,307,308):
                        url = urljoin(url, r.headers.get('Location','')); continue
                    r.raise_for_status()
                    if any(t in r.headers.get('Content-Type','').lower() for t in ('text/', 'json')):
                        raise RuntimeError('视频下载返回了网页或 JSON')
                    size = 0; head = b''
                    with temporary.open('xb') as stream:
                        for chunk in r.iter_content(1024*1024):
                            if not chunk: continue
                            if not head: head = chunk[:64]
                            size += len(chunk)
                            if size > 2*1024**3: raise RuntimeError('视频超过客户端 2 GB 下载上限')
                            stream.write(chunk)
                    if size < 12 or b'ftyp' not in head[:32]: raise RuntimeError('API 结果不是有效 MP4 文件')
                    if r.headers.get('Content-Length') and size != int(r.headers['Content-Length']):
                        raise RuntimeError('视频下载不完整，请恢复查询重试下载')
                    if target.exists(): raise RuntimeError('输出文件已存在，请勿覆盖')
                    temporary.replace(target)
                    return target
            raise RuntimeError('视频下载重定向次数过多')
        finally:
            temporary.unlink(missing_ok=True)

    def close(self):
        self.session.close(); self.download_session.close()


def execute(client, project, job, notify=lambda s:None, stopping=lambda:False, poll_seconds=3, max_wait=7200):
    def update(status, **fields):
        job.update(status=status, updated=now(), **fields)
        atomic_json(project.file('jobs/'+job['id']+'.json'),job)
        notify(status)
    try:
        job.pop('error', None)
        job.pop('progress', None)
        if not job.get('prompt_id'):
            g = Generation(**job['generation'])
            payload, audit = prepare(project, g)
            update('submitting', provider='pixstag', uploaded_references=audit)
            ident = client.submit(payload)  # Exactly one attempt, including on timeout.
            update('queued', prompt_id=ident, remote_status='queued')
        deadline = time.monotonic()+max_wait
        failures = 0
        while True:
            if stopping() or time.monotonic() >= deadline:
                update('detached', progress=None); return []
            try:
                task = client.query(job['prompt_id']); failures = 0
            except Exception:
                failures += 1
                if failures >= 3: raise
                # Only GET queries may retry. Sleep remains interruptible.
                until = time.monotonic()+poll_seconds*failures
                while time.monotonic() < until and not stopping(): time.sleep(min(.2, max(0,until-time.monotonic())))
                continue
            remote = task['status']
            metadata = {k:task[k] for k in ('model','resolution','duration','ratio','usage') if k in task}
            if remote == 'failed':
                error = task.get('error') or {}
                update('failed',remote_status=remote,remote_result=metadata)
                raise RuntimeError('Pixstag 生成失败：'+client.clean_error(error))
            if remote == 'cancelled':
                update('cancelled', remote_status=remote, remote_result=metadata); return []
            if remote == 'succeeded':
                update('downloading', remote_status=remote, remote_result=metadata, progress=None)
                url = (task.get('content') or {}).get('url')
                if not isinstance(url,str) or not url: raise RuntimeError('Pixstag 已成功但缺少视频地址，请恢复查询')
                target = project.file('outputs/'+job['id']+'/pixstag-video.mp4')
                if not target.exists(): client.download(url,target)
                relative = target.relative_to(project.root).as_posix()
                update('completed', outputs=[relative]); return [relative]
            update(remote, remote_status=remote, remote_result=metadata, progress=None)
            until = time.monotonic()+poll_seconds
            while time.monotonic() < until and not stopping(): time.sleep(min(.2,max(0,until-time.monotonic())))
    except Exception as exc:
        status = 'unknown' if job.get('status') == 'submitting' else 'failed' if not job.get('prompt_id') or job.get('remote_status') == 'failed' else 'detached'
        update(status, error=client.clean_error(exc))
        raise
    finally:
        client.close()
