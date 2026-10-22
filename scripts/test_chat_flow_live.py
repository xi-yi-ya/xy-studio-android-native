"""Opt-in billed DeepSeek + low-resolution ComfyUI integration check."""
import os,sys,time,json
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication,QMessageBox,QDialog
from PySide6.QtTest import QTest
from studio.ui import Studio,GenerationDialog
from studio.storage import Project,uid,atomic_json
from studio.comfy import Comfy

def main():
    queue=Comfy().queue()
    if queue['queue_running'] or queue['queue_pending']:raise RuntimeError('ComfyUI busy')
    app=QApplication([]);root=Path(__file__).resolve().parents[1]
    p=Project(root/'local-data'/('v016-live-'+uid()[:8]),True)
    w=Studio(p.root);w.online.blockSignals(True);w.online.setChecked(False);w.model_picker.blockSignals(True);w.model_picker.setCurrentText('deepseek-flash')
    approvals=[]
    def confirm(d):
        if d.button(QMessageBox.Apply):
            approvals.append(d.text());return QMessageBox.Apply
        print('DIALOG',d.text(),flush=True);return QMessageBox.Ok
    def parameters(d):
        approvals.append('generation:'+d.target)
        d.mp.setValue(.1);d.steps.setValue(4);d.accept_valid()
        return d.result()
    QMessageBox.exec=confirm;GenerationDialog.exec=parameters
    w.input.setPlainText('新建一个名叫雨夜便利店的场景，并调用 Krea 图片工作流生成一张无人的雨夜便利店图片。构图由你决定，已确认要生成，不要只写提示词。');w.send_chat()
    end=time.monotonic()+300
    while time.monotonic()<end:
        QTest.qWait(50);time.sleep(.01)
        if w.chat_worker is None and not w.active:break
    if w.active:
        w.worker.requestInterruption()
        while w.active:QTest.qWait(50);time.sleep(.01)
    if w.chat_worker:
        while w.chat_worker:QTest.qWait(50);time.sleep(.01)
    jobs=w.project.data['jobs'];report={'project':str(p.root),'approvals':approvals,'jobs':jobs,'chat_rounds':w.chat_rounds}
    atomic_json(root/'local-data/v016-live-report.json',report)
    assert jobs and jobs[-1]['status']=='completed',json.dumps(report,ensure_ascii=True)
    item=w.project.get(jobs[-1]['target']);assert item in w.project.data['scenes'] and item['versions']
    assert w.project.file(item['image']).is_file()
    print(json.dumps({'passed':True,'project':str(p.root),'rounds':w.chat_rounds,'status':jobs[-1]['status']},ensure_ascii=True),flush=True)
    w.close()
if __name__=='__main__':main()
