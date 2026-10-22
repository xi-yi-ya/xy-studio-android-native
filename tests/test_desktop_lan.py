"""Embedded service shares desktop state and has an independent network lifecycle."""
import json
import socket
import uuid

import pytest
import requests
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


def test_desktop_project_switch_needs_explicit_share(control, tmp_path):
    service, panel = control
    panel.start()
    other = Project(tmp_path/'private', create=True)
    service.load(other.root)
    assert panel.host.state()['project'] is None
    panel.share_current()
    assert panel.host.state()['project']['id'] == other.data['id']
    panel.stop()
    assert not panel.host.allowed


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
