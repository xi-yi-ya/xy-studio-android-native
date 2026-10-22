import copy,json,time
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog,QPushButton,QDialog,QLineEdit,QPlainTextEdit
from PySide6.QtTest import QTest
from test_gui_state import app
from studio.ui import Studio
from studio.storage import Project,atomic_json
from studio.workspace import AssetGrid,WorkspaceCard
from studio.workflows import frames


def project(tmp_path):
    p=Project(tmp_path/'p',True)
    for kind in ('characters','scenes','shots'):
        for n in range(3):p.add(kind,f'{kind} {n}','长描述，角色关系与空间方向。'*20)
    p.data['shots'][0]['materials']=[p.data['characters'][0]['id'],p.data['scenes'][0]['id']];p.save();return p


def test_project_open_new_save_preserves_existing_ids_and_versions(tmp_path,monkeypatch):
    p=project(tmp_path);before=copy.deepcopy(p.data)
    w=Studio();monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a:(str(p.path),''));w.open_project();w.save()
    after=Project(p.root)
    for kind in ('characters','scenes','shots','jobs','chat'):assert after.data[kind]==before[kind]
    fresh=tmp_path/'new';monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *a:str(fresh));w.new_project()
    assert w.project.root==fresh and w.project.data['schema']==1
    w.close()


def test_timeline_selection_collapse_and_versions_stay_in_card(tmp_path):
    p=project(tmp_path);w=Studio(p.root);w.show();w.navigation.setCurrentRow(3);app.processEvents()
    shot=w.project.data['shots'][1];ident=shot['id']
    w.timeline.buttons[ident].click();assert w.selected_id==ident and w.card_widgets[ident].property('selected')
    assert shot['name'] in w.context_label.text()
    card=w.card_widgets[ident];card.fold.click();assert ident in w.collapsed_shots and card.body.isHidden()
    job={'id':'v1','target':ident,'generation':{'mode':'qwen','prompt':'new picture'},'status':'completed','outputs':['outputs/fake.png']}
    w.project.data['jobs'].append(job);w.project.attach_output(job,'outputs/fake.png');w.refresh();app.processEvents()
    assert len(w.project.data['shots'])==3 and len(w.project.get(ident)['versions'])==1
    assert w.card_widgets[ident].body.isHidden() and w.timeline.buttons[ident].isChecked()
    assert w.card_widgets[ident].state.text()=='已完成'
    w.clear_context();assert w.selected_id is None and not w.timeline.buttons[ident].isChecked()
    w.close()


def test_selected_asset_is_passed_to_agent_and_dock_toggle_keeps_it(tmp_path,monkeypatch):
    import studio.ui as ui
    p=project(tmp_path);w=Studio(p.root);captured=[]
    monkeypatch.setattr(ui.keyring,'get_password',lambda *a:'test')
    def chat(*args,**kwargs):captured.append(args[3]);return {'role':'assistant','content':'已收到上下文'}
    monkeypatch.setattr(ui,'chat',chat)
    ident=w.project.data['characters'][1]['id'];w.card_widgets[ident].title.click();w.toggle_chat();w.toggle_chat()
    w.input.setPlainText('帮我修改这个角色的描述');w.send_chat()
    for _ in range(100):
        QTest.qWait(10)
        if w.chat_worker is None:break
    assert captured[0]['selected_ids']==[ident]
    assert len(w.project.data['characters'])==3
    w.close()


def test_tasks_page_restores_journal_and_keeps_history_on_target(tmp_path):
    p=project(tmp_path);ident=p.data['shots'][0]['id'];j={'id':'job','target':ident,'generation':{'mode':'h3_t2v','prompt':'x','seconds':2},'status':'running','created':'2026-10-10'};p.data['jobs'].append(j);p.save()
    atomic_json(p.file('jobs/job.json'),dict(j,status='completed',outputs=['outputs/movie.mp4']))
    w=Studio(p.root);assert w.project.get(ident)['video']=='outputs/movie.mp4'
    assert len(w.project.get(ident)['versions'])==1
    w.show_jobs();assert w.workspace_stack.currentIndex()==2 and w.jobs_dialog.table.rowCount()==1
    w.load_project(p.root);assert len(w.project.get(ident)['versions'])==1
    w.close()


def test_shot_name_edit_keeps_number_and_id(tmp_path,monkeypatch):
    p=project(tmp_path);w=Studio(p.root);shot=w.project.data['shots'][0];ident=shot['id']
    def edit(d):
        d.findChild(QLineEdit).setText('抵达便利店');d.findChild(QPlainTextEdit).setPlainText('雨夜停步');return QDialog.Accepted
    monkeypatch.setattr(QDialog,'exec',edit);w.edit_item('shots',shot)
    reopened=Project(p.root).get(ident)
    assert reopened['name']=='分镜 1' and reopened['original_name']=='抵达便利店'
    assert '抵达便利店' in w.card_widgets[ident].title.text();w.close()


def test_many_cards_narrow_window_and_empty_state(tmp_path):
    p=Project(tmp_path/'many',True)
    for n in range(100):p.add('characters','角色'+str(n)+'很长的名称'*30,'没有空格的很长中文描述'*100)
    w=Studio(p.root);w.resize(1000,720);w.show();app.processEvents()
    assert len(w.card_widgets)==100 and w.width()==1000
    grid=w.tabs.widget(0).findChild(AssetGrid);assert grid.columns==1
    for width in (1440,1920):w.resize(width,900);app.processEvents();assert w.width()==width
    assert grid.columns>=2
    assert w.card_widgets[p.data['characters'][0]['id']].title.toolTip()==p.data['characters'][0]['name']
    w.navigation.setCurrentRow(3);app.processEvents();assert not w.timeline.buttons
    w.close()


def test_planned_timeline_duration_is_labelled(tmp_path):
    p=project(tmp_path);shot=p.data['shots'][0]
    p.data['jobs'].append({'id':'j','target':shot['id'],'status':'new','generation':{'mode':'h3_t2v','seconds':2}});p.save()
    w=Studio(p.root);assert w.shot_duration(shot)==f'预计 {frames(2)/24:.2f} 秒';w.close()

def test_no_project_has_guided_empty_state(tmp_path):
    w=Studio();w.show();app.processEvents()
    assert w.workspace_stack.currentIndex()==0
    assert all(not(w.navigation.item(i).flags()&Qt.ItemIsEnabled) for i in range(1,5))
    assert w.navigation.item(5).flags()&Qt.ItemIsEnabled
    p=Project(tmp_path/'empty',True);w.load_project(p.root)
    assert all(w.navigation.item(i).flags()&Qt.ItemIsEnabled for i in range(1,5))
    w.close()

def test_tasks_readable_details_keep_errors_and_raw_record(tmp_path):
    p=project(tmp_path);ident=p.data['characters'][0]['id']
    p.data['jobs'].append({'id':'j','target':ident,'status':'failed','created':'2026-10-10','generation':{'mode':'qwen','prompt':'a rainy shop'},'error':'backend unavailable'});p.save()
    w=Studio(p.root);w.show_jobs();d=w.jobs_dialog
    assert '工作流：Qwen' in d.details.toPlainText() and 'backend unavailable' in d.details.toPlainText()
    d.raw_details.setChecked(True);assert json.loads(d.details.toPlainText())['id']=='j'
    w.close()
