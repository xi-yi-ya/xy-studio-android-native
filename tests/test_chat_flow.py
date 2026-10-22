import json,time
import pytest
from PySide6.QtCore import Qt,QTimer,QEventLoop,QUrl
from PySide6.QtGui import QImage,QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog,QMessageBox,QDialogButtonBox
from test_gui_state import app
import studio.ui as ui
from studio.storage import Project
from studio.chat_view import transcript_html
from studio.image_viewer import ImageViewer


def call(name,args):
    return {'role':'assistant','content':'好的','tool_calls':[{'id':'call-'+name,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}

@pytest.mark.parametrize('cancel',[False,True])
def test_worker_continues_after_real_nested_confirmation(tmp_path,monkeypatch,cancel):
    p=Project(tmp_path/'p',True);w=ui.Studio(p.root);requests=[]
    monkeypatch.setattr(ui.keyring,'get_password',lambda *a:'test')
    monkeypatch.setattr(w,'start_next',lambda:None)
    def fake_chat(key,model,history,context,**kwargs):
        requests.append(history)
        if len(requests)==1:return call('add_item',{'kind':'scenes','name':'雨夜便利店','description':'雨夜'})
        assert history[-1]['role']=='tool'
        target=context['scenes'][0]['id']
        return call('generate',{'target':target,'mode':'qwen','prompt':'rain at night','references':[]})
    monkeypatch.setattr(ui,'chat',fake_chat)
    def confirm(d):
        assert d.button(QMessageBox.Apply).text()=='确认创建条目'
        assert d.button(QMessageBox.Cancel).text()=='取消本次操作'
        loop=QEventLoop();QTimer.singleShot(30,loop.quit);loop.exec()
        return QMessageBox.Cancel if cancel else QMessageBox.Apply
    monkeypatch.setattr(QMessageBox,'exec',confirm)
    monkeypatch.setattr(ui.GenerationDialog,'exec',lambda d:QDialog.Accepted)
    w.input.setPlainText('新建雨夜便利店并生成图片');w.send_chat()
    for _ in range(100):
        QTest.qWait(20)
        if w.chat_worker is None:break
    assert w.chat_worker is None
    assert len(requests)==(1 if cancel else 2)
    assert len(w.project.data['jobs'])==(0 if cancel else 1)
    assert w.send.isEnabled()
    if not cancel:
        assert w.project.data['jobs'][0]['target']==w.project.data['scenes'][0]['id']
        assert '已加入队列' in w.transcript.toPlainText()
    w.close()


def test_chat_cards_fold_navigation_and_refresh(tmp_path):
    p=Project(tmp_path/'p',True)
    p.data['chat']=[{'role':'user','content':'第一条 <script>'},{'role':'assistant','content':'长回答\n'*800},{'role':'user','content':'第二条'},{'role':'assistant','content':'答复'}];p.save()
    w=ui.Studio(p.root);w.show();app.processEvents()
    assert '你 · 我的消息' in w.transcript.toPlainText() and 'AI · 创作助手' in w.transcript.toPlainText()
    assert '展开完整回复' in w.transcript.toPlainText()
    assert w.my_messages.count()==3
    assert 'bgcolor="#dceeff"' in w.transcript.toHtml()
    w.chat_link(QUrl('xychat:toggle/1'));assert '收起长回复' in w.transcript.toPlainText()
    w.jump_user(1);app.processEvents();position=w.transcript.verticalScrollBar().value()
    w.refresh();app.processEvents();assert w.transcript.verticalScrollBar().value()==position
    rendered,_=transcript_html(p.data['chat'],set());assert '&lt;script&gt;' in rendered
    w.close()


def test_double_click_image_and_zoom(tmp_path):
    p=Project(tmp_path/'p',True);im=QImage(800,600,QImage.Format_RGB32);im.fill(QColor('green'));im.save(str(p.file('assets/test.png')))
    w=ui.Studio(p.root);thumb=w.thumbnail('assets/test.png','');thumb.show();app.processEvents()
    QTest.mouseDClick(thumb,Qt.LeftButton);app.processEvents()
    viewers=w.findChildren(ImageViewer);assert len(viewers)==1
    d=viewers[0];d.zoom(1);assert d.image.pixmap().width()==800
    d.zoom(2);assert d.image.pixmap().width()==1600
    d.fit();assert d.image.width()<=d.area.viewport().width()
    d.close();thumb.close();w.close()


def test_generation_cancel_is_chinese(tmp_path):
    from studio.workflows import Generation
    d=ui.GenerationDialog(Project(tmp_path/'p',True),Generation(prompt='test'))
    bb=d.findChild(QDialogButtonBox)
    assert bb.button(QDialogButtonBox.Cancel).text()=='取消生成'
    d.close()

def test_atomic_json_retries_transient_windows_read_lock(tmp_path,monkeypatch):
    import studio.storage as storage
    path=tmp_path/'state.json';storage.atomic_json(path,{'old':True})
    replace=storage.os.replace;calls=[]
    def busy_once(source,target):
        calls.append(source)
        if len(calls)==1:raise PermissionError('open Windows reader')
        replace(source,target)
    monkeypatch.setattr(storage.os,'replace',busy_once)
    monkeypatch.setattr(storage.time,'sleep',lambda _:None)
    storage.atomic_json(path,{'new':True})
    assert json.loads(path.read_text())=={'new':True}
    assert len(calls)==2 and not list(tmp_path.glob('*.tmp'))

def test_cross_round_explicit_name_reference_and_ambiguity():
    from studio.action_targets import resolve_target
    args={'target':'@雨夜便利店'}
    items=[{'id':'actual','name':'雨夜便利店'}]
    assert resolve_target('generate',args,[],{},items)['target']=='actual'
    with pytest.raises(ValueError):resolve_target('generate',args,[],{},items*2)
    with pytest.raises(ValueError):resolve_target('generate',args,[{'function':{'name':'add_item'}}],{},items)
