import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from studio.ui import GenerationDialog
from studio.storage import Project
from studio.workflows import Generation
from studio.ui import Studio
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QDialog,QGroupBox,QHBoxLayout
import pytest

app=QApplication.instance() or QApplication([])

def test_video_controls_match_actual_graph(tmp_path):
    p=Project(tmp_path/'p',True)
    d=GenerationDialog(p,Generation(mode='h3_i2v',megapixels=.2,seconds=2))
    assert '608 × 352' in d.summary.text() and '56 帧' in d.summary.text()
    assert d.cinema.isEnabled() and not d.quad.isEnabled() and not d.scale.isEnabled()
    d.deleteLater()

def test_visible_history_and_delete_on_all_cards(tmp_path):
    p=Project(tmp_path/'cards',True)
    for kind in ('characters','scenes','shots'):p.add(kind,kind)
    window=Studio(p.root)
    labels=[b.text() for b in window.findChildren(QPushButton)]
    assert labels.count('生成历史')==3
    assert {'删除角色','删除场景','删除分镜'}<=set(labels)
    window.close()

def test_qwen_geometry_and_upscale_controls(tmp_path):
    p=Project(tmp_path/'p',True)
    d=GenerationDialog(p,Generation(mode='qwen',megapixels=.2))
    assert '608 × 352' in d.summary.text()
    assert not d.seconds.isEnabled() and d.int8.isEnabled()
    d.mode.setCurrentIndex(d.mode.findData('upscale'))
    assert d.scale.isEnabled() and not d.mp.isEnabled()
    d.deleteLater()

def test_media_entrypoints_and_irrelevant_controls(tmp_path):
    p=Project(tmp_path/'p',True)
    video=GenerationDialog(p,Generation(mode='h3_i2v'))
    assert all(video.mode.itemData(i).startswith('h3') for i in range(video.mode.count()))
    assert video.scale.isHidden() and video.quad.isHidden() and video.int8.isHidden()
    image=GenerationDialog(p,Generation(mode='qwen'))
    assert all(not image.mode.itemData(i).startswith('h3') for i in range(image.mode.count()))
    assert image.mode.findData('upscale')>=0
    assert image.seconds.isHidden() and 'H3' not in image.summary.text()
    video.deleteLater();image.deleteLater()

def test_new_shots_without_dialog_and_stable_ids(tmp_path,monkeypatch):
    p=Project(tmp_path/'p',True);w=Studio(p.root)
    def forbidden(*args):raise AssertionError('Unexpected pre-input dialog')
    monkeypatch.setattr(QDialog,'exec',forbidden)
    w.edit_item('shots');w.edit_item('shots');w.edit_item('shots')
    shots=w.project.data['shots'];last_id=shots[-1]['id']
    assert [s['name'] for s in shots]==['分镜 1','分镜 2','分镜 3']
    w.project.delete(shots[1]['id'])
    again=Project(p.root)
    assert [s['name'] for s in again.data['shots']]==['分镜 1','分镜 2']
    assert again.data['shots'][1]['id']==last_id
    w.close()

def test_all_cards_are_full_rows_and_invalid_ai_links_rejected(tmp_path):
    p=Project(tmp_path/'p',True)
    actor=p.add('characters','角色');scene=p.add('scenes','场景');shot=p.add('shots','旧名称')
    w=Studio(p.root)
    for kind in ('characters','scenes','shots'):
        card=w.card(kind,w.project.data[kind][0])
        assert isinstance(card.layout(),QHBoxLayout)
        card.deleteLater()
    with pytest.raises(ValueError):w.apply_action('update_item',{'id':shot['id'],'description':'x','materials':[shot['id']]})
    with pytest.raises(ValueError):w.generate(actor,'h3_i2v')
    assert w.project.get(shot['id'])['description']==''
    w.close()

def test_reference_order_and_text_only_mode_does_not_submit_hidden_refs(tmp_path):
    p=Project(tmp_path/'p',True)
    d=GenerationDialog(p,Generation(mode='qwen_edit',prompt='test',references=['first','last']))
    d.refs.setCurrentRow(1);d.move_ref(-1)
    assert [d.refs.item(i).text() for i in range(2)]==['last','first']
    d.mode.setCurrentIndex(d.mode.findData('qwen'))
    d.accept_valid()
    assert d.result()==QDialog.Accepted and d.g.references==[]
    d.deleteLater()

def test_prompt_roundtrip_and_workflow_switch(tmp_path):
    p=Project(tmp_path/'p',True);a=p.add('characters','a')
    p.data['jobs'].append({'id':'j','target':a['id'],'generation':{'mode':'qwen','prompt':'旧项目最后提示词'},'status':'completed'})
    a['last_prompts']={'qwen_edit':'只修改衣服'};p.save();p=Project(p.root)
    assert p.last_prompt(a['id'],'qwen')=='旧项目最后提示词'
    d=GenerationDialog(p,Generation(mode='qwen',prompt=p.last_prompt(a['id'],'qwen')),target=a['id'])
    d.prompt.setPlainText('本次草稿');d.mode.setCurrentIndex(d.mode.findData('qwen_edit'))
    assert d.prompt.toPlainText()=='只修改衣服'
    d.mode.setCurrentIndex(d.mode.findData('qwen'));assert d.prompt.toPlainText()=='本次草稿'
    d.deleteLater()

def test_fixed_thumbnail_and_task_management(tmp_path):
    from studio.ui import TaskDialog
    from dataclasses import asdict
    p=Project(tmp_path/'p',True);a=p.add('characters','a')
    p.data['jobs']=[{'id':'j','target':a['id'],'generation':asdict(Generation(prompt='saved')),'status':'new'}];p.save()
    w=Studio(p.root);thumb=w.thumbnail('','empty')
    assert thumb.minimumWidth()==thumb.maximumWidth()==240
    assert thumb.minimumHeight()==thumb.maximumHeight()==240
    d=TaskDialog(w);assert d.table.rowCount()==1
    d.cancel();assert w.project.data['jobs'][0]['status']=='cancelled'
    d.filter.setCurrentIndex(4);assert d.table.rowCount()==1
    d.pause();assert Project(p.root).data['queue_paused']
    d.close();thumb.deleteLater();w.close()

def test_agent_controls_and_safe_source_links(tmp_path):
    p=Project(tmp_path/'p',True)
    p.data['chat']=[{'role':'assistant','content':'结果','_activity':[{'type':'search','query':'test','sources':[{'title':'来源 [一] <script>','url':'https://example.com/docs?q=1&x=2'},{'title':'不可打开','url':'file:///C:/private'}]}]}];p.save()
    w=Studio(p.root)
    assert w.model_picker.findText('deepseek-flash')>=0
    text=w.transcript.toPlainText()
    assert '来源 [一] <script>' in text and '不可打开' not in text
    assert 'href="https://example.com/docs?q=1&amp;x=2"' in w.transcript.toHtml()
    w.close()
