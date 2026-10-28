import json
from dataclasses import asdict
from pathlib import Path
import pytest
from studio.workflows import Generation,build,frames,resolution,preflight,MODES,STYLES,default_steps
from studio.storage import Project,uid
from studio.comfy import execute,Comfy
from studio.deepseek import validate_action,chat

def test_h3_frame_alignment_and_short_test():
    for sec in (.2,1,2,5,15,60,149):
        n=frames(sec);assert n%17==5;assert n>=round(sec*24);assert n-round(sec*24)<17
    assert frames(2)==56
    assert resolution('16:9',.2)==(608,352)

@pytest.mark.parametrize('mode',[m for m in MODES if not m.startswith('pixstag_')])
def test_graphs_closed_and_output(mode):
    n={'qwen_edit':1,'quad':1,'h3_i2v':1,'h3_ref':2,'h3_fl2v':2,'upscale':1}.get(mode,0)
    g=Generation(mode=mode,prompt='test',references=['a']*n)
    graph=build(g,['uploaded.png']*n)
    for node in graph.values():
        for x in node['inputs'].values():
            if isinstance(x,list):assert x[0] in graph
    assert graph['output']['class_type']==('SaveVideo' if mode.startswith('h3') else 'SaveImageAdvanced' if mode.startswith('qwen') else 'SaveImage')


def test_qwen_t2i_matches_approved_precision_sampling_and_export():
    graph=build(Generation(prompt='测试',megapixels=6.6),[])
    assert graph['model']['inputs']['unet_name']=='qwen_image_2.1_bf16.safetensors'
    assert graph['clip']['inputs']['clip_name']=='qwen3vl_8b_bf16.safetensors'
    assert graph['vae']['inputs']['vae_name']=='qwen_image_2.1_vae_bf16.safetensors'
    sample=graph['sample']['inputs']
    assert (sample['steps'],sample['cfg'],sample['sampler_name'],sample['scheduler'],sample['denoise'])==(40,1,'euler','simple',1)
    assert graph['encode']['inputs']['resolution']==1024
    assert (graph['latent']['inputs']['width'],graph['latent']['inputs']['height'])==resolution('16:9',6.6,8)
    assert graph['output']['inputs']['format.bit_depth']=='16-bit'


@pytest.mark.parametrize('mode',[m for m in MODES if not m.startswith('pixstag_')])
def test_zero_steps_still_uses_workflow_default_in_legacy_jobs(mode):
    refs=['a']*({'qwen_edit':1,'quad':1,'h3_i2v':1,'h3_ref':1,'h3_fl2v':2,'upscale':1}.get(mode,0))
    g=Generation(mode=mode,prompt='test',references=refs,seed=100,steps=0)
    graph=build(g,refs)
    sampler=graph['sigmas' if mode.startswith('h3') else 'up' if mode=='upscale' else 'sample']['inputs']
    assert sampler['steps']==default_steps(mode)


@pytest.mark.parametrize('steps',[True,1.5,'40',-1,101])
def test_invalid_sampling_steps_rejected_before_comfy_submission(steps):
    with pytest.raises(ValueError,match='整数'):
        Generation(prompt='test',steps=steps).validate()

def test_lora_disable_rewires_both_h3_consumers():
    g=Generation(mode='h3_i2v',prompt='test',references=['x'],cinema=True)
    on=build(g,['x']);assert on['guide']['inputs']['model']==['cinema',0];assert on['sigmas']['inputs']['model']==['cinema',0]
    g.cinema=False;off=build(g,['x']);assert 'cinema' not in off
    assert off['guide']['inputs']['model']==off['sigmas']['inputs']['model']==['model',0]

def test_style_switches_and_quad():
    g=Generation(mode='krea',prompt='test',styles=list(STYLES))
    assert len([n for n in build(g,[]).values() if n['class_type']=='LoraLoaderModelOnly'])==9
    g.styles=[];assert not any(n['class_type']=='LoraLoaderModelOnly' for n in build(g,[]).values())
    g=Generation(mode='quad',prompt='test',references=['x'],quad_lora=False)
    assert build(g,['x'])['patch']['inputs']['model']==['model',0]

def test_edit_geometry_and_reference_order():
    g=Generation(mode='qwen_edit',prompt='change hat',references=['a','b'])
    graph=build(g,['uploaded-a','uploaded-b'])
    assert graph['encode']['inputs']['images.image_1']==['ref0',0]
    assert graph['encode']['inputs']['images.image_2']==['ref1',0]
    assert graph['sample']['inputs']['latent_image']==['encode',2]
    assert 'resize' not in graph and 'latent' not in graph
    assert graph['sample']['inputs']['model']==['qwen_cache',0]
    g.edit_follow_source=False
    custom=build(g,['uploaded-a','uploaded-b'])
    assert custom['sample']['inputs']['latent_image']==['latent',0]
    assert custom['encode']['inputs']['images.image_1']==['ref0',0]

def test_project_roundtrip_versions_and_path_safety(tmp_path):
    p=Project(tmp_path/'p',True);a=p.add('characters','robot');s=p.add('shots','01');s['materials']=[a['id']];p.save()
    with pytest.raises(ValueError):p.delete(a['id'])
    with pytest.raises(ValueError):p.file('../outside')
    j={'id':'job','target':s['id'],'generation':asdict(Generation(prompt='test'))}
    p.attach_output(j,'outputs/a.png');p.attach_output(j,'outputs/a.png')
    again=Project(p.root);assert len(again.get(s['id'])['versions'])==1

def test_missing_refs_and_models():
    with pytest.raises(ValueError):Generation(mode='h3_i2v',prompt='x').validate()
    with pytest.raises(ValueError):preflight(build(Generation(prompt='x'),[]),{})

def test_ai_bounded_tools_and_no_key():
    assert validate_action('set_story',{'text':'hello'})['text']=='hello'
    for name,args in [('delete_file',{}),('set_story',{'text':9}),('set_story',{'text':'x','command':'rm'}),('add_item',{'kind':'bad','name':'x','description':'x'})]:
        with pytest.raises(ValueError):validate_action(name,args)
    with pytest.raises(ValueError):chat('','model',[],{})


def test_read_only_asset_tools_are_available_offline_and_do_not_become_project_actions(monkeypatch):
    requests=[];queries=[]
    class Response:
        ok=True
        def json(self):
            if len(requests)==1:
                return {'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[{'id':str(i),'function':{'name':name,'arguments':'{"source":"generated","offset":0,"limit":20}'}} for i,name in enumerate(('query_image_assets','query_video_assets'))]}}]}
            return {'choices':[{'message':{'role':'assistant','content':'查询已完成。'}}]}
    def post(url,**kwargs):requests.append(kwargs['json'].copy());return Response()
    def query(**args):queries.append(args);return {'total':2,'items':[{'file':'outputs/a.png'}]}
    monkeypatch.setattr('studio.deepseek.requests.post',post)
    message=chat('test-only','test-model',[],{},asset_query=query)
    names={t['function']['name'] for t in requests[0]['tools']}
    assert {'query_image_assets','query_video_assets'}<=names and 'web_search' not in names
    assert [q['kind'] for q in queries]==['image','video']
    assert len(message['_activity'])==2 and not message.get('tool_calls')
    with pytest.raises(ValueError):validate_action('query_image_assets',{'limit':True})

class Fake:
    def __init__(self,root):self.submits=0;self.root=root
    def history(self,pid):return {'status':{'completed':True},'outputs':{}}
    def download(self,h,d):
        d.mkdir(parents=True,exist_ok=True);f=d/'x.png';f.write_bytes(b'png');return [f]

def test_resume_never_resubmits(tmp_path):
    p=Project(tmp_path/'p',True);f=Fake(p.root)
    j={'id':uid(),'prompt_id':'existing','generation':asdict(Generation(prompt='x')),'status':'running'}
    assert execute(f,p,j);assert f.submits==0;assert j['status']=='completed'

def test_cancel_only_selected_prompt(monkeypatch):
    c=Comfy();calls=[]
    monkeypatch.setattr(c,'queue',lambda:{'queue_running':[[0,'other']], 'queue_pending':[[1,'ours']]})
    monkeypatch.setattr(c,'call',lambda *a,**k:calls.append((a,k)))
    c.cancel('ours');assert calls==[(('POST','/queue'),{'json':{'delete':['ours']}})]

def test_deepseek_mocked_request_contract(monkeypatch):
    calls=[]
    class Response:
        ok=True
        def json(self):return {'choices':[{'message':{'role':'assistant','content':'计划','tool_calls':[{'id':'c1','type':'function','function':{'name':'set_story','arguments':'{"text":"故事"}'}}]}}]}
    def post(url,**kw):calls.append((url,kw));return Response()
    monkeypatch.setattr('studio.deepseek.requests.post',post)
    msg=chat('test-only-key','test-model',[{'role':'user','content':'写故事'}],{'story':''})
    assert msg['tool_calls'][0]['id']=='c1'
    assert calls[0][0]=='https://api.deepseek.com/chat/completions'
    assert calls[0][1]['json']['tools'] and calls[0][1]['json']['thinking']=={'type':'disabled'}


def test_guide_loading_retry_keeps_existing_generation_on_review_tool_path(monkeypatch):
    import copy
    requests=[]
    class Response:
        ok=True
        def json(self):return {'choices':[{'message':{'role':'assistant','content':'请确认修改内容。','tool_calls':[{'id':'edit','function':{'name':'generate','arguments':json.dumps({'target':'existing','mode':'qwen_edit','prompt':'将机器人改为黄色，保留构图。','references':['assets/robot.png']})}}]}}]}
    def post(*a,**kw):requests.append(copy.deepcopy(kw['json']));return Response()
    monkeypatch.setattr('studio.deepseek.requests.post',post)
    result=chat('test-only','test-model',[{'role':'user','content':'请改图'}],{})
    assert result['tool_calls'][0]['function']['name']=='generate'
    assert len(requests)==2 and 'tool_choice' not in requests[0]
    assert requests[1]['tool_choice']=='required'
    assert requests[1]['thinking']=={'type':'disabled'}

def test_cancelled_job_not_registered_as_success(tmp_path):
    p=Project(tmp_path/'p',True)
    class Interrupted:
        def history(self,pid):return {'status':{'status_str':'error','messages':[['execution_interrupted',{}]]}}
    j={'id':uid(),'prompt_id':'p','status':'running'}
    assert execute(Interrupted(),p,j)==[];assert j['status']=='cancelled'

def test_asset_change_marks_only_referencing_shots(tmp_path):
    p=Project(tmp_path/'p',True);a=p.add('characters','a');s=p.add('shots','1');other=p.add('shots','2');s['materials']=[a['id']]
    p.mark_dependents(a['id']);assert s['needs_review'];assert not other.get('needs_review')

def test_video_max_length_is_legal():
    assert frames(149)<=3600
    with pytest.raises(ValueError):frames(150)

def test_h3_prompt_repair_is_bounded(monkeypatch):
    import copy,json
    calls=[]
    complete='integrated_multimodal_description: [Shot 1] robot waves\noverall_soundscape: quiet room\nnon_diegetic_music: N/A'
    args={'target':'shot','mode':'h3_i2v','prompt':'incomplete','references':['image.png']}
    class Response:
        ok=True
        def json(self):
            args['prompt']=complete if len(calls)==2 else 'incomplete'
            return {'choices':[{'message':{'role':'assistant','tool_calls':[{'id':'t','function':{'name':'generate','arguments':json.dumps(args)}}]}}]}
    def post(*a,**kw):calls.append(copy.deepcopy(kw['json']));return Response()
    monkeypatch.setattr('studio.deepseek.requests.post',post)
    assert chat('test','model',[],{})['tool_calls']
    assert len(calls)==2 and '未通过' in calls[1]['messages'][-1]['content']

def test_h3_reference_prompt_uses_six_sections():
    from studio.deepseek import validate_prompt
    args={'mode':'h3_ref','prompt':'integrated_multimodal_description: x\noverall_soundscape: y\nnon_diegetic_music: N/A'}
    with pytest.raises(ValueError):validate_prompt(args)
    args['prompt']='subject_definitions: x\nsummary: x\nretention_analysis: x\ndetailed_description: x\noverall_soundscape: x\nnon_diegetic_music: N/A'
    validate_prompt(args)

def test_progress_events_ignore_other_prompts():
    import json,websocket
    c=Comfy()
    class Socket:
        def __init__(self):self.events=iter([json.dumps({'type':'progress','data':{'prompt_id':'other','value':9,'max':10}}),json.dumps({'type':'progress','data':{'prompt_id':'ours','node':'sample','value':2,'max':8}})])
        def recv(self):
            try:return next(self.events)
            except StopIteration:raise websocket.WebSocketTimeoutException()
    c.ws=Socket();events=c.progress_events('ours')
    assert len(events)==1 and events[0]['data']['value']==2


def test_progress_state_uses_only_running_nodes_of_our_prompt():
    import websocket
    c=Comfy()
    class Socket:
        def __init__(self):self.events=iter([
            json.dumps({'type':'progress_state','data':{'prompt_id':'other','nodes':{'sample':{'state':'running','value':9,'max':10}}}}),
            json.dumps({'type':'progress_state','data':{'prompt_id':'ours','nodes':{
                'old':{'state':'finished','value':8,'max':8},
                'sample':{'state':'running','value':3,'max':8},
                'decode':{'state':'pending','value':0,'max':1}}}}),
            json.dumps({'type':'progress_state','data':{'prompt_id':'ours','nodes':{'decode':{'state':'running','value':0,'max':0}}}})])
        def recv(self):
            try:return next(self.events)
            except StopIteration:raise websocket.WebSocketTimeoutException()
    c.ws=Socket();events=c.progress_events('ours')
    assert events==[
        {'type':'progress','data':{'prompt_id':'ours','node':'sample','value':3,'max':8}},
        {'type':'executing','data':{'prompt_id':'ours','node':'decode'}}]


def test_empty_success_response_from_comfy_cancel_is_accepted(monkeypatch):
    c=Comfy()
    class Response:
        ok=True
        content=b''
        def json(self):raise AssertionError('Empty responses are not JSON')
    monkeypatch.setattr(c.session,'request',lambda *a,**kw:Response())
    assert c.call('POST','/queue',json={'delete':['ours']})=={}

def test_real_step_progress_does_not_complete_before_output(tmp_path):
    p=Project(tmp_path/'p',True);states=[]
    class ProgressFake(Fake):
        def progress_events(self,pid):return [{'type':'progress','data':{'node':'sample','value':8,'max':8}}]
    j={'id':uid(),'prompt_id':'existing','generation':asdict(Generation(prompt='x')),'status':'running'}
    execute(ProgressFake(p.root),p,j,lambda state:states.append((state,j.get('progress'))))
    assert states[0]==('running',{'value':8,'max':8})
    assert states[1][0]=='downloading' and states[-1][0]=='completed'
