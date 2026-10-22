"""Real local HTTP/WS tests over temporary projects, not generation acceptance."""
import asyncio
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import aiohttp
import pytest
import requests
from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from studio import service as module
from studio.service import StudioService
from studio.storage import Project
from studio.lan.host import Host
from studio.lan.server import LanServer
from studio.lan.security import Pairing, local_address

app = QApplication.instance() or QApplication([])


def network(fn):
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(fn)
        end = time.monotonic()+15
        while not future.done() and time.monotonic() < end:
            app.processEvents()
            time.sleep(.002)
        return future.result(timeout=1)


@pytest.fixture
def lan(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'QSettings', lambda *_: QSettings(str(tmp_path/'settings.ini'), QSettings.IniFormat))
    monkeypatch.setattr(module.keyring, 'get_password', lambda *_:'SECRET-MUST-STAY-PC')
    service = StudioService()
    p = Project(tmp_path/'real-files', create=True)
    Image.new('RGB',(32,24),'green').save(p.file('assets/check.png'))
    host = Host(service, tmp_path/'new-projects')
    ident = host.authorize(p.root)
    service.load(p.root)
    server = LanServer(host, port=0)
    session = requests.Session(); session.trust_env=False
    def req(method, path, **kwargs):
        return network(lambda: session.request(method, server.base+path, timeout=10, **kwargs))
    response = req('POST','/pair',json={'code':server.pairing.code,'name':'test-device'})
    token = response.json()['token']
    session.headers['Authorization'] = 'Bearer '+token
    def rpc(command, payload=None, **extra):
        body = {'id':str(uuid.uuid4()),'command':command,'payload':payload or {},
                'projectId':service.project.data['id'], 'revision':host.revision, **extra}
        return req('POST','/rpc',json=body).json()
    yield service, host, server, req, rpc, token, ident
    server.close()
    service.shutdown()


def test_persistent_password_session_expiry_rate_limit_and_lan_bind():
    p=Pairing();code=p.code
    token=p.pair(code,'phone');assert p.require(token)
    assert p.require(p.pair(code,'other'))
    p.revoke()
    with pytest.raises(PermissionError):p.require(token)
    with pytest.raises(PermissionError):p.pair(code,'revoked')
    late=p.pair(p.code,'late');p.sessions[late]['expires']=0
    with pytest.raises(PermissionError):p.require(late)
    p.rotate()
    for _ in range(10):
        with pytest.raises(PermissionError):p.pair('wrong','other')
    with pytest.raises(PermissionError):p.pair(p.code,'phone')
    p.retry_after=time.monotonic()-1
    assert p.require(p.pair(p.code,'phone'))
    saved=[]
    first=Pairing(save_password=saved.append)
    restored=Pairing(saved[-1])
    assert restored.require(restored.pair(first.code,'remembered device'))
    for ip in ('0.0.0.0','8.8.8.8','198.18.0.1','example.com'):assert not local_address(ip)
    for ip in ('127.0.0.1','192.168.50.198','172.20.1.3','10.1.2.3'):assert local_address(ip)


def test_auth_origin_and_private_capabilities(lan):
    s,h,server,req,rpc,token,ident=lan
    assert req('POST','/rpc',json={},headers={'Authorization':''}).status_code==401
    assert req('POST','/rpc',json={},headers={'Origin':'https://evil.example'}).status_code==403
    state=rpc('bootstrap')['result']
    assert state['project']['id']==s.project.data['id']
    assert state['recent'][0]['path']==ident
    assert 'SECRET-MUST-STAY-PC' not in json.dumps(state)
    assert str(s.project.root) not in json.dumps(state,ensure_ascii=False)
    for cmd,args in [('settings.save',{'key':'overwrite'}),('settings.save',{'comfy':'http://evil.example'}),
                     ('project.open',{'path':str(s.project.root)}),('library.import',{'paths':['C:/secret.png']}),
                     ('references.import',{'paths':['C:/secret.png']}),('agent.import',{'path':'C:/secret.json'}),
                     ('media.open',{'file':'project.json'}),('app.close',{})]:
        assert rpc(cmd,args)['ok'] is False, cmd


def test_media_range_revocation_and_traversal(lan):
    s,h,server,req,rpc,token,ident=lan
    result=rpc('library.query',{'kind':'image'})['result']
    url=result['items'][0]['media']
    assert url.startswith('/media/') and token not in url
    r=req('GET',url,headers={'Range':'bytes=0-15','Authorization':''})
    assert r.status_code==206 and len(r.content)==16 and r.headers['Content-Range'].startswith('bytes 0-15/')
    assert req('GET',url.split('?')[0]).status_code==401
    assert req('GET',url.replace('sig=','sig=x')).status_code==401
    assert not rpc('references.describe',{'files':['../secret.png']})['ok']
    assert req('GET','/media/project.json').status_code==401
    server.revoke()
    assert req('GET',url).status_code==401


def test_mutation_serialization_stale_guard_dedup_and_review(lan):
    s,h,server,req,rpc,token,ident=lan
    stale=h.revision
    assert rpc('project.story',{'text':'one'})['ok']
    assert not rpc('project.story',{'text':'stale'},revision=stale)['ok']
    assert s.project.data['story']=='one'
    body={'id':str(uuid.uuid4()),'command':'asset.add','payload':{'kind':'shots'},'projectId':s.project.data['id']}
    first=req('POST','/rpc',json=body).json()
    second=req('POST','/rpc',json=body).json()
    assert first['result']==second['result'] and len(s.project.data['shots'])==1
    assert not rpc('project.story',{'text':'wrong project'},projectId='other')['ok']
    s._accept_message({'role':'assistant','content':'review','tool_calls':[{'id':'test-call','type':'function',
        'function':{'name':'set_story','arguments':json.dumps({'text':'approved'})}}]})
    assert s.project.data['story']=='one'
    assert not rpc('review.respond',{'id':s.pending['id'],'accepted':'false'})['ok']
    assert rpc('review.respond',{'id':s.pending['id'],'accepted':True})['ok']
    assert s.project.data['story']=='approved'
    assert Project(s.project.root).data['story']=='approved'


def test_websocket_bootstrap_and_upload(lan):
    s,h,server,req,rpc,token,ident=lan
    async def connect():
        async with aiohttp.ClientSession() as client:
            async with client.ws_connect(server.base+'/events') as ws:
                await ws.send_json({'token':token})
                return await ws.receive_json(timeout=5)
    message=network(lambda:asyncio.run(connect()))
    assert message['state']['project']['id']==s.project.data['id']
    data=s.project.file('assets/check.png').read_bytes()
    metadata={'projectId':s.project.data['id'],'command':'library.import','payload':{'kind':'image'}}
    response=req('POST','/upload',files={'metadata':(None,json.dumps(metadata)), 'file':('phone.png',data,'image/png')})
    assert response.status_code==200,response.text
    file=response.json()['result'][0]
    assert s.project.file(file).read_bytes()==data
    assert len(rpc('library.query',{'kind':'image'})['result']['items'])==2


def test_project_switch_invalidates_media_and_unapproved_state(lan,tmp_path):
    s,h,server,req,rpc,token,ident=lan
    url=rpc('library.query',{'kind':'image'})['result']['items'][0]['media']
    outside=Project(tmp_path/'not-authorized',create=True)
    s.load(outside.root)
    state=rpc('bootstrap')['result']
    assert state['project'] is None and state['review'] is None
    assert req('GET',url).status_code==401
    assert not rpc('project.story',{'text':'forbidden'})['ok']
    assert rpc('project.open',{'path':ident})['ok']
    assert req('GET',url).status_code==401
