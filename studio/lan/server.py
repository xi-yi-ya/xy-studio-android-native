import asyncio
import hashlib
import hmac
import json
import secrets
import tempfile
import threading
from collections import OrderedDict
from pathlib import Path

from aiohttp import web, WSMsgType
from .security import Pairing, local_address
from ..media_server import MEDIA_SUFFIXES


class LanServer:
    def __init__(self, host, bind='127.0.0.1', port=8765, origins=(), pairing=None):
        if not local_address(bind): raise ValueError('只能绑定明确的局域网 IPv4 或回环地址')
        self.host, self.bind, self.port = host, bind, port
        self.pairing = pairing or Pairing()
        self.origins = {'http://localhost', 'https://localhost', *origins}
        self.clients = {}
        self.results = OrderedDict()
        self.started = threading.Event()
        self.error = None
        self.loop = None
        host.changed.connect(self.changed)
        host.notice.connect(self.notice)
        self.thread = threading.Thread(target=self.run, name='xy-lan', daemon=True)
        self.thread.start()
        if not self.started.wait(10): raise RuntimeError('LAN 服务启动超时')
        if self.error:
            self.host.changed.disconnect(self.changed)
            self.host.notice.disconnect(self.notice)
            raise self.error

    def run(self):
        try: asyncio.run(self.main())
        except Exception as exc:
            self.error = exc
            self.started.set()

    async def main(self):
        self.loop = asyncio.get_running_loop()
        self.dirty = asyncio.Event()
        self.stop = asyncio.Event()
        self.serial = asyncio.Lock()

        @web.middleware
        async def boundary(request, handler):
            origin = request.headers.get('Origin')
            if not local_address(request.remote or ''):
                return web.json_response({'error':'仅允许局域网访问'}, status=403)
            if origin and origin not in self.origins:
                return web.json_response({'error':'来源不允许'}, status=403)
            try:
                if request.method == 'OPTIONS': response = web.Response(status=204)
                else: response = await handler(request)
            except PermissionError as exc:
                response = web.json_response({'error':str(exc)}, status=401)
            except (ValueError, KeyError, TypeError) as exc:
                response = web.json_response({'error':str(exc)}, status=400)
            except web.HTTPException as exc: response = exc
            except Exception:
                response = web.json_response({'error':'PC 操作失败，请检查 PC 服务日志或状态'}, status=500)
            if origin:
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Vary'] = 'Origin'
                response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
                response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, Range'
                response.headers['Access-Control-Expose-Headers'] = 'Content-Range, Content-Length'
            response.headers['Cache-Control'] = 'no-store'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['Referrer-Policy'] = 'no-referrer'
            return response

        app = web.Application(middlewares=[boundary], client_max_size=100*1024*1024)
        app.add_routes([web.get('/health', self.health), web.post('/pair', self.pair),
                        web.post('/rpc', self.rpc), web.get('/events', self.events),
                        web.get('/media/{ident}', self.media), web.post('/upload', self.upload),
                        web.options('/{tail:.*}', self.options)])
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, self.bind, self.port)
        await site.start()
        self.port = site._server.sockets[0].getsockname()[1]
        self.base = f'http://{self.bind}:{self.port}'
        self.started.set()
        broadcaster = asyncio.create_task(self.broadcast())
        await self.stop.wait()
        broadcaster.cancel()
        for ws in list(self.clients): await ws.close(code=1001)
        await runner.cleanup()

    async def invoke(self, action, payload=None):
        return await asyncio.wrap_future(self.host.call(action, payload))

    async def health(self, request):
        return web.json_response({'service':'XY Studio LAN','protocol':1})

    async def options(self, request):
        return web.Response(status=204)

    async def small_json(self, request):
        if request.content_length is None or request.content_length > 4*1024*1024:
            raise web.HTTPRequestEntityTooLarge(max_size=4*1024*1024, actual_size=request.content_length or 0)
        body = await request.json()
        if not isinstance(body, dict): raise ValueError('请求必须是对象')
        return body

    async def pair(self, request):
        a = await self.small_json(request)
        token = self.pairing.pair(a.get('code',''), a.get('name','Android'))
        return web.json_response({'token':token, 'expiresIn':8*3600})

    def auth(self, request):
        header = request.headers.get('Authorization','')
        token = header[7:] if header.startswith('Bearer ') else ''
        self.pairing.require(token)
        return token

    def sign_media(self, value, token):
        if isinstance(value, dict): return {k:self.sign_media(v,token) for k,v in value.items()}
        if isinstance(value, list): return [self.sign_media(v,token) for v in value]
        if isinstance(value, str) and value.startswith('/media/'):
            ident = value.split('/')[-1]
            sid = hashlib.sha256(token.encode()).hexdigest()[:32]
            sig = hmac.new(token.encode(), ident.encode(), hashlib.sha256).hexdigest()
            return value+'?sid='+sid+'&sig='+sig
        return value

    async def rpc(self, request):
        token = self.auth(request)
        body = await self.small_json(request)
        ident = body.get('id')
        if not isinstance(ident, str) or not 8 <= len(ident) <= 100: raise ValueError('请求 ID 无效')
        digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        # Serialize network commands as well as Qt writes; deduplicate explicit
        # request retries so an uncertain response cannot submit a second render.
        async with self.serial:
            self.pairing.require(token)
            key = (token, ident)
            if key in self.results:
                old_digest, result = self.results[key]
                if digest != old_digest: raise ValueError('请求 ID 已用于不同操作')
            else:
                try:
                    result = {'ok':True, 'result':await self.invoke('command', body)}
                except (PermissionError, ValueError, KeyError, TypeError) as exc:
                    result = {'ok':False, 'error':str(exc)}
                result['state'] = await self.invoke('state')
                self.results[key] = (digest, result)
                while len(self.results) > 512: self.results.popitem(last=False)
        return web.json_response(self.sign_media(result, token))

    async def events(self, request):
        if len(self.clients) >= 16: raise web.HTTPTooManyRequests()
        ws = web.WebSocketResponse(heartbeat=15, max_msg_size=4096)
        await ws.prepare(request)
        try:
            first = await asyncio.wait_for(ws.receive(), 5)
            if first.type != WSMsgType.TEXT: return ws
            token = json.loads(first.data).get('token','')
            self.pairing.require(token)
            self.clients[ws] = token
            await ws.send_json({'type':'state','state':self.sign_media(await self.invoke('state'), token)})
            async for msg in ws:
                self.pairing.require(token)
                if msg.type == WSMsgType.TEXT and msg.data == 'ping': await ws.send_str('pong')
        except (PermissionError, ValueError, asyncio.TimeoutError):
            await ws.close(code=4001, message=b'Pairing required')
        finally:
            self.clients.pop(ws, None)
        return ws

    def changed(self):
        if self.loop and not self.loop.is_closed(): self.loop.call_soon_threadsafe(self.dirty.set)

    def notice(self, message):
        # State contains the authoritative status; don't forward arbitrary desktop
        # notifications (which may refer to a project that wasn't authorized).
        self.changed()

    async def broadcast(self):
        while True:
            try: await asyncio.wait_for(self.dirty.wait(), 10)
            except asyncio.TimeoutError: pass
            self.dirty.clear()
            await asyncio.sleep(.15)
            if not self.clients: continue
            state = await self.invoke('state')
            for ws, token in list(self.clients.items()):
                try:
                    self.pairing.require(token)
                    await asyncio.wait_for(ws.send_json({'type':'state','state':self.sign_media(state,token)}), 3)
                except (PermissionError, ConnectionError, asyncio.TimeoutError):
                    await ws.close(code=4001)

    async def media(self, request):
        ident, sid, sig = request.match_info['ident'], request.query.get('sid'), request.query.get('sig','')
        token = next((t for t in self.pairing.sessions if hashlib.sha256(t.encode()).hexdigest()[:32] == sid), '')
        self.pairing.require(token)
        expected = hmac.new(token.encode(), ident.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected): raise PermissionError('素材授权无效')
        target = await self.invoke('media', ident)
        return web.FileResponse(target, headers={'Accept-Ranges':'bytes'})

    async def upload(self, request):
        self.auth(request)
        reader = await request.multipart()
        field = await reader.next()
        if not field or field.name != 'metadata': raise ValueError('缺少导入参数')
        # Bound each field while streaming, rather than reading arbitrary bytes.
        metadata = await field.read_chunk(8192)
        if not field.at_eof(): raise ValueError('导入参数过长')
        a = json.loads(metadata)
        field = await reader.next()
        if not field or field.name != 'file': raise ValueError('缺少素材')
        suffix = Path(field.filename or '').suffix.lower()
        if suffix not in MEDIA_SUFFIXES: raise ValueError('只支持图片或视频文件')
        with tempfile.TemporaryDirectory(prefix='xy-lan-upload-') as temp:
            path = Path(temp)/('upload'+suffix)
            size = 0
            with path.open('wb') as stream:
                while block := await field.read_chunk(256*1024):
                    size += len(block)
                    if size > 100*1024*1024: raise ValueError('单个素材不能超过 100 MB')
                    stream.write(block)
            async with self.serial:
                self.auth(request)
                result = await self.invoke('upload', (path, a.get('projectId'), a.get('command'), a.get('payload',{})))
        return web.json_response({'result':result})

    def revoke(self):
        self.pairing.revoke()
        self.changed()

    def close(self):
        if self.loop and not self.loop.is_closed(): self.loop.call_soon_threadsafe(self.stop.set)
        self.thread.join(timeout=5)
        if self.thread.is_alive(): raise RuntimeError('LAN 服务仍在停止，请稍后重试')
        if not getattr(self, '_disconnected', False):
            self.host.changed.disconnect(self.changed)
            self.host.notice.disconnect(self.notice)
            self._disconnected = True
