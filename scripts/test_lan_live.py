"""Explicit opt-in real LAN/ComfyUI test. Creates its own project, consumes local GPU.

No fake progress, responses or generation files. Evidence excludes pairing secrets.
Usage: python scripts/test_lan_live.py --ready local-data/android-lan-ready.json
"""
import argparse
import asyncio
import json
import sys
import threading
import time
import uuid
from pathlib import Path

import requests
import aiohttp


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--ready',required=True)
    parser.add_argument('--evidence',default='demo/evidence/pc-lan-live.json')
    args=parser.parse_args()
    ready=json.loads(Path(args.ready).read_text(encoding='utf-8'))
    session=requests.Session();session.trust_env=False
    base=ready['base']
    paired=session.post(base+'/pair',json={'code':ready['code'],'name':'PC live integration test'},timeout=10)
    paired.raise_for_status();token=paired.json()['token']
    session.headers['Authorization']='Bearer '+token
    state={}
    evidence={'type':'real PC LAN + ComfyUI integration (not Android device acceptance)',
              'started':time.strftime('%Y-%m-%dT%H:%M:%S'), 'checks':{}, 'jobs':[], 'progressEvents':[]}
    path=Path(args.evidence);path.parent.mkdir(parents=True,exist_ok=True)
    def save():path.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    def rpc(command,payload=None):
        nonlocal state
        request={'id':str(uuid.uuid4()),'command':command,'payload':payload or {},
                 'projectId':(state.get('project') or {}).get('id'),'revision':state.get('lanRevision')}
        response=session.post(base+'/rpc',json=request,timeout=40);response.raise_for_status()
        value=response.json();state=value.get('state',state)
        if not value['ok']:raise RuntimeError(value['error'])
        return value.get('result')
    stop=threading.Event()
    async def listen_async():
        seen=set()
        async with aiohttp.ClientSession(trust_env=False) as client:
            async with client.ws_connect(base+'/events') as ws:
                await ws.send_json({'token':token})
                while not stop.is_set():
                    try:
                        msg=await ws.receive_json(timeout=2)
                        for task in (msg.get('state',{}).get('project') or {}).get('tasks',[]):
                            if task.get('steps'):
                                record={'id':task['id'],'node':task.get('node'),'steps':task['steps']}
                                key=json.dumps(record,sort_keys=True)
                                if key not in seen:seen.add(key);evidence['progressEvents'].append(record)
                    except asyncio.TimeoutError:pass
    def listen():
        try:asyncio.run(listen_async())
        except Exception as exc:evidence['websocketError']=str(exc)
    reader=threading.Thread(target=listen,daemon=True);reader.start()
    try:
        rpc('bootstrap')
        evidence['checks']['existingProjectRead']={'id':state['project']['id'],'name':state['project']['name'],'tasks':len(state['project']['tasks'])}
        for kind in ('image','video'):
            media=rpc('library.query',{'kind':kind,'limit':1})
            if media['items']:
                item=media['items'][0];v=rpc('library.preview',{'file':item['file']})
                url=v.get('originalUrl') or v['url']
                result=session.get(base+url,headers={'Range':'bytes=0-1023'},timeout=20)
                evidence['checks']['existing_'+kind]={'http':result.status_code,'bytes':len(result.content),'file':item['file']}
                assert result.status_code==206
        rpc('project.new',{'title':'Android 原生 LAN 真实生成验收 '+time.strftime('%Y%m%d-%H%M')})
        evidence['projectId']=state['project']['id'];save()
        print('Created dedicated real-generation project',evidence['projectId'],flush=True)
        def generate(kind,prompt,refs=None):
            g=rpc('generation.defaults',{'kind':kind,'mode':'qwen' if kind=='image' else 'h3_i2v'})
            g.update(prompt=prompt,megapixels=.2 if kind=='image' else .1,steps=4,seconds=2,seed='20261022',qwen_int8=True,references=refs or [])
            ident=rpc('generation.submit',{'generation':g,'name':'Android LAN '+kind+' live test'})
            entry={'id':ident,'kind':kind,'generation':g};evidence['jobs'].append(entry);save()
            last=None;deadline=time.monotonic()+1500
            while time.monotonic()<deadline:
                rpc('bootstrap');task=next(t for t in state['project']['tasks'] if t['id']==ident)
                marker=(task['status'],task.get('node'),str(task.get('steps')))
                if marker!=last:print(kind,marker,flush=True);last=marker
                entry.update(status=task['status'],promptId=task['raw'].get('prompt_id'))
                if task['status'] in ('completed','failed','unknown','cancelled'):
                    entry['error']=task.get('error');entry['outputs']=task['raw'].get('outputs',[]);save()
                    if task['status']!='completed':raise RuntimeError(f"{kind}: {task.get('error')}")
                    v=task['results'][0];url=v.get('originalUrl') or v['url']
                    result=session.get(base+url,headers={'Range':'bytes=0-2047'},timeout=20)
                    entry['mediaRange']={'status':result.status_code,'bytes':len(result.content)}
                    assert result.status_code==206
                    save();return v['file']
                time.sleep(2)
            raise TimeoutError('Generation exceeded live-test deadline; inspect PC queue before continuing')
        image=generate('image','A small orange toy robot on a clean pale blue studio table, soft daylight, clear silhouette, detailed miniature photography, no text.')
        generate('video','A small orange toy robot stands on the table. The camera slowly pushes in while soft light moves gently across the scene. Keep the robot shape stable. Quiet room tone, no dialogue, no music.',[image])
        evidence['checks']['realWebsocketProgress']=len(evidence['progressEvents'])>0
        evidence['completed']=time.strftime('%Y-%m-%dT%H:%M:%S');save()
        print('REAL LAN IMAGE + VIDEO COMPLETED; evidence:',path,flush=True)
    except Exception as exc:
        evidence['failure']=str(exc);save();raise
    finally:
        stop.set();reader.join(timeout=3)


if __name__=='__main__':main()
