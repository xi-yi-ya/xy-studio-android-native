"""User-facing summaries; original agent messages remain intact on disk."""
import json
import re


def public_status(text):
    text = str(text or '')
    if text.startswith('读取技能：'):
        return '正在准备视频创作建议' if 'h3/' in text else '正在准备图片创作建议'
    if text.startswith('联网检索：'):
        return '正在查找相关资料'
    return text


def _record_summary(value):
    if isinstance(value, list) and value:
        summaries = [_record_summary(v) for v in value]
        return '\n'.join(dict.fromkeys(summaries)) if all(summaries) else None
    if not isinstance(value, dict):
        return None
    if value.get('type') == 'skill' and set(value) <= {'type', 'skill', 'file'}:
        return '已参考视频创作指南。' if value.get('skill') == 'h3' else '已参考图片创作指南。'
    if value.get('type') == 'function' and isinstance(value.get('function'), dict):
        if value['function'].get('name') in ('generate', 'add_item', 'update_item', 'set_story', 'read_skill'):
            return '已准备操作建议，请在界面确认后执行。'
    return None


def display_chat_text(message):
    text = message.get('_display', message.get('content')) or ''
    if message.get('role') == 'user':
        return text
    operation_calls = any(
        c.get('function', {}).get('name') in ('generate', 'add_item', 'update_item', 'set_story')
        for c in message.get('tool_calls', [])
    )
    if message.get('role') == 'assistant' and (
        not text and message.get('tool_calls') or
        operation_calls and not re.search(r'[\u4e00-\u9fff]', text)
    ):
        text = '操作建议已列在下方，请查看确认内容或执行结果。'
    if message.get('role') == 'tool':
        try:
            value = json.loads(text)
            if isinstance(value, dict) and 'id' in value and 'name' in value:
                return '已创建：' + str(value['name'])
            if isinstance(value, dict) and 'error' in value:
                return '操作未完成：' + str(value['error'])
        except (ValueError, TypeError):
            pass
        text = re.sub(r'，任务 [0-9a-f]{32}；', '；', text)
    if message.get('role')=='assistant' and any(a.get('type')=='skill' for a in message.get('_activity', [])):
        text = text.replace('已完成技能读取', '已准备好创作建议')
        text = text.replace('SKILL.md', '创作指南') if '"file"' not in text else text
        # Unsupported implementation notation from older guide replies must
        # not imply that it changed the actual GUI parameters.
        text = re.sub(r'(?m)^.*ratio_follow.*$', '画面比例与大小请以生成确认窗口为准。', text)
    # Convert only recognized internal metadata, never arbitrary creative JSON.
    def fence(match):
        try:
            return _record_summary(json.loads(match[1])) or match[0]
        except ValueError:
            return match[0]
    text = re.sub(r'```(?:json)?\s*([\s\S]*?)```', fence, text)
    decoder = json.JSONDecoder()
    chunks, at = [], 0
    for match in re.finditer(r'[\[{]', text):
        start = match.start()
        if start < at:
            continue
        try:
            value, end = decoder.raw_decode(text[start:])
        except ValueError:
            continue
        summary = _record_summary(value)
        if summary:
            chunks.extend((text[at:start], summary))
            at = start + end
    chunks.append(text[at:])
    return ''.join(chunks)
