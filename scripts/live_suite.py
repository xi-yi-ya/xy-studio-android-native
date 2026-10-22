"""Manually invoked, sequential low-resolution acceptance matrix."""
import subprocess,sys,json,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
ref=str(next((root/'local-data/smoke-project/outputs/f516b896ef9b4bfea259e9cb82df9e89').glob('*.png')))
matrix=[('h3_i2v',ref,'--cinema'),('h3_ref',ref),('h3_ref',ref,'--cinema'),('qwen',),('qwen_edit',ref),('krea','','--style'),('quad',ref),('upscale',ref)]
results=[]
for args in matrix:
    start=time.time();print('START',args[0],args[2:] if len(args)>2 else '',flush=True)
    p=subprocess.run([sys.executable,str(root/'scripts/live_test.py'),*args],capture_output=True,text=True,encoding='utf-8',errors='replace')
    results.append({'args':args,'returncode':p.returncode,'seconds':round(time.time()-start,1),'stdout':p.stdout,'stderr':p.stderr})
    (root/'local-data/live-suite.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print('DONE',args[0],p.returncode,p.stdout[-400:],p.stderr[-1000:],flush=True)
