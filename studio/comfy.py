import json
import time
import uuid
from pathlib import Path
import requests
import websocket
from urllib.parse import urlsplit
from .workflows import Generation,build,preflight
from .storage import atomic_json,now,uid

class Comfy:
    def __init__(self,url='http://127.0.0.1:8188'):
        self.url=url.rstrip('/'); self.session=requests.Session()
        # Local inference must not be redirected through environment proxies.
        self.session.trust_env=False
        self.client_id=str(uuid.uuid4());self.ws=None

    def open_progress(self,client_id=None):
        if client_id:self.client_id=client_id
        try:
            self.ws=websocket.create_connection(self.url.replace('http','ws',1)+'/ws?clientId='+self.client_id,timeout=3,http_no_proxy=[urlsplit(self.url).hostname])
            self.ws.settimeout(.1)
        except Exception:self.ws=None

    def progress_events(self,prompt_id):
        events=[]
        if self.ws is None:return events
        try:
            for _ in range(100):
                raw=self.ws.recv()
                if not raw:break
                if not isinstance(raw,str):continue
                event=json.loads(raw);data=event.get('data',{})
                if data.get('prompt_id')==prompt_id and event.get('type') in ('progress','executing'):
                    events.append(event)
                elif data.get('prompt_id')==prompt_id and event.get('type')=='progress_state':
                    # Recent ComfyUI versions also publish per-node snapshots.
                    # Only running nodes are measurements of current work;
                    # finished nodes must not look like total task completion.
                    for node_id, state in data.get('nodes', {}).items():
                        if state.get('state')!='running':continue
                        node=state.get('node_id',node_id)
                        if state.get('max',0)>0:
                            events.append({'type':'progress','data':{'prompt_id':prompt_id,'node':node,'value':state['value'],'max':state['max']}})
                        else:
                            events.append({'type':'executing','data':{'prompt_id':prompt_id,'node':node}})
        except websocket.WebSocketTimeoutException:pass
        except Exception:self.close_progress()
        return events

    def close_progress(self):
        if self.ws:
            try:self.ws.close()
            except Exception:pass
        self.ws=None

    def call(self,method,path,**kw):
        r=self.session.request(method,self.url+path,timeout=(10,60),**kw)
        if not r.ok: raise RuntimeError(f'ComfyUI HTTP {r.status_code}: {r.text[:2000]}')
        # Queue deletion/interrupt may return HTTP 200 with an empty body.
        return r.json() if r.content.strip() else {}

    def info(self): return self.call('GET','/object_info')
    def queue(self): return self.call('GET','/queue')
    def upload(self,path):
        path=Path(path)
        with path.open('rb') as f:
            x=self.call('POST','/upload/image',files={'image':(uid()+path.suffix,f)},data={'type':'input','overwrite':'false','subfolder':'AIStoryStudio'})
        return '/'.join(v for v in (x.get('subfolder'),x['name']) if v)

    def submit(self,graph):
        data=self.call('POST','/prompt',json={'prompt':graph,'client_id':self.client_id})
        if data.get('node_errors') or not data.get('prompt_id'): raise RuntimeError(json.dumps(data,ensure_ascii=False))
        return data['prompt_id']

    def history(self,prompt_id): return self.call('GET','/history/'+prompt_id).get(prompt_id)

    def cancel(self,prompt_id):
        q=self.queue()
        if any(x[1]==prompt_id for x in q.get('queue_pending',[])):
            self.call('POST','/queue',json={'delete':[prompt_id]}); return 'cancelled'
        if any(x[1]==prompt_id for x in q.get('queue_running',[])):
            # Endpoint supports prompt_id on this installed backend; never interrupt globally.
            self.call('POST','/interrupt',json={'prompt_id':prompt_id}); return 'cancel_requested'
        return 'not_queued'

    def download(self,history,dest):
        outputs=history.get('outputs',{}).get('output',{})
        files=[]
        for key in ('images','videos','gifs'):
            for entry in outputs.get(key,[]):
                if entry.get('type')!='output': continue
                name=Path(entry['filename']).name
                if Path(name).suffix.lower() not in ('.png','.jpg','.jpeg','.webp','.mp4','.webm','.mkv'): continue
                dest=Path(dest); dest.mkdir(parents=True,exist_ok=True)
                target=dest/(uid()+Path(name).suffix.lower())
                r=self.session.get(self.url+'/view',params={k:entry.get(k,'') for k in ('filename','subfolder','type')},timeout=(10,120))
                r.raise_for_status(); target.write_bytes(r.content); files.append(target)
        if not files: raise RuntimeError('任务完成但没有可读取的图片或视频输出')
        return files

def execute(client, project, job, notify=lambda s:None, stopping=lambda:False):
    """Caller serializes execution and project writes. Persist id before polling.

    A network error after submission is UNKNOWN, never automatically re-submit.
    Resume jobs with a known prompt_id by calling this again.
    """
    def update(state,**fields):
        job.update(status=state,updated=now(),**fields)
        atomic_json(project.file('jobs/'+job['id']+'.json'),job)
        notify(state)
    try:
        if hasattr(client,'open_progress'):
            client.open_progress(job.get('client_id'));job['client_id']=client.client_id
        job.pop('progress',None)
        if not job.get('prompt_id'):
            g=Generation(**job['generation'])
            if 'edit_follow_source' in job: g.edit_follow_source=job['edit_follow_source']
            g.validate()
            uploaded=[client.upload(project.file(p)) for p in g.references]
            graph=build(g,uploaded,'AIStoryStudio/'+job['id'])
            preflight(graph,client.info())
            atomic_json(project.file('jobs/'+job['id']+'-graph.json'),graph)
            update('submitting')
            prompt_id=client.submit(graph)
            update('queued',prompt_id=prompt_id)
        pid=job['prompt_id']
        misses=0
        while True:
            if stopping(): update('detached'); return []
            for event in client.progress_events(pid) if hasattr(client,'progress_events') else []:
                data=event['data'];node=data.get('node')
                if event['type']=='executing':
                    update('running',node=node,progress=None)
                elif data.get('max',0)>0:
                    update('running',node=node,progress={'value':data['value'],'max':data['max']})
            history=client.history(pid)
            if history:
                status=history.get('status',{})
                if status.get('status_str')=='error':
                    if any(m[0]=='execution_interrupted' for m in status.get('messages',[])):
                        update('cancelled');return []
                    raise RuntimeError(json.dumps(status.get('messages',[]),ensure_ascii=False)[:6000])
                if status.get('completed'):
                    update('downloading',progress=None)
                    files=client.download(history,project.file('outputs/'+job['id']))
                    relative=[p.relative_to(project.root).as_posix() for p in files]
                    update('completed',outputs=relative)
                    return relative
            q=client.queue()
            if any(x[1]==pid for x in q.get('queue_running',[])): misses=0;update('running')
            elif any(x[1]==pid for x in q.get('queue_pending',[])): misses=0;update('queued')
            elif not history:
                misses+=1
                if misses>=16: raise RuntimeError('任务已不在队列且无历史记录；请检查 ComfyUI，未自动重交')
            time.sleep(.5)
    except Exception as e:
        update('unknown' if job.get('status')=='submitting' else 'failed',error=str(e))
        raise
    finally:
        if hasattr(client,'close_progress'):client.close_progress()
