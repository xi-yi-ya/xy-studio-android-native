"""Contract fixtures only: no requests to a paid generation endpoint."""
import copy
import json
import socket
from dataclasses import asdict
from unittest.mock import Mock

import pytest
import requests
from PIL import Image

from studio.pixstag import Pixstag, prepare, execute
from studio.storage import Project
from studio.workflows import Generation, API_MODELS, is_video, build


@pytest.fixture
def project(tmp_path):
    p = Project(tmp_path/'project', create=True)
    Image.new('RGB',(32,48),'teal').save(p.file('assets/reference.png'))
    Image.new('RGB',(32,48),'teal').save(p.file('assets/reference.webp'))
    p.file('assets/reference.mp4').write_bytes(b'\x00\x00\x00\x18ftypmp42'+b'fixture-not-real-video')
    return p


def job(g=None, **kw):
    return dict(id='test-contract-job', generation=asdict(g or Generation(mode='pixstag_t2v',prompt='镜头向前推进')),
                status='new', target='__library__', **kw)


@pytest.mark.parametrize('model',API_MODELS)
def test_documented_payload_models_and_frame_roles(project,model):
    g = Generation(mode='pixstag_fl2v',prompt='走过街道',seconds=5,api_model=model,
                   references=['assets/reference.png','assets/reference.webp'])
    original=project.file('assets/reference.webp').read_bytes()
    payload,audit=prepare(project,g)
    assert payload['model']==model and payload['duration']==5 and payload['resolution']=='720P'
    assert payload['use_context_ir'] is True and payload['return_last_frame'] is True and not payload['aigc_watermark']
    assert [v.get('role') for v in payload['content'][1:]]==['first_frame','last_frame']
    assert payload['content'][1]['image_url']['url'].startswith('data:image/png;base64,')
    assert audit[1]['converted'] and project.file('assets/reference.webp').read_bytes()==original
    assert is_video(g.mode)
    with pytest.raises(ValueError,match='云端'): build(g,[])


def test_reference_mode_and_upload_boundary(project):
    g=Generation(mode='pixstag_ref',prompt='参考动作',references=['assets/reference.png'],video_references=['assets/reference.mp4'])
    payload,audit=prepare(project,g)
    assert [c.get('role') for c in payload['content'][1:]]==['reference_image','reference_video']
    assert audit[1]['bytes']>0
    with pytest.raises(ValueError,match='越界'): prepare(project,Generation(mode='pixstag_i2v',prompt='x',references=['../outside.png']))
    project.data['media_trash']={'assets/reference.png':{}}
    with pytest.raises(ValueError,match='回收站'): prepare(project,g)
    project.file('assets/large.mp4').write_bytes(b'x'*(5*1024*1024+1))
    g.references=[];g.video_references=['assets/large.mp4']
    with pytest.raises(ValueError,match='5 MB'): prepare(project,g)


@pytest.mark.parametrize('values',[
    {'seconds':3},{'seconds':4.5},{'seconds':float('nan')},{'seconds':True},
    {'api_model':'other'},{'ratio':'2:3'},{'api_resolution':'480P'},
    {'api_watermark':'false'},{'prompt':'x'*5001},{'references':['a.png']},
    {'video_references':['a.mp4']},
])
def test_invalid_cloud_parameters_rejected(values):
    g=Generation(mode='pixstag_t2v',prompt='x')
    for k,v in values.items():setattr(g,k,v)
    with pytest.raises(ValueError):g.validate()


def response(value,status=200):
    r=requests.Response();r.status_code=status;r._content=json.dumps(value).encode();return r


def test_transport_auth_wrapped_result_and_no_post_retry(monkeypatch):
    client=Pixstag('Bearer test-secret')
    request=Mock(return_value=response({'data':{'task_id':'task-123'}}))
    monkeypatch.setattr(client.session,'request',request)
    assert client.submit({'model':'MiniMax-H3'})=='task-123'
    args,kw=request.call_args
    assert args==('POST','https://pixstag.com/api/v2/video_generation')
    assert kw['headers']['Authorization']=='Bearer test-secret' and kw['allow_redirects'] is False
    request.side_effect=requests.Timeout('test-secret')
    with pytest.raises(RuntimeError) as exc:client.submit({})
    assert 'test-secret' not in str(exc.value) and request.call_count==2
    client.close()


def test_errors_and_account_fields_do_not_expose_secret(monkeypatch):
    client=Pixstag('test-secret')
    request=Mock(return_value=response({'error':'test-secret https://cdn.example/file?token=private'},401))
    monkeypatch.setattr(client.session,'request',request)
    with pytest.raises(RuntimeError) as exc:client.account()
    assert 'test-secret' not in str(exc.value) and 'token=private' not in str(exc.value)
    request.return_value=response({'data':{'credit':42,'status':1,'token':'should-not-escape'}})
    assert client.account()=={'credit':42,'status':1}
    client.close()


def fake_client():
    client=Pixstag('test-secret')
    client.submit=Mock(return_value='remote-123')
    client.query=Mock(return_value={'status':'succeeded','content':{'url':'https://cdn.example/signed?token=not-a-log'}})
    def download(url,target):
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(b'\x00\x00\x00\x18ftypmp42-contract-fixture')
        return target
    client.download=Mock(side_effect=download)
    return client


def test_submission_progress_and_recoverable_local_download(project):
    client=fake_client();states=[];j=job()
    client.query.side_effect=[{'status':'queued'},{'status':'running'}, {'status':'succeeded','duration':5,'content':{'url':'https://cdn.example/video'}}]
    outputs=execute(client,project,j,states.append,poll_seconds=0)
    assert states==['submitting','queued','queued','running','downloading','completed']
    assert j['prompt_id']=='remote-123' and j['progress'] is None
    assert outputs==['outputs/test-contract-job/pixstag-video.mp4']
    assert project.file(outputs[0]).exists() and client.submit.call_count==1
    journal=project.file('jobs/'+j['id']+'.json').read_text(encoding='utf-8')
    assert 'test-secret' not in journal and 'https://' not in journal and 'base64' not in journal
    restored=json.loads(journal);client=fake_client()
    assert execute(client,project,restored,poll_seconds=0)==outputs
    client.submit.assert_not_called();client.download.assert_not_called()


def test_post_timeout_is_unknown_and_does_not_retry(project):
    client=fake_client();client.submit.side_effect=RuntimeError('network timeout')
    j=job()
    with pytest.raises(RuntimeError):execute(client,project,j,poll_seconds=0)
    assert j['status']=='unknown' and not j.get('prompt_id')
    client.submit.assert_called_once();client.query.assert_not_called()


def test_query_failure_retains_id_and_resume_never_resubmits(project):
    client=fake_client();client.query.side_effect=RuntimeError('connection failed')
    j=job(prompt_id='existing-task')
    with pytest.raises(RuntimeError):execute(client,project,j,poll_seconds=0)
    assert j['status']=='detached' and j['prompt_id']=='existing-task'
    assert client.query.call_count==3;client.submit.assert_not_called()
    recovered=copy.deepcopy(j);client=fake_client()
    assert execute(client,project,recovered,poll_seconds=0)
    client.submit.assert_not_called()


@pytest.mark.parametrize('remote,expected',[('failed','failed'),('cancelled','cancelled')])
def test_remote_terminal_statuses(project,remote,expected):
    client=fake_client();client.query.return_value={'status':remote,'error':{'code':'NOT_SUPPORTED','message':'test-secret'}}
    j=job(prompt_id='existing-task')
    if remote=='failed':
        with pytest.raises(RuntimeError):execute(client,project,j,poll_seconds=0)
    else:assert execute(client,project,j,poll_seconds=0)==[]
    assert j['status']==expected and 'test-secret' not in j.get('error','')


def test_stopping_detaches_without_remote_cancel(project):
    client=fake_client();j=job(prompt_id='existing-task')
    assert execute(client,project,j,stopping=lambda:True)==[]
    assert j['status']=='detached';client.submit.assert_not_called();client.query.assert_not_called()


@pytest.mark.parametrize('url',['http://cdn.example/v.mp4','https://localhost/v.mp4','https://127.0.0.1/v.mp4','https://u:p@cdn.example/v.mp4'])
def test_download_rejects_local_or_unsafe_destinations(monkeypatch,url):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('127.0.0.1',443))])
    with pytest.raises(ValueError):Pixstag.check_download_url(url)


def test_download_does_not_forward_bearer_and_validates_mp4(project,monkeypatch):
    client=Pixstag('test-secret')
    monkeypatch.setattr(client,'check_download_url',lambda _:None)
    class Download:
        status_code=200
        headers={'Content-Type':'video/mp4'}
        def __enter__(self):return self
        def __exit__(self,*_):pass
        def raise_for_status(self):pass
        def iter_content(self,*_):yield b'\x00\x00\x00\x18ftypmp42'+b'fixture'
    get=Mock(return_value=Download());monkeypatch.setattr(client.download_session,'get',get)
    target=project.file('outputs/test.mp4')
    assert client.download('https://cdn.example/v',target)==target
    assert 'headers' not in get.call_args.kwargs and not client.download_session.headers.get('Authorization')
    assert not target.with_name('test.mp4.part').exists()
    client.close()
