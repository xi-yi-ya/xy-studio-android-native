"""VP9/Opus viewing cache for Qt's non-proprietary Chromium codecs.

Original generated files and schema are untouched. One daemon worker limits CPU
and memory; the cache is disposable and output is published atomically.
"""
import hashlib
import queue
import threading
from pathlib import Path
import av
from PySide6.QtCore import QObject, Signal


def preview_path(project, relative):
    source = project.file(relative)
    stat = source.stat()
    key = hashlib.sha256(f'vp9-v1:{relative}:{stat.st_size}:{stat.st_mtime_ns}'.encode()).hexdigest()
    return project.file('previews/'+key+'.webm')


def transcode(project, relative, stopping=lambda: False):
    target = preview_path(project, relative)
    if target.exists():
        return target.relative_to(project.root).as_posix()
    target.parent.mkdir(exist_ok=True)
    temporary = target.with_suffix('.partial.webm')
    try:
        with av.open(str(project.file(relative))) as source, av.open(str(temporary), 'w', format='webm') as dest:
            original = source.streams.video[0]
            ratio = min(1, 1280/max(original.width, original.height))
            video = dest.add_stream('libvpx-vp9', rate=original.average_rate or 24)
            video.width = max(2, int(original.width*ratio)//2*2)
            video.height = max(2, int(original.height*ratio)//2*2)
            video.pix_fmt = 'yuv420p'
            video.options = {'deadline':'realtime', 'cpu-used':'5', 'crf':'28'}
            video.bit_rate = 0
            video.codec_context.thread_count = 2
            streams = [original]
            audio, resampler = None, None
            if source.streams.audio:
                streams.append(source.streams.audio[0])
                audio = dest.add_stream('libopus', rate=48000)
                audio.layout = 'stereo' if len(streams[1].layout.channels)>1 else 'mono'
                audio.bit_rate = 96000
                resampler = av.AudioResampler(format='flt', layout=audio.layout, rate=48000)
            count = 0
            for packet in source.demux(streams):
                if stopping(): raise InterruptedError('应用退出，预览缓存未完成')
                for frame in packet.decode():
                    if isinstance(frame, av.VideoFrame):
                        for encoded in video.encode(frame.reformat(video.width, video.height, 'yuv420p')):
                            dest.mux(encoded)
                        count += 1
                    elif audio:
                        for converted in resampler.resample(frame):
                            for encoded in audio.encode(converted): dest.mux(encoded)
            if not count: raise ValueError('视频没有可解码帧')
            for encoded in video.encode(): dest.mux(encoded)
            if audio:
                for converted in resampler.resample(None):
                    for encoded in audio.encode(converted): dest.mux(encoded)
                for encoded in audio.encode(): dest.mux(encoded)
        temporary.replace(target)
        return target.relative_to(project.root).as_posix()
    finally:
        if temporary.exists(): temporary.unlink()


class PreviewCache(QObject):
    ready = Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pending = set()
        self.errors = {}
        self.tasks = queue.Queue()
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self.run, name='xy-preview', daemon=True)
        self.thread.start()

    def request(self, project, relative):
        target = preview_path(project, relative)
        key = str(target)
        if target.exists(): return target.relative_to(project.root).as_posix(), ''
        if key in self.errors: return '', self.errors[key]
        if key not in self.pending:
            self.pending.add(key)
            self.tasks.put((project, relative, key))
        return '', '正在准备兼容预览'

    def run(self):
        while not self.stopping.is_set():
            try: project, relative, key = self.tasks.get(timeout=.5)
            except queue.Empty: continue
            try: transcode(project, relative, self.stopping.is_set)
            except Exception as e: self.errors[key] = '预览转换失败：'+str(e)
            finally:
                self.pending.discard(key)
                if not self.stopping.is_set(): self.ready.emit()

    def close(self):
        self.stopping.set()
