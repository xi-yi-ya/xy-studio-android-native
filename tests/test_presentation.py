import json
import pytest
from studio.presentation import display_chat_text


@pytest.mark.parametrize('text',[
    '{"type":"skill","skill":"h3","file":"SKILL.md"}',
    '建议如下：\n```json\n{"type":"skill","skill":"h3","file":"SKILL.md"}\n```',
    '[{"type":"skill","skill":"h3","file":"SKILL.md"}]',
])
def test_only_known_internal_metadata_becomes_readable_summary(text):
    result=display_chat_text({'role':'assistant','content':text})
    assert 'SKILL.md' not in result and '视频创作指南' in result
    assert display_chat_text({'role':'user','content':text})==text


def test_creative_json_and_errors_are_preserved():
    story=json.dumps({'type':'story','description':'一个女孩走进舞台'})
    assert display_chat_text({'role':'assistant','content':story})==story
    assert display_chat_text({'role':'tool','content':'{"error":"参考图不存在"}'})=='操作未完成：参考图不存在'
    assert display_chat_text({'role':'tool','content':'{"id":"old-id","name":"舞台"}'})=='已创建：舞台'


def test_legacy_guide_notation_does_not_claim_unsupported_settings():
    text='已完成技能读取。\n- 画幅：`ratio_follow = <image1>`\n机器人改成黄色。'
    result=display_chat_text({'role':'assistant','content':text,'_activity':[{'type':'skill','skill':'qwen','file':'SKILL.md'}]})
    assert 'ratio_follow' not in result and '技能读取' not in result
    assert '以生成确认窗口为准' in result and '机器人改成黄色' in result


def test_empty_tool_reply_has_a_readable_summary_without_claiming_generation():
    message={'role':'assistant','content':None,'tool_calls':[{'id':'proposal'}]}
    assert display_chat_text(message)=='操作建议已列在下方，请查看确认内容或执行结果。'
    assert message['content'] is None


def test_english_operation_preamble_is_readable_but_original_and_creative_text_survive():
    text = "I'll set up the edit on the existing character."
    message = {'role': 'assistant', 'content': text, 'tool_calls': [
        {'function': {'name': 'generate', 'arguments': '{"prompt":"A yellow robot"}'}}
    ]}
    assert '请查看确认内容' in display_chat_text(message)
    assert message['content'] == text
    assert message['tool_calls'][0]['function']['arguments'] == '{"prompt":"A yellow robot"}'
    assert display_chat_text({'role': 'assistant', 'content': 'A yellow robot on a desk.'}) == 'A yellow robot on a desk.'
