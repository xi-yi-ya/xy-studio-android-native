import copy,json
import pytest
from PySide6.QtWidgets import QDialog,QMessageBox
from studio.ui import Studio,GenerationDialog
from studio.storage import Project
from studio.action_targets import resolve_target

@pytest.mark.parametrize('kind,mode',[('characters','qwen'),('scenes','qwen'),('shots','qwen'),('shots','h3_t2v')])
def test_ai_create_then_manual_generation_preserves_owner(tmp_path,monkeypatch,kind,mode):
    from test_gui_state import app
    p=Project(tmp_path/'p',True);old=p.add(kind,'测试条目')
    w=Studio(p.root)
    monkeypatch.setattr(QMessageBox,'exec',lambda self:QMessageBox.Apply)
    monkeypatch.setattr(GenerationDialog,'exec',lambda self:QDialog.Accepted)
    monkeypatch.setattr(w,'start_next',lambda:None)
    def call(i,name,args):return {'id':i,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}
    w.chat_result({'role':'assistant','content':'创建并生成','tool_calls':[
        call('create','add_item',{'kind':kind,'name':'新条目','description':'新描述'}),
        call('gen','generate',{'target':'@新条目','mode':mode,'prompt':'AI prompt','references':[]})]})
    item=w.project.data[kind][-1];first=w.project.data['jobs'][0]
    assert first['target']==item['id']!=old['id']
    w.generate(item,mode);second=w.project.data['jobs'][1]
    # Deliver first result after the manual second request and a GUI rebuild.
    w.refresh()
    for job in [first,second]:
        snapshot=copy.deepcopy(job);snapshot['status']='completed'
        w.job_result(job,snapshot,['outputs/'+job['id']+'/result.png'])
    assert w.project.get(old['id'])['versions']==[]
    assert [v['job'] for v in item['versions']]==[first['id'],second['id']]
    reopened=Project(p.root)
    assert len(reopened.get(item['id'])['versions'])==2
    assert reopened.get(old['id'])['image']==''
    w.close()

def test_wrong_existing_target_in_creation_batch_is_blocked():
    calls=[{'function':{'name':'add_item'}}]
    with pytest.raises(ValueError,match='不能猜测'):
        resolve_target('generate',{'target':'old'},calls,{'create':'new'})
    with pytest.raises(ValueError,match='尚未成功'):
        resolve_target('generate',{'target':'@cancelled'},calls,{})
    assert resolve_target('generate',{'target':'old'},[],{})['target']=='old'


def test_missing_material_alias_fails_cleanly():
    with pytest.raises(ValueError,match='关联素材'):
        resolve_target('update_item',{'id':'@shot','materials':['@missing']},[],{'shot':'new-shot'})
@pytest.mark.parametrize('cancel_create',[False,True])
def test_bad_or_cancelled_ai_batch_never_queues(tmp_path,monkeypatch,cancel_create):
    from test_gui_state import app
    import studio.ui as ui
    p=Project(tmp_path/'p',True);old=p.add('characters','测试角色1');w=Studio(p.root)
    monkeypatch.setattr(QMessageBox,'exec',lambda self:QMessageBox.Cancel if cancel_create else QMessageBox.Apply)
    monkeypatch.setattr(ui,'message',lambda *args:None)
    monkeypatch.setattr(w,'generate',lambda *args:pytest.fail('Wrong target reached generation'))
    def call(i,name,args):return {'id':i,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}
    w.chat_result({'role':'assistant','content':'','tool_calls':[
      call('create','add_item',{'kind':'characters','name':'新角色','description':''}),
      call('generate','generate',{'target':'@新角色' if cancel_create else old['id'],'mode':'qwen','prompt':'x','references':[]})]})
    assert not w.project.data['jobs']
    assert '操作未执行' in w.project.data['chat'][-1]['content']
    w.close()
