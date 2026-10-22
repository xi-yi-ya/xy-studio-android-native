import argparse
import json
import signal
import sys
import time
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox
from ..service import StudioService
from .host import Host
from .server import LanServer
from .security import Pairing
import keyring


class Control(QWidget):
    def __init__(self, service, host, server, root):
        super().__init__()
        self.service, self.host, self.server, self.root = service, host, server, root
        self.desktop = None
        self.setWindowTitle('XY Studio · 局域网服务')
        self.resize(620, 430)
        layout = QVBoxLayout(self)
        self.address = QLabel('手机连接地址：'+server.base+'\n仅用于可信局域网；请勿做公网端口转发。')
        self.address.setWordWrap(True)
        layout.addWidget(self.address)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        for label, callback in [('授权并打开已有项目', self.open_project),
                                ('打开共用桌面工作台', self.show_desktop),
                                ('更换连接密码并撤销全部设备', self.revoke)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            layout.addWidget(button)
        layout.addWidget(QLabel('独立旧版桌面程序需先关闭该项目。此处打开的桌面与手机共用同一实例。\n关闭此窗口将停止 LAN 服务；项目和素材保留。'))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.refresh()

    def refresh(self):
        p = self.service.project
        names = '、'.join(s['name'] for s in list(self.server.pairing.sessions.values())) or '无'
        pairing = self.server.pairing
        code_label = pairing.code
        self.status.setText(f"固定连接密码（首次输入，手机加密记住）：{code_label}\n"
                            f"已配对设备：{names}\n在线连接：{len(self.server.clients)}\n"
                            f"授权项目：{len(self.host.allowed)} 个\n当前项目：{p.data['title'] if p else '未打开'}\n"
                            f"状态：{self.service.status}\n{self.service.last_error}")

    def open_project(self):
        path = QFileDialog.getOpenFileName(self, '授权项目', '', 'XY Studio 项目 (project.json)')[0]
        if path:
            try:
                self.host.authorize(path)
                self.service.load(path)
            except Exception as exc: QMessageBox.warning(self, '未打开', str(exc))

    def show_desktop(self):
        if self.desktop is None:
            from ..desktop import Desktop
            self.desktop = Desktop(self.root/'frontend'/'dist', service=self.service, lan_control=self)
        self.desktop.show()
        self.desktop.raise_()

    def rotate(self):
        self.server.pairing.rotate()
        self.refresh()

    def revoke(self):
        self.server.revoke()
        self.refresh()

    def closeEvent(self, event):
        try:
            self.service.shutdown()
        except Exception as exc:
            self.service.closing = False
            QMessageBox.warning(self, '无法停止', str(exc))
            event.ignore()
            return
        self.server.close()
        if self.desktop: self.desktop.server.close()
        QApplication.instance().quit()
        event.accept()


def main():
    parser = argparse.ArgumentParser(description='XY Studio LAN — private network only')
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--project', action='append', default=[])
    parser.add_argument('--project-home', default=str(Path.home()/'Documents'/'XY Studio Projects'))
    parser.add_argument('--headless', action='store_true', help='No control window (automated local QA)')
    parser.add_argument('--ready-file', help='Local QA only, contains connection password; do not share')
    parser.add_argument('--allow-origin', action='append', default=[], help='Explicit local QA browser origins')
    args = parser.parse_args()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    service = StudioService()
    host = Host(service, args.project_home)
    for path in args.project: host.authorize(path)
    if args.project: service.load(args.project[0])
    password = keyring.get_password('XY Studio LAN', 'connection-password')
    pairing = Pairing(password, lambda value: keyring.set_password('XY Studio LAN', 'connection-password', value))
    server = LanServer(host, args.bind, args.port, args.allow_origin, pairing=pairing)
    root = Path(__file__).resolve().parents[2]
    control = Control(service, host, server, root)
    if not args.headless: control.show()
    if args.ready_file:
        Path(args.ready_file).write_text(json.dumps({'base':server.base,'code':server.pairing.code}), encoding='utf-8')
    print('XY Studio LAN:', server.base, flush=True)
    if args.headless: print('Headless QA: connection password written only to --ready-file', flush=True)
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)
    signal.signal(signal.SIGINT, lambda *_: control.close())
    code = app.exec()
    return code


if __name__ == '__main__': sys.exit(main())
