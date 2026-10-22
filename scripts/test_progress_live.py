"""Explicit low-resolution ComfyUI progress check. Does not run under pytest."""
import sys
from pathlib import Path
from dataclasses import asdict
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio.comfy import Comfy,execute
from studio.storage import Project,uid,atomic_json
from studio.workflows import Generation

def main():
    client=Comfy()
    queue=client.queue()
    if queue.get('queue_running') or queue.get('queue_pending'):raise RuntimeError('Backend busy; test not submitted')
    root=Path(__file__).resolve().parents[1]
    p=Project(root/'local-data'/('progress-check-'+uid()[:8]),True)
    item=p.add('characters','Progress test','A small red robot on a desk.')
    g=Generation(mode='krea',prompt=item['description'],megapixels=.2,steps=4)
    j={'id':uid(),'target':item['id'],'generation':asdict(g),'status':'new','materials':[]}
    p.data['jobs'].append(j);p.save();events=[]
    def notify(state):
        entry={'state':state,'node':j.get('node'),'progress':j.get('progress')}
        if not events or events[-1]!=entry:
            events.append(entry);print(entry,flush=True)
    result=execute(client,p,j,notify)
    for path in result:p.attach_output(j,path)
    p.save()
    atomic_json(root/'local-data/progress-live-report.json',{'project':str(p.root),'events':events,'job':j})
    assert any(e.get('progress') for e in events),'No real progress event received'
    assert j['status']=='completed'
    print('PASS',p.root,flush=True)

if __name__=='__main__':main()
