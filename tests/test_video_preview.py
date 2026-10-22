"""Codec cache contains actual frames/audio and never rewrites source media."""
import hashlib
import struct
from fractions import Fraction
import av
import pytest
from studio.storage import Project
from studio.video_preview import transcode, preview_path


def make_clip(path):
    with av.open(str(path),'w') as c:
        video=c.add_stream('libx264',rate=24);video.width=64;video.height=64;video.pix_fmt='yuv420p'
        audio=c.add_stream('aac',rate=48000);audio.layout='mono'
        for i in range(24):
            frame=av.VideoFrame(64,64,'yuv420p');frame.pts=i;frame.time_base=Fraction(1,24)
            for plane in frame.planes:plane.update(bytes([80])*plane.buffer_size)
            for packet in video.encode(frame):c.mux(packet)
        frame=av.AudioFrame(format='fltp',layout='mono',samples=48000)
        frame.sample_rate=48000;frame.pts=0;frame.time_base=Fraction(1,48000)
        frame.planes[0].update(struct.pack('<f',.1)*48000)
        for packet in audio.encode(frame):c.mux(packet)
        for packet in video.encode():c.mux(packet)
        for packet in audio.encode():c.mux(packet)


def test_preview_preserves_frames_audio_source_and_caches(tmp_path):
    p=Project(tmp_path/'story',True);original=p.file('assets/actual.mp4');make_clip(original)
    digest=hashlib.sha256(original.read_bytes()).hexdigest()
    relative=transcode(p,'assets/actual.mp4');target=p.file(relative);mtime=target.stat().st_mtime_ns
    with av.open(str(target)) as c:
        assert [s.codec_context.name for s in c.streams]==['vp9','opus']
        assert abs(c.duration/av.time_base-1)<.04
        assert len(list(c.decode(video=0)))==24
    with av.open(str(target)) as c:assert sum(f.samples for f in c.decode(audio=0))==48000
    assert hashlib.sha256(original.read_bytes()).hexdigest()==digest
    assert transcode(p,'assets/actual.mp4')==relative and target.stat().st_mtime_ns==mtime


def test_preview_exit_cancels_and_removes_partial_cache(tmp_path):
    p=Project(tmp_path/'story',True);original=p.file('assets/actual.mp4');make_clip(original)
    target=preview_path(p,'assets/actual.mp4')
    with pytest.raises(InterruptedError):transcode(p,'assets/actual.mp4',lambda:True)
    assert original.exists() and not target.exists() and not target.with_suffix('.partial.webm').exists()
