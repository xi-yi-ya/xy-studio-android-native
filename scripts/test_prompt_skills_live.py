"""Opt-in, billed DeepSeek prompt-only check. Does not execute generation tools."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import keyring
from PySide6.QtCore import QSettings
from studio.deepseek import chat
from studio.storage import Project,atomic_json

def main():
    root=Path(__file__).resolve().parents[1]
    report=json.loads((root/'local-data/deepseek-live-latest.json').read_text(encoding='utf-8'))
    project=Project(report['project'])
    actor=project.data['characters'][0];shot=project.data['shots'][0]
    context={k:project.data[k] for k in ('story','characters','scenes','shots')}
    key=keyring.get_password('AIStoryStudio','deepseek')
    model=QSettings('XiYi','AIStoryStudio').value('model','deepseek-flash')
    cases=[('qwen_edit',actor['id'],actor['image'],'只将输入图中的机器人轻微改成暖绿色，保留所有原文字、构图和形状。'),
           ('h3_i2v',shot['id'],actor['image'],'首帧开始机器人轻轻抬手，固定机位，2.33秒，无配乐。'),
           ('h3_ref',shot['id'],actor['image'],'参考这张图的机器人身份，创作机器人在窗边轻轻挥手的2.33秒单镜头，无配乐。')]
    results=[]
    for mode,target,ref,request in cases:
        text=f'请为我生成素材：{request} 请调用一次 generate 工具提出可审阅的生成操作，target={target}, mode={mode}, references=["{ref}"]。请使用内置对应 skill，工具参数由用户在窗口确认。'
        msg=chat(key,model,[{'role':'user','content':text}],context)
        atomic_json(root/'local-data/prompt-skills-last-response.json',msg)
        calls=msg.get('tool_calls',[])
        assert len(calls)==1 and calls[0]['function']['name']=='generate'
        args=json.loads(calls[0]['function']['arguments'])
        assert args['mode']==mode and args['target']==target and args['references']==[ref]
        prompt=args['prompt']
        if mode=='h3_i2v':
            assert all(s in prompt for s in ('integrated_multimodal_description','overall_soundscape','non_diegetic_music','<Picture 1>'))
        if mode=='h3_ref':
            fields=['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
            positions=[prompt.index(s) for s in fields]
            assert positions==sorted(positions)
        results.append({'mode':mode,'message':msg,'status':'passed'})
        print('PASS',mode,flush=True)
    atomic_json(root/'local-data/prompt-skills-live.json',{'model':model,'checks':results})

if __name__=='__main__':main()
