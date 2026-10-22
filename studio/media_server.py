"""Loopback static/media server. No business endpoints or filesystem listing."""
import mimetypes
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

MEDIA_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.mp4', '.webm', '.mkv'}


class MediaServer:
    def __init__(self, service, frontend):
        owner = self
        self.service = service
        self.frontend = Path(frontend).resolve()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                self.serve(False)
            def do_HEAD(self):
                self.serve(True)
            def serve(self, head):
                try:
                    path = unquote(urlsplit(self.path).path)
                    if path.startswith('/project-media/'):
                        parts = path.split('/', 3)
                        if len(parts) != 4 or parts[2] != owner.service.media_token or not owner.service.project:
                            self.send_error(403); return
                        relative = parts[3]
                        target = owner.service.project.file(relative)
                        if target.suffix.lower() not in MEDIA_SUFFIXES:
                            self.send_error(403); return
                    else:
                        target = (owner.frontend/(path.lstrip('/') or 'index.html')).resolve()
                        if not target.is_relative_to(owner.frontend):
                            self.send_error(403); return
                    if not target.is_file():
                        self.send_error(404); return
                    size = target.stat().st_size
                    start, end, ranged = 0, size-1, False
                    header = self.headers.get('Range')
                    if header:
                        match = re.fullmatch(r'bytes=(\d*)-(\d*)', header)
                        if not match or not any(match.groups()):
                            self.send_error(416); return
                        a, b = match.groups()
                        start, end = (int(a), min(size-1, int(b) if b else size-1)) if a else (max(0,size-int(b)),size-1)
                        if start > end or start >= size:
                            self.send_response(416);self.send_header('Content-Range', f'bytes */{size}');self.end_headers();return
                        ranged = True
                    self.send_response(206 if ranged else 200)
                    self.send_header('Content-Type', mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
                    self.send_header('Content-Length', str(end-start+1))
                    self.send_header('Accept-Ranges', 'bytes')
                    self.send_header('Cache-Control', 'no-cache')
                    self.send_header('X-Content-Type-Options', 'nosniff')
                    if target.suffix == '.html':
                        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self'; connect-src 'self'; object-src 'none'; frame-src 'none'")
                    if ranged:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
                    self.end_headers()
                    if not head:
                        with target.open('rb') as stream:
                            stream.seek(start)
                            left = end-start+1
                            while left:
                                block = stream.read(min(left,256*1024))
                                if not block:break
                                self.wfile.write(block);left -= len(block)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except (ValueError, OSError):
                    self.send_error(403)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, name='xy-media', daemon=True)
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        service.media_base = self.base
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
