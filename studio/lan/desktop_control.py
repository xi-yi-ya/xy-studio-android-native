"""LAN lifecycle for the normal desktop. The existing StudioService owns all data."""
import time
from pathlib import Path

import keyring
from PySide6.QtCore import Qt, QTimer
from PySide6.QtNetwork import QNetworkInterface
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QComboBox, QSpinBox, QMessageBox)

from .host import Host
from .security import Pairing, local_address
from .server import LanServer


def addresses():
    result = []
    for interface in QNetworkInterface.allInterfaces():
        if not interface.flags() & QNetworkInterface.IsUp:
            continue
        for entry in interface.addressEntries():
            ip = entry.ip().toString()
            if ':' not in ip and local_address(ip) and not ip.startswith('127.'):
                virtual = any(word in interface.humanReadableName().lower()
                              for word in ('virtual', 'vethernet', 'wsl', 'docker', 'vmware'))
                result.append((virtual, ip, interface.humanReadableName()))
    return sorted(set(result))


class DesktopLanControl(QWidget):
    def __init__(self, service, parent=None):
        super().__init__(parent, Qt.Window)
        self.service = service
        self.host = Host(service, Path.home()/'Documents'/'XY Studio Projects')
        self.server = None
        self.setWindowTitle('XY Studio · 手机连接')
        self.resize(620, 440)
        layout = QVBoxLayout(self)
        intro = QLabel('服务开启后，手机可浏览 Studio 已登记的全部项目，打开或新建项目会自动加入列表。两端共用当前项目，切换后自动跟随，无需再次共享。')
        intro.setWordWrap(True)
        layout.addWidget(intro)
        row = QHBoxLayout()
        self.bind = QComboBox()
        self.bind.setEditable(True)
        for _, ip, name in addresses():
            self.bind.addItem(ip, name)
        if not self.bind.count(): self.bind.addItem('127.0.0.1')
        saved = str(service.settings.value('lan/bind', ''))
        if self.bind.findText(saved) >= 0: self.bind.setCurrentText(saved)
        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        try: port = int(service.settings.value('lan/port', 8765))
        except (TypeError, ValueError): port = 8765
        self.port.setValue(port)
        row.addWidget(QLabel('PC IPv4'))
        row.addWidget(self.bind, 1)
        row.addWidget(QLabel('端口'))
        row.addWidget(self.port)
        layout.addLayout(row)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.status, 1)
        self.toggle_button = QPushButton('启动局域网服务并自动同步')
        self.toggle_button.clicked.connect(self.toggle)
        layout.addWidget(self.toggle_button)
        self.revoke_button = QPushButton('更换固定密码并撤销全部设备')
        self.revoke_button.clicked.connect(self.revoke)
        layout.addWidget(self.revoke_button)
        note = QLabel('手机首次输入固定密码后会加密记住。关闭本面板不停止服务；退出 Studio 会停止服务。\n仅用于可信局域网，不开放 ComfyUI 端口，不自动修改防火墙。')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.refresh()

    def start(self):
        if self.server: return
        bind = self.bind.currentText().strip()
        if ':' in bind or not local_address(bind):
            raise ValueError('请选择 PC 的私有 IPv4 地址；不允许绑定公网或 0.0.0.0')
        password = keyring.get_password('XY Studio LAN', 'connection-password')
        pairing = Pairing(password, lambda value: keyring.set_password('XY Studio LAN', 'connection-password', value))
        self.host.follow_desktop_projects()
        try:
            self.server = LanServer(self.host, bind, self.port.value(), pairing=pairing)
        except Exception:
            self.host.follow_current = False
            self.host.allowed.clear()
            self.host.media.clear()
            raise
        self.service.settings.setValue('lan/bind', bind)
        self.service.settings.setValue('lan/port', self.port.value())
        self.refresh()

    def stop(self):
        self.host.follow_current = False
        if self.server:
            self.server.close()
            self.server = None
        self.host.allowed.clear()
        self.host.media.clear()
        self.refresh()

    def toggle(self):
        try:
            if self.server: self.stop()
            else: self.start()
        except Exception as exc:
            QMessageBox.warning(self, '局域网服务', f'{exc}\n若端口被占用，请先停止原服务或选择其他端口。')

    def revoke(self):
        if self.server:
            self.server.revoke()
            self.refresh()

    def refresh(self):
        running = self.server is not None
        self.bind.setEnabled(not running)
        self.port.setEnabled(not running)
        self.toggle_button.setText('停止局域网服务' if running else '启动局域网服务并自动同步')
        self.revoke_button.setEnabled(running)
        if not running:
            self.status.setText('服务未启动。桌面业务可以照常使用。')
            return
        server = self.server
        devices = {s['name'] for s in list(server.pairing.sessions.values()) if s['expires'] > time.monotonic()}
        project = self.service.project
        self.status.setText(f'手机地址：{server.base}\n固定连接密码：{server.pairing.code}\n'
                            f'已授权设备：{"、".join(sorted(devices)) or "无"} · 在线连接：{len(server.clients)}\n'
                            f'全部已登记项目：{len(self.host.allowed)} 个可访问 · 自动跟随已开启\n'
                            f'当前项目：{project.data["title"] if project else "尚未打开，可在 PC 或手机项目列表选择"}')

    def closeEvent(self, event):
        self.hide()
        event.ignore()
