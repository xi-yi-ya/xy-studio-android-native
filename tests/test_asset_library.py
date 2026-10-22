import copy
from dataclasses import asdict

import av
import pytest
from PIL import Image

from studio.asset_library import AssetLibrary
from studio.storage import Project
from studio.workflows import Generation


def image(p, relative, color='blue', size=(64, 96)):
    file = p.file(relative); file.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', size, color).save(file)
    return relative


def video(p, relative):
    file = p.file(relative); file.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(file), 'w') as container:
        stream = container.add_stream('libvpx-vp9', rate=24)
        stream.width, stream.height, stream.pix_fmt = 64, 48, 'yuv420p'
        for n in range(2):
            frame = av.VideoFrame.from_image(Image.new('RGB', (64, 48), 'green'))
            frame.pts = n
            for packet in stream.encode(frame): container.mux(packet)
        for packet in stream.encode(): container.mux(packet)
    return relative


def job(p, target, relative, ident, prompt='舞台灯光', mode='qwen'):
    j = {'id': ident, 'target': target, 'generation': asdict(Generation(mode=mode, prompt=prompt)), 'status': 'completed', 'outputs': [relative]}
    p.data['jobs'].append(j); p.attach_output(j, relative)
    return j


def test_inventory_keeps_generated_history_deleted_outputs_unassigned_and_imports(tmp_path):
    p=Project(tmp_path/'story', True); a=p.add('characters','歌手'); s=p.add('scenes','舞台')
    imported=image(p,'assets/import.png'); p.attach_output({'id':'import','target':a['id'],'generation':asdict(Generation(prompt='导入'))},imported)
    # Real import records have no generation job.
    a['versions'][0].pop('job')
    first=image(p,'outputs/one.png','red'); second=image(p,'outputs/two.png','green')
    job(p,s['id'],first,'one'); job(p,s['id'],second,'two')
    s['image']=first  # Switching current version must not lose the other output.
    reference=image(p,'assets/unassigned.png')
    orphan=image(p,'outputs/orphan/retained.png')
    cache=image(p,'previews/derived.png')
    before=copy.deepcopy(p.data)
    rows=AssetLibrary(p).query('image',limit=100)['items']
    assert {r['file'] for r in rows}=={imported,first,second,reference,orphan}
    assert next(r for r in rows if r['file']==first)['current']
    assert not next(r for r in rows if r['file']==second)['current']
    assert next(r for r in rows if r['file']==orphan)['source']=='generated'
    assert next(r for r in rows if r['file']==imported)['source']=='imported'
    assert p.data==before and cache not in {r['file'] for r in rows}
    p.delete(s['id'])
    retained=AssetLibrary(p).query('image',owner='deleted')
    assert {r['file'] for r in retained['items']}=={first,second}
    assert all(r['exists'] and r['deletedOwner'] for r in retained['items'])


def test_search_pagination_and_readable_metadata_cover_all_results(tmp_path):
    p=Project(tmp_path/'story',True); a=p.add('shots','镜头')
    for n in range(31): job(p,a['id'],image(p,f'outputs/{n:02}.png'),str(n),prompt='Stage LIGHT '+str(n))
    library=AssetLibrary(p)
    first=library.query('image',query='stage light',source='generated',owner='shots',sort='name',limit=24)
    second=library.query('image',query='stage light',source='generated',owner='shots',sort='name',limit=24,offset=24)
    assert first['total']==31 and first['hasMore'] and len(second['items'])==7 and not second['hasMore']
    assert {r['file'] for r in first['items']}.isdisjoint({r['file'] for r in second['items']})
    assert first['stats']['generated']==31
    assert all(r['width']==64 and r['height']==96 and r['bytes']>0 for r in first['items'])
    assert library.query('video')['total']==0


def test_video_inventory_reads_original_metadata_and_cache_is_not_a_new_asset(tmp_path):
    p=Project(tmp_path/'story',True); a=p.add('shots','镜头')
    original=video(p,'outputs/clip.webm'); job(p,a['id'],original,'clip',mode='h3_i2v')
    video(p,'previews/clip-cache.webm')
    result=AssetLibrary(p).query('video')
    assert result['total']==1
    r=result['items'][0]
    assert r['file']==original and r['width']==64 and r['height']==48 and r['duration']>0


def test_missing_corrupt_and_unsafe_files_are_not_silent_or_outside_the_project(tmp_path):
    p=Project(tmp_path/'story',True); a=p.add('characters','人物')
    job(p,a['id'],'outputs/missing.png','missing')
    p.file('assets/corrupt.png').write_bytes(b'not an image')
    outside=tmp_path/'outside.png'; Image.new('RGB',(32,32)).save(outside)
    a['versions'].append({'id':'unsafe','file':'../outside.png','kind':'image','intent':''})
    result=AssetLibrary(p).query('image')
    assert result['total']==2 and result['stats']['missing']==1
    assert all(r['error'] for r in result['items'])
    assert not next(r for r in result['items'] if r['file']=='outputs/missing.png')['exists']
    with pytest.raises(ValueError):AssetLibrary(p).get('../outside.png')


@pytest.mark.parametrize('args',[{'kind':'bad'},{'kind':'image','limit':True},{'kind':'image','offset':-1},{'kind':'image','limit':101},{'kind':'image','source':'hidden'},{'kind':'image','query':5}])
def test_invalid_query_ranges_and_types_are_rejected(tmp_path,args):
    with pytest.raises(ValueError):AssetLibrary(Project(tmp_path/'p',True)).query(**args)
