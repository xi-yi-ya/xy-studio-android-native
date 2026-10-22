import ipaddress
import secrets
import time


def local_address(value):
    try:
        ip = ipaddress.ip_address(value)
        return ip.is_loopback or any(ip in ipaddress.ip_network(n) for n in
                                    ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
    except ValueError:
        return False


class Pairing:
    """Reusable PC password; session tokens remain revocable and expire after 8h."""
    def __init__(self, password=None, save_password=None):
        self.sessions = {}
        self.save_password = save_password
        self.code = password or self.rotate()
        self.attempts = 0
        self.retry_after = 0

    def rotate(self):
        self.code = f'{secrets.randbelow(10**12):012d}'
        self.attempts = 0
        self.retry_after = 0
        if self.save_password: self.save_password(self.code)
        return self.code

    def pair(self, code, name):
        if time.monotonic() < self.retry_after:
            raise PermissionError('连接密码连续错误过多，请 5 分钟后重试')
        if self.retry_after:
            self.attempts = 0
            self.retry_after = 0
        if not secrets.compare_digest(str(code), self.code):
            self.attempts += 1
            if self.attempts >= 10: self.retry_after = time.monotonic()+300
            raise PermissionError('连接密码错误，请核对 PC 服务窗口')
        self.attempts = 0
        for old in [t for t,s in self.sessions.items() if s['expires'] < time.monotonic()]:
            self.sessions.pop(old, None)
        if len(self.sessions) >= 128: raise PermissionError('设备会话过多，请在 PC 撤销旧授权')
        token = secrets.token_urlsafe(32)
        self.sessions[token] = {'name': str(name)[:60], 'expires': time.monotonic()+8*3600}
        return token

    def require(self, token):
        session = self.sessions.get(token)
        if not session or session['expires'] < time.monotonic():
            self.sessions.pop(token, None)
            raise PermissionError('授权已失效，请重新配对')
        return session

    def revoke(self):
        self.sessions.clear()
        self.rotate()
