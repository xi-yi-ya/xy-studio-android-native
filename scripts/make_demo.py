import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio.storage import Project
root=Path(__file__).resolve().parents[1]
p=Project(root/'local-data'/'demo-project',create=not (root/'local-data'/'demo-project'/'project.json').exists())
if not p.data['shots']:
    p.data['title']='小机器人的午后 · 示例项目'
    p.data['story']='午后的工作室里，小机器人发现窗外的光。它抬起手向光线打招呼，最后安静地坐回桌边。'
    a=p.add('characters','小机器人','红色铁皮玩具机器人，圆形眼睛，方形身体。')
    s=p.add('scenes','午后工作室','木质桌面、浅蓝色墙壁、窗边柔和的自然光。')
    images=list((root/'local-data'/'smoke-project'/'outputs'/'f516b896ef9b4bfea259e9cb82df9e89').glob('*.png'))
    if images:a['image']=p.import_file(images[0])
    for name,desc in [('分镜 01','固定机位。小机器人站在桌面上，看向窗外。'),('分镜 02','小机器人缓缓举起一只手，向阳光打招呼。')]:
        shot=p.add('shots',name,desc);shot['materials']=[a['id'],s['id']];shot['image']=a['image']
    p.save()
print(p.root)
