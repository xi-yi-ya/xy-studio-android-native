import copy,json
import pytest
from studio.deepseek import chat,SYSTEM
from studio.skill_library import read_skill
from studio.research import web_search

def call(name,args,id='c'):
    return {'id':id,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}

def mock_chat(monkeypatch,answers):
    payloads=[];it=iter(answers)
    class Response:
        ok=True
        def __init__(self,msg):self.msg=msg
        def json(self):return {'choices':[{'message':self.msg}]}
    def post(*a,**kw):payloads.append(copy.deepcopy(kw['json']));return Response(next(it))
    monkeypatch.setattr('studio.deepseek.requests.post',post)
    return payloads

def test_normal_chat_has_catalog_not_skill_bodies(monkeypatch):
    payloads=mock_chat(monkeypatch,[{'role':'assistant','content':'你好'}])
    msg=chat('test','deepseek-flash',[],{})
    assert msg['_activity']==[]
    assert 'references/base-en.txt' in SYSTEM
    assert 'The camera pans right with large amplitude' not in SYSTEM
    assert not any(t['function']['name']=='web_search' for t in payloads[0]['tools'])

def test_read_skill_roundtrip_and_no_eager_h3(monkeypatch):
    payloads=mock_chat(monkeypatch,[{'role':'assistant','tool_calls':[call('read_skill',{'skill':'qwen','file':'references/edit-guide.md'})]}, {'role':'assistant','content':'将杯子改成红色。'}])
    result=chat('test','deepseek-flash',[],{})
    assert result['_activity'][0]['skill']=='qwen'
    assert '修改原图' in payloads[1]['messages'][-1]['content']
    assert 'retention_analysis' not in payloads[1]['messages'][-1]['content']
    with pytest.raises(ValueError):read_skill('qwen','../../project.json')

def test_search_then_mutation_requires_new_review_round(monkeypatch):
    source={'query':'official docs','summary':'data','sources':[{'title':'Official','url':'https://example.com'}],'warnings':[]}
    monkeypatch.setattr('studio.deepseek.web_search',lambda *a:source)
    payloads=mock_chat(monkeypatch,[{'role':'assistant','tool_calls':[call('web_search',{'query':'official docs'}),call('set_story',{'text':'尚未采用'},'c2')]},{'role':'assistant','content':'查到了资料。','tool_calls':[call('set_story',{'text':'可审阅的故事'},'c3')]}])
    result=chat('test','deepseek-flash',[],{},online=True)
    assert result['tool_calls'][0]['id']=='c3'
    assert '尚未执行' in payloads[1]['messages'][-1]['content']
    assert result['_activity'][0]['sources']==source['sources']

def test_web_requires_real_sources(monkeypatch):
    class Response:
        ok=True
        def json(self):return {'content':[{'type':'text','text':'I searched (but no evidence).'}]}
    monkeypatch.setattr('studio.research.requests.post',lambda *a,**kw:Response())
    with pytest.raises(RuntimeError,match='来源'):web_search('test','deepseek-flash','query')

def test_disabled_search_cannot_execute_even_if_model_requests_it(monkeypatch):
    def forbidden(*a):raise AssertionError('Network search must not run')
    monkeypatch.setattr('studio.deepseek.web_search',forbidden)
    payloads=mock_chat(monkeypatch,[{'role':'assistant','tool_calls':[call('web_search',{'query':'q'})]},{'role':'assistant','content':'请开启联网。'}])
    result=chat('test','deepseek-flash',[],{},online=False)
    assert result['_activity'][0]['type']=='error'
    assert '联网已关闭' in payloads[1]['messages'][-1]['content']


def test_three_view_request_repairs_wrong_asset_creation_before_review(monkeypatch):
    wrong={'role':'assistant','content':'','tool_calls':[call('add_item',{'kind':'characters','name':'洛天依','description':'角色三视图'},'bad-role'),call('add_item',{'kind':'scenes','name':'背景','description':'白色'},'bad-scene')]}
    correct={'role':'assistant','content':'请确认三视图生成参数','tool_calls':[call('generate',{'mode':'qwen','prompt':'Luo Tianyi three views on white background','references':[]},'image')]}
    payloads=mock_chat(monkeypatch,[wrong,correct,correct])
    history=[{'role':'user','content':'帮我生成一个洛天依三视图'}]
    result=chat('test','deepseek-flash',history,{},asset_query=lambda **kw:{'items':[]})
    assert result['tool_calls'][0]['function']['name']=='generate'
    assert len(payloads)==3 # Incorrect action repaired, then required guide loaded.
    replies=[m for m in payloads[1]['messages'] if m.get('role')=='tool']
    assert [m['tool_call_id'] for m in replies]==['bad-role','bad-scene']
    assert all('尚未执行' in m['content'] for m in replies)
    assert history==[{'role':'user','content':'帮我生成一个洛天依三视图'}]


def test_invalid_asset_path_has_bounded_repair_and_never_returns_mutation(monkeypatch):
    wrong={'role':'assistant','tool_calls':[call('add_item',{'kind':'characters','name':'洛天依','description':'','file':'imaginary.png'})]}
    payloads=mock_chat(monkeypatch,[wrong,wrong,wrong])
    with pytest.raises(ValueError,match='未修改项目'):
        chat('test','deepseek-flash',[],{},asset_query=lambda **kw:{'items':[]})
    assert len(payloads)==3


def test_existing_image_adoption_still_reaches_review(monkeypatch):
    suggestion={'role':'assistant','tool_calls':[call('add_item',{'kind':'characters','name':'角色','description':'','file':'assets/real.png'})]}
    mock_chat(monkeypatch,[suggestion])
    result=chat('test','deepseek-flash',[],{},asset_query=lambda **kw:{'items':[{'file':'assets/real.png','exists':True,'error':''}]})
    assert result['tool_calls'][0]['function']['name']=='add_item'
