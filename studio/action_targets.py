"""Resolve creation dependencies before any generation is offered for approval."""
import copy


def resolve_target(name, args, calls, created, existing=()):
    args = copy.deepcopy(args)
    if name not in ('generate', 'update_item'):
        return args
    field = 'target' if name == 'generate' else 'id'
    target = args[field]
    if target.startswith('@'):
        call_id = target[1:]
        if call_id not in created:
            # A follow-up model response may retain the explicit name reference.
            # Resolve only an exact, unique existing name, never in a create batch.
            matches = [item for item in existing if item['name']==call_id]
            if any(c['function']['name']=='add_item' for c in calls) or len(matches)!=1:
                raise ValueError('所引用的新条目尚未成功创建或已取消，或名称不唯一；没有提交生成。')
            args[field] = matches[0]['id']
        else:
            args[field] = created[call_id]
    elif any(c['function']['name'] == 'add_item' for c in calls):
        raise ValueError('同轮包含新建条目，不能猜测生成或修改归属。请用 @新条目名称 引用新条目，或下一轮单独操作已有条目。')
    if 'materials' in args:
        if any(x.startswith('@') and x[1:] not in created for x in args['materials']):
            raise ValueError('关联素材引用的新条目尚未成功创建或名称不唯一。')
        args['materials'] = [created[x[1:]] if x.startswith('@') else x for x in args['materials']]
    return args
