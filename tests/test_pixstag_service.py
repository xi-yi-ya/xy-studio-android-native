"""Shared desktop/LAN business path with isolated projects; never paid traffic."""
import json
from unittest.mock import Mock

import pytest
from PIL import Image

from studio import service as module
from studio.lan.host import Host
from studio.storage import Project
from test_desktop_service import service, call


def configure(monkeypatch):
    keys={('AIStoryStudio','pixstag'):'unit-secret'}
    monkeypatch.setattr(module.keyring,'get_password',lambda app,user:keys.get((app,user)))
    monkeypatch.setattr(module.keyring,'set_password',lambda app,user,value:keys.__setitem__((app,user),value))
    return keys


def test_cloud_preview_is_local_and_settings_key_never_reaches_lan(service,tmp_path,monkeypatch):
    keys=configure(monkeypatch)
    client=Mock(side_effect=AssertionError('preview must not instantiate a network client'))
    monkeypatch.setattr(module,'Pixstag',client)
    source=tmp_path/'ref.webp';Image.new('RGB',(40,60),'teal').save(source)
    ref=service.project.import_file(source)
    g=call(service,'generation.defaults',mode='pixstag_i2v',kind='video')
    assert g['seconds']==5 and g['api_resolution']=='720P' and g['steps']==0
    g.update(prompt='人物缓慢转头',references=[ref])
    preview=call(service,'generation.preview',generation=g)
    assert preview['provider']=='pixstag' and preview['references'][0]['converted']
    assert preview['keySet'] and 'frames' not in preview and 'steps' not in preview
    assert not service.project.data['jobs'];client.assert_not_called()
    call(service,'settings.save',pixstagKey='Bearer replacement-secret')
    assert keys[('AIStoryStudio','pixstag')]=='replacement-secret'
    host=Host(service,tmp_path/'remote-projects');host.authorize(service.project.root)
    snapshot=host.state()
    assert snapshot['config']['pixstagKeySet'] is True
    assert 'replacement-secret' not in json.dumps(snapshot)
    with pytest.raises(PermissionError):host.command({'command':'settings.save','payload':{'pixstagKey':'remote-injection'}})
    with pytest.raises(PermissionError):host.command({'command':'pixstag.check','payload':{}})
    assert keys[('AIStoryStudio','pixstag')]=='replacement-secret'


def test_cloud_queue_task_kind_cancellation_and_original_schema(service,monkeypatch):
    configure(monkeypatch)
    service.project.data['queue_paused']=True
    g=call(service,'generation.defaults',mode='pixstag_t2v',kind='video');g['prompt']='云端测试，不实际提交'
    ident=call(service,'generation.submit',generation=g)
    task=service.snapshot()['project']['tasks'][0]
    assert task['kind']=='video' and task['provider']=='pixstag' and task['canCancel']
    assert task['progress'] is None and task['remoteId'] is None
    assert task['generation']['steps']==0
    call(service,'task.cancel',id=ident)
    assert service.project.data['jobs'][0]['status']=='cancelled'
    assert Project(service.project.root).data['schema']==1
    j=service.project.data['jobs'][0];j.update(status='queued',prompt_id='remote-123')
    task=service.snapshot()['project']['tasks'][0]
    assert not task['canCancel']
    with pytest.raises(ValueError,match='未提供取消'):call(service,'task.cancel',id=ident)


def test_cloud_worker_selects_api_and_resume_preserves_remote_id(service,monkeypatch):
    configure(monkeypatch)
    service.project.data['queue_paused']=True
    g=call(service,'generation.defaults',mode='pixstag_t2v',kind='video');g['prompt']='test'
    ident=call(service,'generation.submit',generation=g)
    j=service.project.data['jobs'][0];j.update(prompt_id='known-id',status='detached')
    marker=object();api=Mock(return_value=marker);runner=Mock(return_value=[])
    monkeypatch.setattr(module,'Pixstag',api);monkeypatch.setattr(module,'execute_pixstag',runner)
    monkeypatch.setattr(module,'Comfy',Mock(side_effect=AssertionError('cloud must not contact ComfyUI')))
    monkeypatch.setattr(service,'_spawn',lambda kind,fn:fn())
    call(service,'task.resume',id=ident)
    assert runner.call_count==1 and runner.call_args.args[0] is marker
    assert runner.call_args.args[2]['prompt_id']=='known-id'
    assert len(service.project.data['jobs'])==1


def test_cloud_missing_key_or_bad_duration_does_not_enqueue(service):
    g=call(service,'generation.defaults',mode='pixstag_t2v',kind='video');g['prompt']='test'
    with pytest.raises(ValueError,match='API Key'):call(service,'generation.submit',generation=g)
    g['seconds']=2
    with pytest.raises(ValueError,match='4–30'):call(service,'generation.submit',generation=g)
    assert service.project.data['jobs']==[]
