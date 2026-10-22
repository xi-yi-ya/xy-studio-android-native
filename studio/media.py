"""Decode an actual first video frame; cache independently of project metadata."""
import hashlib
from pathlib import Path
import av

def video_poster(project,relative):
    source=project.file(relative)
    stat=source.stat()
    key=hashlib.sha256(f'{relative}:{stat.st_size}:{stat.st_mtime_ns}'.encode()).hexdigest()
    target=project.file('previews/'+key+'.png')
    if not target.exists():
        target.parent.mkdir(exist_ok=True)
        with av.open(str(source)) as container:
            frame=next(container.decode(video=0),None)
            if frame is None:raise ValueError('视频没有可解码帧')
            img=frame.to_image();img.thumbnail((480,270));img.save(target)
    return target.relative_to(project.root).as_posix()


from functools import lru_cache

@lru_cache(maxsize=256)
def _duration(path,size,mtime):
    with av.open(path) as container:
        if container.duration is not None:return container.duration/av.time_base
        stream=container.streams.video[0]
        if stream.duration is not None:return float(stream.duration*stream.time_base)
        raise ValueError('视频没有时长元数据')

def video_duration(path):
    path=Path(path);stat=path.stat()
    return _duration(str(path),stat.st_size,stat.st_mtime_ns)
