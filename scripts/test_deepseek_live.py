"""Opt-in real DeepSeek + ComfyUI test. Uses the saved key, never logs it.

Runs only against a newly created synthetic project. Actual API usage is billed.
"""
import sys,json,argparse
from pathlib import Path
from dataclasses import asdict
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import keyring
from PySide6.QtCore import QSettings
from studio.deepseek import chat,validate_action
from studio.storage import Project,uid,now,atomic_json
from studio.workflows import Generation
from studio.comfy import Comfy,execute
from studio.media import video_poster

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True,help='Existing robot test image to copy into a new project')
    options=parser.parse_args()
    source=options.source.resolve(strict=True)
    root=Path(__file__).resolve().parents[1]
    settings=QSettings('XiYi','AIStoryStudio')
    key=keyring.get_password('AIStoryStudio','deepseek')
    if not key:raise RuntimeError('No saved DeepSeek key found')
    model=settings.value('model','deepseek-flash')
    p=Project(root/'local-data'/('deepseek-live-'+uid()[:8]),True)
    actor=p.add('characters','测试机器人','红色玩具机器人，木桌、蓝墙。',p.import_file(source))
    shot=p.add('shots','测试分镜','固定机位，机器人抬手。');shot['materials']=[actor['id']];p.save()
    client=Comfy(settings.value('comfy','http://127.0.0.1:8188'));messages=[];report={'model':model,'project':str(p.root),'checks':[]}
    def request(text,allowed):
        messages.append({'role':'user','content':text})
        context={k:p.data[k] for k in ('story','characters','scenes','shots')}
        msg=chat(key,model,messages,context);messages.append(msg)
        calls=msg.get('tool_calls',[])
        if not allowed and not (msg.get('content') or '').strip():raise RuntimeError('Empty text response')
        if allowed and len(calls)!=1:raise RuntimeError('Expected exactly one test action')
        for call in calls:
            name=call['function']['name'];args=json.loads(call['function']['arguments']);validate_action(name,args)
            if name not in allowed:raise RuntimeError('Unexpected test action: '+name)
            if name=='set_story':p.data['story']=args['text'];p.save();result='故事已保存'
            else:
                if args['target'] not in (actor['id'],shot['id']):raise RuntimeError('Unexpected target')
                if args['mode'] not in ('qwen_edit','h3_i2v'):raise RuntimeError('Unexpected generation mode')
                g=Generation(mode=args['mode'],prompt=args['prompt'],references=args['references'],megapixels=.2,seconds=2,qwen_int8=True)
                g.validate()
                for ref in g.references:
                    if not p.file(ref).is_file():raise RuntimeError('Missing reference')
                job={'id':uid(),'target':args['target'],'generation':asdict(g),'materials':[],'created':now(),'status':'new','source':'DeepSeek real API'}
                p.data['jobs'].append(job);p.save()
                outputs=execute(client,p,job)
                for output in outputs:p.attach_output(job,output)
                p.save();result=json.dumps({'status':job['status'],'outputs':outputs},ensure_ascii=False)
                report['checks'].append({'mode':g.mode,'status':job['status'],'outputs':outputs})
            messages.append({'role':'tool','tool_call_id':call['id'],'content':result})
        p.data['chat']=messages;p.save();atomic_json(p.root/'live-report.json',report)
        print('PASS',allowed or 'text',flush=True)
        return msg
    request('这是连通性测试。不要调用工具，只回复“连接成功”。',[])
    request('请只调用一次 set_story，写一个不超过80字的小机器人在桌面上向阳光抬手的完整小故事。不要新增或生成其他内容。',['set_story'])
    request(f'请只调用一次 generate，target 为 {actor["id"]}，mode 为 qwen_edit，references 仅使用 {actor["image"]}。把红色机器人改为绿色，其他构图、形状、桌面、背景和光线保持不变。不要声称已经生成。',['generate'])
    request(f'上一张改图已完成。请只调用一次 generate，target 为 {shot["id"]}，mode 为 h3_i2v，references 必须只使用实际新图片 {actor["image"]}。固定机位，绿色机器人缓缓抬起一只手；2秒，保持构图。H3提示词用三个字段的JSON字符串；不要其他调用。',['generate'])
    request('请根据工具执行结果，用一句话总结哪些操作完成，不要调用工具。',[])
    if shot['video']:report['poster']=video_poster(p,shot['video'])
    report['status']='passed';atomic_json(p.root/'live-report.json',report)
    atomic_json(root/'local-data/deepseek-live-latest.json',report)
    print('PROJECT',p.root,flush=True)

if __name__=='__main__':main()
