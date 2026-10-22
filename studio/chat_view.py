"""Escaped chat rendering with role cards and stable user-message anchors."""
import html
import re
from .research import safe_link


def markup(text):
    escaped = html.escape(text)
    escaped = re.sub(r'\[([^\]]+)\]\((https?://[^\s)]+)\)',
                     lambda m: '<a href="'+m[2]+'">'+m[1]+'</a>' if safe_link(html.unescape(m[2])) else m[0], escaped)
    escaped = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', escaped)
    return escaped.replace('\n', '<br>')


def transcript_html(messages, expanded):
    cards = []; users = []; turn = 0
    for index, msg in enumerate(messages):
        role = msg['role']; content = msg.get('content') or ''
        if role == 'tool':
            content = msg.get('_display', '')
            if not content:
                try:
                    import json
                    item = json.loads(msg.get('content', ''))
                    content = '已创建：'+item['name'] if isinstance(item, dict) and 'id' in item and 'name' in item else ''
                except (ValueError, TypeError):
                    content = msg.get('content', '')
        if role == 'user':
            turn += 1; users.append((index, f'{turn}. '+content.replace('\n', ' ')[:55]))
        body = markup(content)
        if role == 'assistant' and len(content) > 1400:
            body = markup(content if index in expanded else content[:650]+'…')
            body += f'<p><a href="xychat:toggle/{index}">'+('收起长回复' if index in expanded else f'展开完整回复（{len(content)} 字）')+'</a></p>'
        for activity in msg.get('_activity', []):
            if activity['type'] == 'skill':
                body += '<p><small>已读取技能：'+markup(activity['skill']+'/'+activity['file'])+'</small></p>'
            elif activity['type'] == 'search':
                body += '<p><small>已联网检索：'+markup(activity['query'])+'</small></p>'
                for source in activity['sources'][:5]:
                    if safe_link(source['url']):
                        body += '<p><a href="'+html.escape(source['url'], quote=True)+'">'+html.escape(source['title'])+'</a></p>'
            elif activity['type'] == 'error':
                body += '<p>'+markup('工具未完成：'+activity['message'])+'</p>'
        if not body: continue
        label, color = ('你 · 我的消息', '#dceeff') if role == 'user' else ('AI · 创作助手', '#f1f3f5') if role == 'assistant' else ('操作结果', '#e7f4e9')
        cards.append(f'<a name="message-{index}"></a><table width="100%" cellpadding="10" cellspacing="0" bgcolor="{color}"><tr><td><b>{label} · 第 {turn} 轮</b><p>{body}</p></td></tr></table><p></p>')
    return ''.join(cards), users
