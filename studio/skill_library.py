"""Read-only, bounded access to bundled prompt guides; no arbitrary file access."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent/'skills'
CATALOG={
    'qwen': {'description':'Qwen 图片生成和编辑：保留主体、文字、参考图映射与编辑范围。',
             'files':['SKILL.md','references/t2i-guide.md','references/edit-guide.md','references/output-contracts.md']},
    'h3': {'description':'H3 视频提示词：普通/首尾帧用 base；参考生成用 base + ref，区分三段和六段。',
           'files':['SKILL.md','references/base-en.txt','references/ref-en.txt']},
}

def read_skill(skill,file='SKILL.md'):
    if skill not in CATALOG or file not in CATALOG[skill]['files']:raise ValueError('技能或文件不在内置目录中')
    path=(ROOT/skill/file).resolve()
    if not path.is_relative_to(ROOT.resolve()):raise ValueError('技能路径越界')
    return path.read_text(encoding='utf-8')

def required_guides(mode):
    if mode in ('qwen','qwen_edit'):
        return {('qwen','SKILL.md'),('qwen','references/t2i-guide.md' if mode=='qwen' else 'references/edit-guide.md')}
    if mode.startswith('h3'):
        return {('h3','SKILL.md'),('h3','references/base-en.txt')} | ({('h3','references/ref-en.txt')} if mode=='h3_ref' else set())
    return set()
