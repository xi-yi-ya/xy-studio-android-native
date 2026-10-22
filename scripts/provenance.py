"""Record hashes only; never copy personal prompts or input paths to Git."""
import hashlib,json
from pathlib import Path
source=Path('D:/AI/CGMi_ComfyUI_Helper_v1.2/CGMi_ComfyUI_Helper_v1.2/ComfyUI/user/default/workflows')
names=['image_qwen_image_2_1_t2i.json','Krea2文生图.json','Krea2角色设定表四视图.json','MiniMax_H3图生视频.json','video_minimax_h3全能参考.json','图片放大修复_RFMSR.json']
data=[]
for name in names:
    p=source/name
    data.append({'file':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
out=Path(__file__).resolve().parents[1]/'docs'/'workflow-sources.json';out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print('Recorded',len(data),'approved workflow hashes')
