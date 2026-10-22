"""Opt-in local inference. Low-resolution tests; never submitted by pytest."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dataclasses import asdict
from studio.storage import Project,uid,atomic_json
from studio.workflows import Generation
from studio.comfy import Comfy,execute

root=Path(__file__).resolve().parents[1]/'local-data'/'smoke-project'
p=Project(root,create=not (root/'project.json').exists())
c=Comfy()
mode=sys.argv[1] if len(sys.argv)>1 else 'krea'
ref=sys.argv[2] if len(sys.argv)>2 else ''
g=Generation(mode=mode,prompt='A small red toy robot standing on a wooden desk, soft daylight, plain blue wall, no text.',megapixels=.2,ratio='16:9',seconds=2,seed=713,qwen_int8=True)
if ref: g.references=[p.import_file(ref)]
if mode.startswith('h3'):
    g.prompt='{"integrated_multimodal_description":"For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced. [Shot 1] Static camera. The small toy robot slowly raises one arm. Keep the desk and wall unchanged.","overall_soundscape":"Quiet room tone.","non_diegetic_music":"None."}'
if '--cinema' in sys.argv: g.cinema=True
if '--style' in sys.argv: g.styles=['darkbrush']
if mode=='h3_ref':
    g.prompt=json.dumps({'subject_definitions':'<Picture 1> shows the small red toy robot and its desk.','summary':'The toy robot raises one arm.','retention_analysis':'Preserve the robot appearance and desk from <Picture 1>.','detailed_description':'[Shot 1] Static camera. The robot slowly raises one arm. Soft daylight.','overall_soundscape':'Quiet room tone.','non_diegetic_music':'None.'})
if mode=='qwen_edit':g.prompt='将 <image1> 中机器人的身体颜色改成绿色。保持机器人形状、背景、构图和光线不变。'
if mode=='quad': g.prompt='Convert the character into a character sheet with four views: face close-up, front view, side view and back view. White background, consistent proportions.'
item=p.add('shots',mode)
j={'id':uid(),'target':item['id'],'generation':asdict(g),'status':'new','materials':[]}
p.data['jobs'].append(j);p.save()
last=['']
def report(s):
    if s!=last[0]: print(s,flush=True);last[0]=s
try:
    result=execute(c,p,j,report)
    for r in result: p.attach_output(j,r)
    p.save();print(json.dumps({'mode':mode,'job':j['id'],'outputs':[str(p.file(r)) for r in result]},ensure_ascii=False),flush=True)
except Exception:
    p.save();raise
