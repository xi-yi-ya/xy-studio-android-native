import av
from PIL import Image
from studio.storage import Project
from studio.media import video_poster

def test_poster_is_actual_first_frame_and_cached(tmp_path):
    p=Project(tmp_path/'p',True);video=p.file('outputs/test.mkv')
    with av.open(str(video),'w') as c:
        stream=c.add_stream('ffv1',rate=24);stream.width=32;stream.height=32;stream.pix_fmt='bgr0'
        for color in ('red','blue'):
            frame=av.VideoFrame.from_image(Image.new('RGB',(32,32),color))
            for packet in stream.encode(frame):c.mux(packet)
        for packet in stream.encode():c.mux(packet)
    relative=video_poster(p,'outputs/test.mkv')
    with Image.open(p.file(relative)) as im:assert im.convert('RGB').getpixel((0,0))==(255,0,0)
    assert video_poster(p,'outputs/test.mkv')==relative

def test_detach_delete_preserves_results_and_removes_only_reference(tmp_path):
    p=Project(tmp_path/'p',True);a=p.add('characters','actor');s=p.add('shots','shot');s['materials']=[a['id']];s['video']='outputs/keep.mp4'
    p.delete(a['id'],detach=True)
    assert s['materials']==[] and s['video']=='outputs/keep.mp4' and s['needs_review']

def test_video_duration_uses_media_metadata(tmp_path):
    from studio.media import video_duration
    video=tmp_path/'duration.mkv'
    with av.open(str(video),'w') as c:
        stream=c.add_stream('ffv1',rate=24);stream.width=32;stream.height=32;stream.pix_fmt='bgr0'
        for _ in range(24):
            for packet in stream.encode(av.VideoFrame.from_image(Image.new('RGB',(32,32),'green'))):c.mux(packet)
        for packet in stream.encode():c.mux(packet)
    assert abs(video_duration(video)-1)<.05
