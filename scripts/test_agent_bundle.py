"""Explicit opt-in integration test: run approved local agent actions in a COPY.

Never run by pytest. Uses actual ComfyUI at low resolution, no DeepSeek key.
"""
import os,sys,json,shutil
from pathlib import Path
from dataclasses import asdict
os.environ['QT_QPA_PLATFORM']='offscreen'
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from PySide6.QtWidgets import QApplication
from studio.ui import Studio
from studio.storage import uid,now,atomic_json
from studio.comfy import Comfy,execute
from studio.media import video_poster

def main():
    bundle=json.loads((root/'local-data/agent-assistant-test.json').read_text(encoding='utf-8-sig'))
    dest=root/'local-data'/('agent-check-'+uid()[:8]);shutil.copytree(root/'local-data/demo-project',dest)
    app=QApplication([]);window=Studio(dest);p=window.project;results=[]
    assert bundle['project_id']==p.data['id']
    def generate(item,mode,g):
        g.megapixels=.2;g.seconds=2;g.qwen_int8=True;g.validate()
        j={'id':uid(),'target':item['id'],'generation':asdict(g),'materials':[],'status':'new','created':now(),'source':bundle['provider']}
        p.data['jobs'].append(j);p.save()
        output=execute(Comfy(),p,j,lambda status:None)
        for relative in output:p.attach_output(j,relative)
        p.save();return j
    window.generate=generate
    for call in bundle['message']['tool_calls']:
        fn=call['function'];result=window.apply_action(fn['name'],json.loads(fn['arguments']))
        results.append({'tool':fn['name'],'result':result});print(fn['name'],result[:160],flush=True)
    for shot in p.data['shots']:
        if shot['video']:video_poster(p,shot['video'])
    atomic_json(root/'local-data/agent-integration-result.json',{'project':str(dest),'provider':bundle['provider'],'results':results,'jobs':p.data['jobs']})
    print('PROJECT',dest,flush=True);window.close()

if __name__=='__main__':main()
