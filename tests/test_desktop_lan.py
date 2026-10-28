"""Embedded service shares desktop state and has an independent network lifecycle."""
import json
import asyncio
import socket
import threading
import uuid

import aiohttp
import pytest
import requests
from PIL import Image
from PySide6.QtCore import QSettings
from studio import service as module
from studio.service import StudioService
from studio.storage import Project
from studio.lan.desktop_control import DesktopLanControl
from test_lan import app, network


@pytest.fixture
def control(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'QSettings', lambda *_: QSettings(str(tmp_path/'settings.ini'), QSettings.IniFormat))
    passwords = {}
    monkeypatch.setattr(module.keyring, 'get_password', lambda service, user: passwords.get((service, user)))
    monkeypatch.setattr(module.keyring, 'set_password', lambda service, user, value: passwords.__setitem__((service, user), value))
    service = StudioService()
    service.load(Project(tmp_path/'shared', create=True).root)
    panel = DesktopLanControl(service)
    panel.bind.setCurrentText('127.0.0.1')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        panel.port.setValue(sock.getsockname()[1])
    yield service, panel
    panel.stop()
    panel.deleteLater()
    service.shutdown()


def test_embedded_start_hide_stop_restart_same_desktop(control):
    service, panel = control
    project = service.project
    assert panel.server is None
    panel.start()
    server = panel.server
    password = server.pairing.code
    assert panel.host.service is service and panel.host.current_allowed()
    session = requests.Session(); session.trust_env = False
    token = session.post(server.base+'/pair', json={'code': password}, timeout=3).json()['token']
    def rpc(command, payload=None):
        return network(lambda: session.post(server.base+'/rpc', headers={'Authorization': 'Bearer '+token},
                       json={'id':str(uuid.uuid4()), 'command':command, 'payload':payload or {},
                             'projectId':project.data['id'], 'revision':panel.host.revision}, timeout=5)).json()
    assert rpc('bootstrap')['result']['project']['id'] == project.data['id']
    assert not rpc('lan.open')['ok']
    assert rpc('project.story', {'text':'Saved through the shared backend'})['ok']
    assert service.project.data['story'] == 'Saved through the shared backend'
    panel.show(); app.processEvents(); panel.close()
    assert not panel.isVisible() and server.thread.is_alive()
    panel.stop()
    assert not server.thread.is_alive() and service.project is project and not service.closing
    service.dispatch('project.save', {})
    panel.start()
    assert panel.server.pairing.code == password
    with pytest.raises(PermissionError): panel.server.pairing.require(token)


def test_desktop_switch_follows_while_hidden_and_stops_with_server(control, tmp_path):
    service, panel = control
    panel.start()
    panel.hide()
    original = service.project
    other = Project(tmp_path/'second', create=True)
    service.load(other.root)
    assert panel.host.state()['project']['id'] == other.data['id']
    assert len(panel.host.state()['recent']) == 2
    service.load(original.root)
    assert panel.host.state()['project']['id'] == original.data['id']
    panel.stop()
    assert not panel.host.allowed and not panel.host.follow_current
    third = Project(tmp_path/'not-yet-shared', create=True)
    service.load(third.root)
    assert not panel.host.allowed and panel.host.state()['project'] is None
    panel.start()
    assert panel.host.state()['project']['id'] == third.data['id']


def test_all_registered_projects_restore_without_open_current(control, tmp_path):
    service, panel = control
    old = Project(tmp_path/'older-than-recent-menu', create=True)
    invalid = tmp_path/'invalid'
    invalid.mkdir(); (invalid/'project.json').write_text('[]')
    service.settings.setValue('lan/project_catalog', json.dumps([str(old.root), str(invalid), str(tmp_path/'missing')]))
    recent = Project(tmp_path/'recent', create=True)
    service.recent.append({'path': str(recent.root), 'title': recent.data['title']})
    service.project_lock.unlock(); service.project_lock = None; service.project = None
    panel.start()
    state = panel.host.state()
    assert state['project'] is None and len(state['recent']) == 3
    assert old.root in panel.host.allowed.values() and recent.root in panel.host.allowed.values()
    hidden = Project(tmp_path/'never-registered', create=True)
    assert hidden.root not in panel.host.allowed.values()
    opened = next(i for i, p in panel.host.allowed.items() if p == old.root)
    assert panel.host.command({'command':'project.open', 'payload':{'path':opened}})
    assert service.project.data['id'] == old.data['id']
    panel.stop()
    service.recent = []  # The catalogue survives the recent-menu limit and restart.
    panel.start()
    assert recent.root in panel.host.allowed.values()


def test_start_before_first_project_then_create_auto_sync(control, tmp_path):
    service, panel = control
    service.project_lock.unlock(); service.project_lock = None; service.project = None
    service.recent = []
    panel.start()
    assert panel.host.state()['project'] is None
    service.load(tmp_path/'created-on-pc', create=True, title='Created on PC')
    assert panel.host.state()['project']['id'] == service.project.data['id']
    assert str(service.project.root) in json.loads(service.settings.value('lan/project_catalog'))


def test_live_socket_follows_switch_and_rejects_stale_writes_media(control, tmp_path):
    service, panel = control
    panel.start()
    server, host = panel.server, panel.host
    original = service.project
    Image.new('RGB', (16, 16), 'red').save(original.file('assets/first.png'))
    old_media = host.sanitize(service.media_url('assets/first.png')).split('/')[-1]
    old_id, old_revision = original.data['id'], host.revision
    other = Project(tmp_path/'socket-follow', create=True)
    token = server.pairing.pair(server.pairing.code, 'test-socket')
    ready = threading.Event()

    async def watch():
        async with aiohttp.ClientSession() as client:
            async with client.ws_connect(server.base+'/events') as ws:
                await ws.send_json({'token':token})
                first = await ws.receive_json(timeout=5)
                ready.set()
                while True:
                    next_state = await ws.receive_json(timeout=5)
                    if next_state['state']['project']['id'] != old_id:
                        return first, next_state

    # Timer runs on the Qt owner thread; the socket remains open during switching.
    from PySide6.QtCore import QTimer
    timer = QTimer()
    def switch():
        if ready.is_set():
            timer.stop()
            service.load(other.root)
    timer.timeout.connect(switch); timer.start(10)
    try:
        before, after = network(lambda: asyncio.run(watch()))
    finally:
        timer.stop()
    assert before['state']['project']['id'] == old_id
    assert after['state']['project']['id'] == other.data['id']
    with pytest.raises(ValueError, match='项目已切换'):
        host.command({'command':'project.story','payload':{'text':'stale edit'},'projectId':old_id,'revision':old_revision})
    with pytest.raises(PermissionError): host.resolve_media(old_media)
    with pytest.raises(PermissionError): server.pairing.require('not-authorized')
    assert service.project.data['story'] == ''


def test_failed_start_does_not_leave_automatic_sharing_enabled(control, monkeypatch):
    service, panel = control
    from studio.lan import desktop_control
    def fail(*args, **kwargs): raise OSError('port already in use')
    monkeypatch.setattr(desktop_control, 'LanServer', fail)
    with pytest.raises(OSError): panel.start()
    assert panel.server is None and not panel.host.follow_current and not panel.host.allowed


def test_local_bridge_routes_panel_without_service_dispatch(control):
    from studio.desktop import Bridge
    service, panel = control
    calls, replies = [], []
    bridge = Bridge(service, {'lan.open': lambda: calls.append('open') or True})
    bridge.reply.connect(lambda raw: replies.append(json.loads(raw)))
    bridge.request(json.dumps({'id':'button', 'command':'lan.open', 'payload':{}}))
    assert calls == ['open'] and replies[-1] == {'id':'button', 'ok':True, 'result':True}
    bridge.request(json.dumps({'id':'existing', 'command':'bootstrap', 'payload':{}}))
    assert replies[-1]['ok'] and replies[-1]['result']['project']['id'] == service.project.data['id']
