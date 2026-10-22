"""Opt-in billed DeepSeek model, skill and search checks. No generation execution."""
import sys,json,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import keyring
from studio.deepseek import chat,list_models
from studio.storage import Project,uid,atomic_json

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case');options=parser.parse_args()
    key=keyring.get_password('AIStoryStudio','deepseek');models=list_models(key)
    root=Path(__file__).resolve().parents[1];p=Project(root/'local-data'/('agent-v014-'+uid()[:8]),True)
    report={'models':models,'checks':[],'project':str(p.root)}
    cases=[('plain','deepseek-flash','你好，请只回一句简短中文，不需要调用工具。',False),
           ('qwen','deepseek-flash','请按内置 Qwen 编辑技能，为“仅把杯子改成红色，其余画面和文字保留”写一句中文提示词。只写提示词，不生成图片，不需要看图。',False),
           ('h3','deepseek-flash','按内置 H3 参考视频技能写一个提示词模板：Picture 1 提供机器人身份，机器人在窗边挥手，单镜头 2.33 秒，无配乐。只交付六段英文提示词，不生成、不修改项目，也不要假装看过图。',False),
           ('search','deepseek-flash','请联网查找 DeepSeek 官方模型列表接口文档，告诉我接口路径，附上官方来源链接。不修改项目。',True)]
    if 'deepseek-v4-pro' in models:cases.append(('pro','deepseek-v4-pro','请只用一句中文确认模型连通，不调用工具。',False))
    for name,model,prompt,online in cases:
        if options.case and name!=options.case:continue
        msg=chat(key,model,[{'role':'user','content':prompt}],{},online=online,notify=lambda s:print(s.encode('ascii','backslashreplace').decode(),flush=True))
        assert not msg.get('tool_calls'),'Unexpected mutation proposal'
        activity=msg.get('_activity',[])
        if name=='plain':assert not activity
        if name=='qwen':assert any(a['type']=='skill' and a['skill']=='qwen' for a in activity)
        if name=='h3':assert any(a['type']=='skill' and a['file']=='references/ref-en.txt' for a in activity)
        if name=='search':assert any(a['type']=='search' and a['sources'] for a in activity)
        p.data['chat'] += [{'role':'user','content':prompt},msg];p.save()
        report['checks'].append({'case':name,'model':model,'status':'passed','activity':activity})
        atomic_json(root/('local-data/agent-v014-live-report'+('-'+options.case if options.case else '')+'.json'),report)
        print('PASS',name,flush=True)
    print('PROJECT',p.root,flush=True)

if __name__=='__main__':main()
