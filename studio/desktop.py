"""The only formal desktop entry: Vue in a web container, Python bridge in-process."""
import argparse
import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot, QUrl, QFile, QIODevice, QTimer, QTranslator, QStandardPaths
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineScript, QWebEngineProfile
from PySide6.QtWebChannel import QWebChannel

from .service import StudioService
from .media_server import MediaServer
from . import __version__


class Bridge(QObject):
    reply = Signal(str)
    stateChanged = Signal(str)
    notification = Signal(str)
    def __init__(self, service, local_commands=None):
        super().__init__()
        self.service = service
        self.local_commands = local_commands or {}
        service.changed.connect(self.stateChanged)
        service.notification.connect(self.notification)

    @Slot(str)
    def request(self, wire):
        ident = None
        try:
            if len(wire) > 4*1024*1024: raise ValueError('操作数据过大')
            request = json.loads(wire)
            ident = request['id']
            if not isinstance(ident, str) or not isinstance(request['command'], str) or not isinstance(request.get('payload', {}), dict):
                raise ValueError('接口请求格式错误')
            local = self.local_commands.get(request['command'])
            result = local() if local else self.service.dispatch(request['command'], request.get('payload', {}))
            response = {'id':ident, 'ok':True, 'result':result}
        except Exception as e:
            response = {'id':ident, 'ok':False, 'error':str(e)}
        self.reply.emit(json.dumps(response, ensure_ascii=False))


class LocalPage(QWebEnginePage):
    def __init__(self, profile, origin, service, parent):
        super().__init__(profile, parent)
        self.origin = origin
        self.service = service
    def acceptNavigationRequest(self, url, kind, main):
        if url.toString().startswith(self.origin+'/') or url.toString() == self.origin:
            return True
        if kind == QWebEnginePage.NavigationTypeLinkClicked:
            try:self.service.dispatch('link.open', {'url':url.toString()})
            except ValueError as e:self.service.notify(e)
        return False
    def javaScriptConsoleMessage(self, level, message, line, source):
        # Do not log bridge payloads or credentials. Show renderer errors explicitly.
        if level == QWebEnginePage.ErrorMessageLevel:
            self.service.last_error = f'界面脚本错误：{message[:800]}'
            self.service.notify(self.service.last_error)


class Desktop(QMainWindow):
    def __init__(self, frontend, project=None, service=None, lan_control=None):
        super().__init__()
        self.setWindowTitle('XY Studio · v'+__version__)
        self.setMinimumSize(900, 620)
        self.resize(1600, 980)
        self.owns_service = service is None
        self.service = service or StudioService(self)
        self.server = MediaServer(self.service, frontend)
        self.lan_control = lan_control
        self.bridge = Bridge(self.service, {'lan.open': self.open_lan})
        self.channel = QWebChannel(self)
        self.channel.registerObject('studio', self.bridge)
        self.profile = QWebEngineProfile(self)
        self.page = LocalPage(self.profile, self.server.base, self.service, self)
        self.page.setWebChannel(self.channel)
        script = QWebEngineScript()
        script.setName('xy-webchannel')
        script.setInjectionPoint(QWebEngineScript.DocumentCreation)
        script.setWorldId(QWebEngineScript.MainWorld)
        file = QFile(':/qtwebchannel/qwebchannel.js')
        if not file.open(QIODevice.ReadOnly):raise RuntimeError('无法读取 Qt WebChannel 脚本')
        script.setSourceCode(bytes(file.readAll()).decode('utf-8'));file.close()
        self.page.scripts().insert(script)
        self.view = QWebEngineView(self)
        self.view.setPage(self.page)
        self.view.setAcceptDrops(False)
        self.setCentralWidget(self.view)
        self.service.exit_requested.connect(self.close)
        self.service.changed.connect(self.title_from_state)
        if project:self.service.load(project)
        self.view.load(QUrl(self.server.base+'/'))
        self.stopped = False
    def open_lan(self):
        if self.lan_control is None:
            try:
                from .lan.desktop_control import DesktopLanControl
                self.lan_control = DesktopLanControl(self.service, self)
            except Exception as exc:
                import traceback
                log = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))/'lan-startup-error.txt'
                log.parent.mkdir(parents=True, exist_ok=True)
                log.write_text(traceback.format_exc(), encoding='utf-8')
                raise RuntimeError(f'手机连接初始化失败：{exc}。诊断记录：{log}') from exc
        self.lan_control.show()
        self.lan_control.raise_()
        self.lan_control.activateWindow()
        return True
    def title_from_state(self, raw):
        p=json.loads(raw)['project']
        self.setWindowTitle('XY Studio'+(' · '+p['name'] if p else '')+' · v'+__version__)
    def closeEvent(self, event):
        if not self.owns_service:
            self.hide()
            event.ignore()
            return
        if not self.stopped:
            try:
                self.service.shutdown()
            except Exception as e:
                self.service.closing = False
                self.service.last_error = '退出前保存失败：'+str(e)
                self.service.notify(self.service.last_error)
                self.service.publish()
                event.ignore()
                return
            self.stopped = True
            if self.lan_control is not None:
                self.lan_control.stop()
            self.view.stop()
            self.server.close()
            self.view.setPage(None)
            self.page.deleteLater()
        event.accept()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('project', nargs='?')
    parser.add_argument('--debug-port', type=int, help='Explicit local QA only; disabled in normal launches')
    args=parser.parse_args()
    if args.debug_port:
        os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = '127.0.0.1:'+str(args.debug_port)
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('XiYi.XYStudio')
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))
    frontend=root/'frontend'/'dist'
    if not (frontend/'index.html').is_file():raise RuntimeError('Vue 前端未构建，请先运行 npm --prefix frontend run build')
    app=QApplication(sys.argv);app.setApplicationName('XY Studio')
    app.setWindowIcon(QIcon(str(root/'studio/assets/xy-studio.ico')))
    translator=QTranslator(app)
    if translator.load(str(root/'studio/assets/qtbase_zh_CN.qm')):app.installTranslator(translator)
    app.zh_translator=translator
    window=Desktop(frontend,args.project)
    window.show()
    return app.exec()
