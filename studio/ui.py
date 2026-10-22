import copy,json,os,sys,html,re
from dataclasses import asdict
from pathlib import Path
import keyring
from PySide6.QtCore import Qt,QThread,Signal,QUrl,QSettings,QTimer,QTranslator
from PySide6.QtGui import QPixmap,QDesktopServices,QAction,QIcon
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QPushButton,QLabel,QLineEdit,QTextEdit,QPlainTextEdit,QTabWidget,QScrollArea,QGroupBox,QDialog,QFormLayout,QComboBox,QDoubleSpinBox,QSpinBox,QCheckBox,QDialogButtonBox,QFileDialog,QMessageBox,QInputDialog,QMenu,QDockWidget,QListWidget,QListWidgetItem,QAbstractItemView,QTextBrowser,QProgressBar,QTableWidget,QTableWidgetItem,QHeaderView,QStackedWidget,QFrame,QSizePolicy)
from PySide6.QtMultimedia import QMediaPlayer,QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from .storage import Project,uid,now,atomic_json
from .workflows import Generation,MODES,RATIOS,STYLES,resolution,frames
from .comfy import Comfy,execute
from .deepseek import chat,validate_action,list_models,DEFAULT_MODELS
from .research import safe_link
from .media import video_poster
from . import __version__
from .action_targets import resolve_target
from .chat_view import transcript_html
from .image_viewer import ImageThumbnail,ImageViewer
from .theme import QSS
from .workspace import WorkspaceCard,AssetGrid,ShotTimeline,label,action_button

def button(text,fn):
    b=QPushButton(text); b.clicked.connect(fn);return b
def message(parent,e):
    d=QMessageBox(QMessageBox.Warning,'提示',str(e),QMessageBox.Ok,parent);d.button(QMessageBox.Ok).setText('知道了');d.exec()
def scroll(widget):
    s=QScrollArea();s.setWidgetResizable(True);s.setWidget(widget);return s

class Worker(QThread):
    progress=Signal(str); result=Signal(object); failed=Signal(str)
    def __init__(self,fn): super().__init__();self.fn=fn
    def run(self):
        try:self.result.emit(self.fn(self))
        except Exception as e:self.failed.emit(str(e))

class GenerationDialog(QDialog):
    def __init__(self,project,g,parent=None,target=None):
        super().__init__(parent);self.project=project;self.g=g
        self.target=target;self.prompt_mode=g.mode;self.prompt_drafts={g.mode:g.prompt}
        self.setWindowTitle('生成参数 · 提交前检查');self.resize(640,760)
        outer=QVBoxLayout(self);body=QWidget();form=QFormLayout(body);self.form=form;outer.addWidget(scroll(body))
        self.target_label=QLabel('归属条目：'+project.get(target)['name']+'（'+target[:8]+'）' if target else '未指定条目')
        self.target_label.setWordWrap(True);form.addRow(self.target_label)
        self.mode=QComboBox()
        self.is_video=g.mode.startswith('h3')
        for k,v in MODES.items():
            if k.startswith('h3')==self.is_video:self.mode.addItem(v,k)
        self.mode.setCurrentIndex(self.mode.findData(g.mode));form.addRow('视频工作流' if self.is_video else '图片工作流',self.mode)
        self.prompt=QPlainTextEdit(g.prompt);self.prompt.setMinimumHeight(110);form.addRow('提示词',self.prompt)
        self.ratio=QComboBox();self.ratio.addItems(RATIOS);self.ratio.setCurrentText(g.ratio);form.addRow('图片 / 视频比例',self.ratio)
        self.mp=QDoubleSpinBox();self.mp.setRange(.1,16);self.mp.setSingleStep(.1);self.mp.setValue(g.megapixels);form.addRow('分辨率（MP）',self.mp)
        self.seconds=QDoubleSpinBox();self.seconds.setRange(.2,149);self.seconds.setValue(g.seconds);form.addRow('H3 时长（秒）',self.seconds)
        self.scale=QDoubleSpinBox();self.scale.setRange(1,8);self.scale.setSingleStep(.1);self.scale.setValue(g.scale);form.addRow('高清放大倍数',self.scale)
        self.seed=QLineEdit(str(g.seed));form.addRow('种子',self.seed)
        self.steps=QSpinBox();self.steps.setRange(0,100);self.steps.setSpecialValueText('沿用工作流默认');self.steps.setValue(g.steps);form.addRow('采样步数',self.steps)
        self.cinema=QCheckBox('启用电影质感 LoRA（普通 H3）');self.cinema.setChecked(g.cinema);form.addRow(self.cinema)
        self.strength=QDoubleSpinBox();self.strength.setRange(0,2);self.strength.setSingleStep(.1);self.strength.setValue(g.cinema_strength);form.addRow('电影 LoRA 强度',self.strength)
        self.quad=QCheckBox('启用角色四视图 LoRA');self.quad.setChecked(g.quad_lora);form.addRow(self.quad)
        self.int8=QCheckBox('Qwen 使用本机 INT8 模型（省显存）');self.int8.setChecked(g.qwen_int8);form.addRow(self.int8)
        self.styles={}
        group=QGroupBox('Krea2 风格 LoRA · 可分别启停');self.style_group=group;gl=QGridLayout(group)
        for i,name in enumerate(STYLES):
            cb=QCheckBox(name);cb.setChecked(name in g.styles);gl.addWidget(cb,i//3,i%3);self.styles[name]=cb
        form.addRow(group)
        self.refs=QListWidget();self.refs.setMinimumHeight(90)
        for r in g.references:self.refs.addItem(r)
        form.addRow('参考图（按顺序；首尾帧为前两张）',self.refs)
        self.available=QComboBox()
        for kind in ('characters','scenes','shots'):
            for item in project.data[kind]:
                if item['image']:self.available.addItem(item['name'],item['image'])
        source_row=QWidget();sl=QHBoxLayout(source_row);sl.addWidget(self.available);sl.addWidget(button('加入参考',self.add_existing));form.addRow('项目素材',source_row)
        row=QWidget();rl=QHBoxLayout(row);rl.addWidget(button('导入图片',self.add_refs));rl.addWidget(button('移除所选',self.remove_ref));rl.addWidget(button('上移',lambda:self.move_ref(-1)));rl.addWidget(button('下移',lambda:self.move_ref(1)));form.addRow(row)
        self.reference_rows=(self.refs,source_row,row)
        self.summary=QLabel();self.summary.setWordWrap(True);form.addRow(self.summary)
        for w in (self.mp,self.seconds,self.scale):w.valueChanged.connect(self.preview)
        self.ratio.currentTextChanged.connect(self.preview);self.mode.currentIndexChanged.connect(self.preview)
        self.mode.currentIndexChanged.connect(self.restore_prompt)
        self.cinema.toggled.connect(self.preview)
        self.preview()
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Ok).setText('加入生成队列');buttons.button(QDialogButtonBox.Cancel).setText('取消生成');buttons.accepted.connect(self.accept_valid);buttons.rejected.connect(self.reject);outer.addWidget(buttons)
    def add_refs(self):
        paths,_=QFileDialog.getOpenFileNames(self,'选择参考图片','','图片 (*.png *.jpg *.jpeg *.webp)')
        for p in paths:self.refs.addItem(self.project.import_file(p))
        self.preview()
    def restore_prompt(self):
        self.prompt_drafts[self.prompt_mode]=self.prompt.toPlainText();self.prompt_mode=self.mode.currentData()
        saved=self.project.last_prompt(self.target,self.prompt_mode) if self.target else ''
        self.prompt.setPlainText(self.prompt_drafts.get(self.prompt_mode,saved or self.prompt.toPlainText()))
    def add_existing(self):
        if self.available.currentData():self.refs.addItem(self.available.currentData());self.preview()
    def remove_ref(self):
        if self.refs.currentRow()>=0:self.refs.takeItem(self.refs.currentRow());self.preview()
    def move_ref(self,offset):
        i=self.refs.currentRow();j=i+offset
        if i>=0 and 0<=j<self.refs.count():self.refs.insertItem(j,self.refs.takeItem(i));self.refs.setCurrentRow(j);self.preview()
    def preview(self,*_):
        mode=self.mode.currentData();w,h=resolution(self.ratio.currentText(),self.mp.value(),32 if mode.startswith(('h3','qwen')) else 8)
        is_video=mode.startswith('h3')
        self.seconds.setEnabled(is_video);self.cinema.setEnabled(is_video);self.strength.setEnabled(is_video and self.cinema.isChecked())
        self.quad.setEnabled(mode=='quad');self.int8.setEnabled(mode.startswith('qwen'))
        self.scale.setEnabled(mode=='upscale');self.mp.setEnabled(mode!='upscale');self.ratio.setEnabled(mode!='upscale')
        for cb in self.styles.values():cb.setEnabled(mode=='krea')
        for widget,visible in ((self.seconds,is_video),(self.cinema,is_video),(self.strength,is_video),(self.quad,mode=='quad'),(self.int8,mode.startswith('qwen')),(self.scale,mode=='upscale'),(self.style_group,mode=='krea'),(self.mp,mode!='upscale'),(self.ratio,mode!='upscale'),(self.prompt,mode!='upscale')):
            self.form.setRowVisible(widget,visible)
        for widget in self.reference_rows:self.form.setRowVisible(widget,mode not in ('qwen','krea','h3_t2v'))
        text=f'输出 {w} × {h}。'
        if is_video:text+=f'H3 {frames(self.seconds.value())} 帧 / 24fps ≈ {frames(self.seconds.value())/24:.2f} 秒。修改时长后请核对提示词时间线。视频建议先低分辨率、短时长测试；高规格未验证。'
        if mode=='upscale':text='请选择一张图片，按原图尺寸放大。'
        if mode=='upscale' and self.refs.count():
            pix=QPixmap(str(self.project.file(self.refs.item(0).text())))
            text=f'预计放大至 {int(pix.width()*self.scale.value())} × {int(pix.height()*self.scale.value())}（以实际输出为准）。'
        if mode=='qwen_edit':text+=' 主参考图按此尺寸居中裁剪后编辑。'
        self.summary.setText(text)
    def accept_valid(self):
        try:
            self.g=Generation(mode=self.mode.currentData(),prompt=self.prompt.toPlainText(),ratio=self.ratio.currentText(),megapixels=self.mp.value(),seconds=self.seconds.value(),seed=int(self.seed.text()),steps=self.steps.value(),cinema=self.cinema.isChecked(),cinema_strength=self.strength.value(),quad_lora=self.quad.isChecked(),qwen_int8=self.int8.isChecked(),styles=[k for k,v in self.styles.items() if v.isChecked()],scale=self.scale.value(),references=[self.refs.item(i).text() for i in range(self.refs.count())])
            if self.g.mode in ('qwen','krea','h3_t2v'):self.g.references=[]
            self.g.validate()
            for r in self.g.references:
                if not self.project.file(r).is_file():raise ValueError('参考图不存在：'+r)
            self.accept()
        except Exception as e:message(self,e)

class TaskDialog(QDialog):
    def __init__(self,studio):
        super().__init__(studio);self.studio=studio;self.setWindowTitle('任务管理 · 当前项目全部角色 / 场景 / 分镜');self.resize(980,650)
        layout=QVBoxLayout(self);self.summary=QLabel();layout.addWidget(self.summary)
        self.filter=QComboBox();self.filter.addItems(['全部','未完成','已完成','失败 / 未知','已取消']);self.filter.currentIndexChanged.connect(self.refresh_jobs);layout.addWidget(self.filter)
        self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['条目','工作流','状态','当前节点进度','创建时间']);self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.setSelectionMode(QAbstractItemView.SingleSelection);self.table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);layout.addWidget(self.table)
        self.raw_details=QCheckBox('显示原始任务记录（排查问题）');self.raw_details.toggled.connect(self.show_details);layout.addWidget(self.raw_details)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details);self.table.itemSelectionChanged.connect(self.show_details)
        row=QHBoxLayout();layout.addLayout(row)
        for label,fn in [('暂停 / 继续待执行队列',self.pause),('取消所选',self.cancel),('恢复查询',self.resume),('再次生成（审阅参数）',self.retry),('打开结果',self.open_result)]:row.addWidget(button(label,fn))
        self.refresh_jobs()
    def chosen(self):
        cell=self.table.item(self.table.currentRow(),0)
        return next((j for j in self.studio.project.data['jobs'] if cell and j['id']==cell.data(Qt.UserRole)),None)
    def refresh_jobs(self):
        current=self.chosen();ident=current['id'] if current else None
        jobs=self.studio.project.data['jobs'];f=self.filter.currentIndex()
        shown=[j for j in jobs if f==0 or (f==1 and j['status'] not in ('completed','cancelled')) or (f==2 and j['status']=='completed') or (f==3 and j['status'] in ('failed','unknown','detached')) or (f==4 and j['status']=='cancelled')]
        self.summary.setText(f"总任务 {len(jobs)} · 已完成 {sum(j['status']=='completed' for j in jobs)} · 待执行 {sum(j['status']=='new' for j in jobs)} · "+('队列已暂停（当前任务继续）' if self.studio.project.data.get('queue_paused') else '队列可执行'))
        self.table.blockSignals(True);self.table.setRowCount(len(shown))
        for i,j in enumerate(shown):
            try:name=self.studio.project.get(j['target'])['name']
            except ValueError:name='已删除条目'
            p=j.get('progress');progress=f"{j.get('node','')} {p['value']}/{p['max']}" if p else '—'
            state={'new':'待执行','queued':'后端排队','submitting':'提交中','running':'运行中','downloading':'保存结果','completed':'完成','failed':'失败','unknown':'状态未知','detached':'已断开','cancelled':'已取消','cancel_requested':'正在取消'}.get(j['status'],j['status'])
            for k,value in enumerate((name,MODES.get(j['generation']['mode'],j['generation']['mode']),state,progress,j.get('created','')[:19])):
                cell=QTableWidgetItem(value);cell.setData(Qt.UserRole,j['id']);self.table.setItem(i,k,cell)
            if j['id']==ident:self.table.selectRow(i)
        self.table.blockSignals(False)
        if not ident and shown:self.table.selectRow(0)
        self.show_details()
    def show_details(self):
        j=self.chosen();text=''
        if j:
            if self.raw_details.isChecked():text=json.dumps(j,ensure_ascii=False,indent=2)
            else:
                try:name=self.studio.project.get(j['target'])['name']
                except ValueError:name='已删除条目'
                g=j['generation'];state=self.table.item(self.table.currentRow(),2).text()
                text=f"条目：{name}\n工作流：{MODES.get(g['mode'],g['mode'])}\n状态：{state}\n创建时间：{j.get('created','未记录')}\n"
                if g.get('ratio'):text+=f"比例：{g['ratio']} · 分辨率：{g.get('megapixels','默认')} MP\n"
                if g['mode'].startswith('h3') and 'seconds' in g:text+=f"预计视频时长：{frames(g['seconds'])/24:.2f} 秒\n"
                if g['mode']=='upscale':text+=f"放大倍数：{g.get('scale','默认')}\n"
                text+=f"参考图：{len(g.get('references',[]))} 张 · 已保存结果：{len(j.get('outputs',[]))} 个\n\n提示词\n{g.get('prompt','')}"
                if j.get('error'):text+='\n\n错误信息（可通过恢复查询检查后端结果）\n'+j['error']
        if self.details.toPlainText()!=text:self.details.setPlainText(text)
    def pause(self):
        p=self.studio.project;p.data['queue_paused']=not p.data.get('queue_paused',False);p.save();self.studio.start_next();self.refresh_jobs()
    def cancel(self):
        j=self.chosen()
        if j:
            try:self.studio.cancel_job(j)
            except Exception as e:message(self,e)
        self.refresh_jobs()
    def resume(self):
        j=self.chosen()
        if j and j.get('prompt_id') and not self.studio.active and j['status'] in ('failed','unknown','detached','queued','running'):self.studio.start_job(j)
    def retry(self):
        j=self.chosen()
        if not j:return
        if j['status'] not in ('completed','cancelled'):
            message(self,'状态不确定或失败的任务请先恢复查询，核对后再手动生成，避免重复提交。');return
        try:self.studio.generate(self.studio.project.get(j['target']),j['generation']['mode'],Generation(**j['generation']))
        except Exception as e:message(self,e)
    def open_result(self):
        j=self.chosen()
        if j and j.get('outputs'):QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.studio.project.file(j['outputs'][0]))))

class Studio(QMainWindow):
    def __init__(self,project_path=None):
        super().__init__();self.settings=QSettings('XiYi','AIStoryStudio');self.project=None;self.active=None;self.chat_worker=None;self.model_worker=None;self.context_ids=[]
        self.jobs_dialog=None
        self.selected_id=None;self.collapsed_shots=set();self.card_widgets={};self.page_scrolls={};self.timeline=None;self.ui_project_root=None
        self.applying_chat=False;self.chat_finish_pending=False;self.chat_continue=False;self.chat_rounds=0;self.chat_expanded=set();self.chat_render_key=None
        self.progress_bar=QProgressBar();self.progress_bar.setMinimumWidth(230);self.statusBar().addPermanentWidget(self.progress_bar)
        self.task_timer=QTimer(self);self.task_timer.timeout.connect(self.update_task_status);self.task_timer.start(700)
        self.setWindowTitle('XY Studio · v'+__version__);self.resize(1600,980);self.setMinimumSize(900,620);self.setStyleSheet(QSS)
        screen=self.screen().availableGeometry();self.resize(max(900,min(1600,screen.width()-60)),max(620,min(980,screen.height()-80)))
        self.tabs=QTabWidget();self.tabs.tabBar().hide()
        shell=QWidget();shell.setObjectName('workspaceShell');shell_layout=QHBoxLayout(shell);shell_layout.setContentsMargins(0,0,0,0);shell_layout.setSpacing(0)
        sidebar=QWidget();sidebar.setObjectName('sidebar');sidebar.setFixedWidth(154);sl=QVBoxLayout(sidebar);sl.setContentsMargins(12,12,12,12)
        sl.addWidget(label('XY Studio','brand'));sl.addWidget(label('故事创作工作台'))
        self.navigation=QListWidget();self.navigation.setObjectName('navigation');self.navigation.addItems(['项目概览','角色资产','场景资产','分镜工作区','任务与历史','全局设置']);sl.addWidget(self.navigation)
        sl.addWidget(label('素材 → 镜头 → 视频'));sl.addWidget(label('v'+__version__))
        shell_layout.addWidget(sidebar);self.workspace_stack=QStackedWidget();self.overview=QWidget();self.overview_layout=QVBoxLayout(self.overview);self.workspace_stack.addWidget(self.overview);self.workspace_stack.addWidget(self.tabs);self.tasks_page=QWidget();self.tasks_layout=QVBoxLayout(self.tasks_page);self.workspace_stack.addWidget(self.tasks_page);shell_layout.addWidget(self.workspace_stack,1);self.setCentralWidget(shell)
        self.navigation.currentRowChanged.connect(self.navigate)
        toolbar=self.addToolBar('项目')
        for title,fn in [('新建项目',self.new_project),('打开项目',self.open_project),('保存',self.save),('设置',self.configure),('任务管理',self.show_jobs),('AI 对话',self.toggle_chat)]:
            a=QAction(title,self);a.triggered.connect(fn);toolbar.addAction(a)
        self.dock=QDockWidget('AI 创作助手 · DeepSeek',self);self.dock.setMinimumWidth(300);self.dock.setFeatures(QDockWidget.DockWidgetClosable);self.dock.setAllowedAreas(Qt.RightDockWidgetArea)
        chatbox=QWidget();cl=QVBoxLayout(chatbox);cl.setContentsMargins(12,8,12,12);cl.setSpacing(10)
        options=QHBoxLayout();self.model_picker=QComboBox();self.model_picker.addItems(self.settings.value('model_list',DEFAULT_MODELS,type=list))
        current=self.settings.value('model','deepseek-flash')
        if self.model_picker.findText(current)<0:self.model_picker.addItem(current)
        self.model_picker.setCurrentText(current);self.model_picker.currentTextChanged.connect(lambda m:self.settings.setValue('model',m))
        options.addWidget(self.model_picker);self.model_refresh=button('刷新模型',self.refresh_models);options.addWidget(self.model_refresh);cl.addLayout(options)
        self.online=QCheckBox('允许 AI 联网检索');self.online.setChecked(self.settings.value('online_search',True,type=bool));self.online.toggled.connect(lambda value:self.settings.setValue('online_search',value));cl.addWidget(self.online)
        self.agent_status=QLabel('技能按需读取 · 联网使用同一 DeepSeek Key');self.agent_status.setWordWrap(True);cl.addWidget(self.agent_status)
        self.transcript=QTextBrowser();self.transcript.setOpenLinks(False);self.transcript.anchorClicked.connect(self.chat_link);cl.addWidget(self.transcript)
        nav=QHBoxLayout();self.my_messages=QComboBox();self.my_messages.setMinimumWidth(160);self.my_messages.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon);self.my_messages.activated.connect(self.jump_user);nav.addWidget(self.my_messages,1);nav.addWidget(button('最新消息',self.chat_latest));cl.addLayout(nav)
        self.context_label=QLabel('右击素材卡可发送给 AI');self.context_label.setWordWrap(True);cl.addWidget(self.context_label);cl.addWidget(button('清除素材上下文',self.clear_context))
        self.input=QPlainTextEdit();self.input.setMaximumHeight(120);self.input.setPlaceholderText('描述故事或修改目标……');cl.addWidget(self.input)
        self.send=button('发送',self.send_chat);self.send.setProperty('primary',True);cl.addWidget(self.send)
        cl.addWidget(button('导入 AI 操作建议',self.import_agent))
        self.dock.setWidget(chatbox);self.addDockWidget(Qt.RightDockWidgetArea,self.dock)
        self.resizeDocks([self.dock],[350],Qt.Horizontal)
        if project_path:self.load_project(project_path)
        else:self.refresh()
    def busy(self):return bool(self.active or self.chat_worker or self.model_worker)
    def guard(self):
        if self.busy():message(self,'任务运行期间请等待完成再切换项目');return False
        return True
    def new_project(self):
        if not self.guard():return
        path=QFileDialog.getExistingDirectory(self,'选择新项目文件夹')
        if path:
            try:
                if self.jobs_dialog:self.jobs_dialog.close()
                self.project=Project(path,True);self.context_ids=[];self.refresh()
            except Exception as e:message(self,e)
    def open_project(self):
        if not self.guard():return
        path,_=QFileDialog.getOpenFileName(self,'打开项目','','项目 (project.json)')
        if path:self.load_project(Path(path).parent)
    def load_project(self,path):
        try:
            if self.jobs_dialog:self.jobs_dialog.close()
            self.project=Project(path);self.context_ids=[]
            # Job journals are authoritative for crash recovery.
            for j in self.project.data['jobs']:
                jp=self.project.file('jobs/'+j['id']+'.json')
                if jp.exists():j.update(json.loads(jp.read_text(encoding='utf-8')))
                if j.get('status')=='completed':
                    for p in j.get('outputs',[]):self.project.attach_output(j,p)
            self.refresh()
        except Exception as e:message(self,e)
    def save(self):
        if self.project:self.project.save();self.statusBar().showMessage('项目已保存',3000)
    def toggle_chat(self):self.dock.setVisible(not self.dock.isVisible())
    def navigate(self,index):
        if index==0:self.workspace_stack.setCurrentIndex(0)
        elif 1<=index<=3:
            self.workspace_stack.setCurrentIndex(1);self.tabs.setCurrentIndex(index-1)
        elif index==4:self.show_jobs()
        elif index==5:
            self.configure()
            self.navigation.blockSignals(True);self.navigation.setCurrentRow(0 if self.workspace_stack.currentIndex()==0 else 4 if self.workspace_stack.currentIndex()==2 else self.tabs.currentIndex()+1);self.navigation.blockSignals(False)
    def refresh_overview(self):
        for row in range(1,5):
            item=self.navigation.item(row);item.setFlags(item.flags()|Qt.ItemIsEnabled if self.project else item.flags()&~Qt.ItemIsEnabled)
        while self.overview_layout.count():
            part=self.overview_layout.takeAt(0)
            if part.widget():part.widget().deleteLater()
        self.overview_layout.setContentsMargins(28,24,28,24);self.overview_layout.setSpacing(18)
        self.overview_layout.addWidget(label('项目概览','pageTitle'))
        title=self.project.data['title'] if self.project else '从一个故事开始'
        self.overview_layout.addWidget(label(title,'cardTitle'))
        self.overview_layout.addWidget(label(str(self.project.root) if self.project else '创建项目，整理角色与场景，再逐个镜头生成图片和视频。'))
        controls=QWidget();row=QHBoxLayout(controls);row.setContentsMargins(0,0,0,0)
        for text,fn in [('新建项目',self.new_project),('打开项目',self.open_project),('保存项目',self.save)]:row.addWidget(action_button(text,fn,text=='新建项目'))
        self.overview_layout.addWidget(controls)
        if self.project:
            counts=self.project.data
            for index,(kind,title,desc) in enumerate([('characters','01  角色资产','保存角色形象、描述和每次生成版本。'),('scenes','02  场景资产','准备可复用的环境与空间参考。'),('shots','03  分镜工作区','关联素材，生成分镜图，再制作视频。')],1):
                box=QFrame();box.setObjectName('overviewCard');v=QVBoxLayout(box);v.setContentsMargins(18,18,18,18);v.addWidget(label(title+f' · {len(counts[kind])}','cardTitle'));v.addWidget(label(desc));v.addWidget(action_button('进入工作区',lambda checked=False,i=index:self.navigation.setCurrentRow(i)));self.overview_layout.addWidget(box)
            self.overview_layout.addWidget(label(f"生成记录 {len(counts['jobs'])} 条 · 已完成 {sum(j['status']=='completed' for j in counts['jobs'])} 条；历史保存在各自素材和镜头中。"))
        self.overview_layout.addStretch()
    def item_status(self,ident):
        jobs=[j for j in self.project.data['jobs'] if j['target']==ident]
        if not jobs:return '未生成'
        j=jobs[-1];status={'new':'等待执行','submitting':'正在提交','queued':'后端排队','running':'生成中','downloading':'保存结果','completed':'已完成','failed':'失败 · 查看任务','unknown':'状态未知 · 恢复查询','detached':'已断开 · 恢复查询','cancelled':'已取消','cancel_requested':'取消中'}.get(j['status'],j['status'])
        if j.get('progress'):status+=f" {j['progress']['value']}/{j['progress']['max']}"
        return status
    def shot_duration(self,item):
        if item['video']:
            try:
                from .media import video_duration
                return f"{video_duration(self.project.file(item['video'])):.2f} 秒"
            except Exception:return '视频时长读取失败'
        jobs=[j for j in self.project.data['jobs'] if j['target']==item['id'] and j['generation']['mode'].startswith('h3')]
        return f"预计 {frames(jobs[-1]['generation']['seconds'])/24:.2f} 秒" if jobs else '时长待定'
    def refresh(self):
        index=self.tabs.currentIndex();positions={k:s.verticalScrollBar().value() for k,s in self.page_scrolls.items()}
        current_root=str(self.project.root) if self.project else None
        if current_root!=self.ui_project_root:
            self.selected_id=None;self.collapsed_shots.clear();positions={};self.ui_project_root=current_root
        self.card_widgets={};self.page_scrolls={};self.timeline=None
        while self.tabs.count():
            old=self.tabs.widget(0);self.tabs.removeTab(0);old.deleteLater()
        self.refresh_overview()
        if not self.project:
            self.navigation.setCurrentRow(0);self.render_chat();return
        self.setWindowTitle(f'XY Studio · {self.project.data["title"]} · v{__version__}')
        for kind,title in [('characters','角色资产'),('scenes','场景资产'),('shots','分镜工作区')]:
            page=QWidget();page.setObjectName('pageBody');layout=QVBoxLayout(page);layout.setContentsMargins(22,20,22,12);layout.setSpacing(12)
            header=QHBoxLayout();header.addWidget(label(title,'pageTitle'),1);header.addWidget(action_button('+ 新增'+{'characters':'角色','scenes':'场景','shots':'分镜'}[kind],lambda checked=False,k=kind:self.edit_item(k),True));layout.addLayout(header)
            layout.addWidget(label(f"{len(self.project.data[kind])} 个条目 · "+('素材 → 分镜图 → 视频 · 每次生成保留在原镜头中' if kind=='shots' else '选中素材与 AI 对话 · 双击图片查看 · 新版本保留历史')))
            if kind=='shots':
                story=QPlainTextEdit(self.project.data['story']);story.setPlaceholderText('故事描述：先写下这个短故事，再按顺序添加镜头。');story.setFixedHeight(74);story.textChanged.connect(lambda s=story:self.set_story(s.toPlainText()));layout.addWidget(story)
                self.timeline=ShotTimeline(self.project.data['shots'],{s['id']:self.shot_duration(s) for s in self.project.data['shots']});self.timeline.selected.connect(self.locate_shot);layout.addWidget(self.timeline)
            cards=[self.card(kind,item) for item in self.project.data[kind]]
            if kind=='shots':
                body=QWidget();v=QVBoxLayout(body);v.setContentsMargins(0,0,0,0);v.setSpacing(16)
                for c in cards:v.addWidget(c)
                if not cards:v.addWidget(label('还没有分镜。点击右上角“新增分镜”，或请 AI 根据故事创建。'))
                v.addStretch()
            else:
                body=QWidget();v=QVBoxLayout(body);v.setContentsMargins(0,0,0,0);v.addWidget(AssetGrid(cards))
                if not cards:v.addWidget(label('这里还没有素材。可以新建条目并导入图片，也可以请 AI 帮你创建。'))
                v.addStretch()
            sc=scroll(body);self.page_scrolls[kind]=sc;layout.addWidget(sc,1);self.tabs.addTab(page,title)
            QTimer.singleShot(0,sc,lambda widget=sc,value=positions.get(kind,0):widget.verticalScrollBar().setValue(value))
        self.tabs.setCurrentIndex(max(0,min(index,2)))
        if self.navigation.currentRow()<0:self.navigation.setCurrentRow(1)
        self.update_selection();self.render_chat()
        if self.navigation.currentRow()==4:self.show_jobs()
    def update_selection(self):
        valid={i['id']:i for k in ('characters','scenes','shots') for i in self.project.data[k]} if self.project else {}
        self.context_ids=[i for i in self.context_ids if i in valid]
        if self.selected_id not in valid:self.selected_id=None
        for ident,card in self.card_widgets.items():card.set_selected(ident==self.selected_id)
        if self.timeline:self.timeline.select(self.selected_id)
        text='当前选择：'+valid[self.selected_id]['name'] if self.selected_id else '点击素材或分镜卡片，选择 AI 操作对象'
        if self.context_ids:text+='\n附加素材：'+'、'.join(valid[i]['name'] for i in self.context_ids)
        self.context_label.setText(text)
    def select_item(self,ident):self.selected_id=ident;self.update_selection()
    def clear_context(self):self.context_ids=[];self.selected_id=None;self.update_selection()
    def locate_shot(self,ident):
        self.select_item(ident);self.navigation.setCurrentRow(3)
        if ident in self.card_widgets:self.page_scrolls['shots'].ensureWidgetVisible(self.card_widgets[ident],0,12)
    def fold_shot(self,ident,collapsed):
        if collapsed:self.collapsed_shots.add(ident)
        else:self.collapsed_shots.discard(ident)
    def set_story(self,text):self.project.data['story']=text;self.project.save()
    def thumbnail(self,relative,empty):
        label=ImageThumbnail(empty);label.setAlignment(Qt.AlignCenter);label.setFixedSize(240,240);label.setStyleSheet('QLabel {background:#edf0f4;border:1px solid #b7bcc6;border-radius:5px;}')
        if relative:
            pix=QPixmap(str(self.project.file(relative)))
            if not pix.isNull():
                label.setPixmap(pix.scaled(228,228,Qt.KeepAspectRatio,Qt.SmoothTransformation));label.setToolTip('双击放大查看');label.setCursor(Qt.PointingHandCursor);label.activated.connect(lambda:self.show_image(relative))
        return label
    def show_image(self,relative):
        try:
            d=ImageViewer(self.project.file(relative),QApplication.activeModalWidget() or self);d.setAttribute(Qt.WA_DeleteOnClose);d.show()
        except Exception as e:message(self,e)
    def card(self,kind,item):
        linked=[]
        for ident in item['materials']:
            try:linked.append(self.project.get(ident))
            except ValueError:linked.append({'id':ident,'name':'已移除素材','image':''})
        poster=''
        if item['video']:
            try:poster=video_poster(self.project,item['video'])
            except Exception:pass
        jobs=[j for j in self.project.data['jobs'] if j['target']==item['id']]
        references=jobs[-1]['generation'].get('references',[]) if jobs else []
        card=WorkspaceCard(kind,item,self.project.root,linked,poster,self.item_status(item['id']),item['id'] in self.collapsed_shots,references)
        card.file_requested.connect(self.show_image)
        card.selected.connect(self.select_item);card.folded.connect(self.fold_shot);card.action.connect(self.card_action);self.card_widgets[item['id']]=card;return card
    def card_action(self,action,ident):
        try:
            item=self.project.get(ident);kind=next(k for k in ('characters','scenes','shots') if any(i['id']==ident for i in self.project.data[k]))
            actions={'edit':lambda:self.edit_item(kind,item),'image':lambda:self.generate(item,self.image_mode(item)),'video':lambda:self.generate(item,'h3_i2v'),'view':lambda:self.show_image(item['image']) if item['image'] else None,'play':lambda:self.play(item['video']) if item['video'] else None,'history':lambda:self.versions(item),'context':lambda:self.add_context(item),'delete':lambda:self.delete(item),'import':lambda:self.import_image(item),'link':lambda:self.link_materials(item),'review':lambda:self.clear_review(item)}
            actions[action]()
        except Exception as e:message(self,e)
    def card_menu(self,box,pos,kind,item):
        m=QMenu(self)
        for name,fn in [('发送给 AI',lambda:self.add_context(item)),('生成历史',lambda:self.versions(item)),('删除条目',lambda:self.delete(item))]:m.addAction(name,fn)
        m.exec(box.mapToGlobal(pos))
    def delete(self,item):
        if any(j['target']==item['id'] and j['status'] in ('new','submitting','queued','running','downloading') for j in self.project.data['jobs']):
            message(self,'此条目仍有生成任务，请先完成或取消任务。');return
        affected=[s['name'] for s in self.project.data['shots'] if item['id'] in s['materials']]
        text='删除“'+item['name']+'”？素材文件和历史输出仍保留。'
        if affected:text+='\n同时解除以下分镜的素材引用，已有图片和视频保留：'+', '.join(affected)
        d=QMessageBox(QMessageBox.Question,'删除条目',text,QMessageBox.Yes|QMessageBox.No,self);d.button(QMessageBox.Yes).setText('确认删除');d.button(QMessageBox.No).setText('保留条目');d.setDefaultButton(QMessageBox.No)
        if d.exec()!=QMessageBox.Yes:return
        try:
            self.project.delete(item['id'],detach=True)
            self.context_ids=[i for i in self.context_ids if i!=item['id']]
            self.context_label.setText('右击素材卡可发送给 AI');self.refresh()
        except Exception as e:message(self,e)
    def clear_review(self,item):item['needs_review']=False;self.save();self.refresh()
    def edit_item(self,kind,item=None):
        if kind=='shots' and item is None:
            self.project.add('shots','');self.refresh();return
        d=QDialog(self);d.setWindowTitle('编辑条目');f=QFormLayout(d);name=QLineEdit(item['name'] if item else '');desc=QPlainTextEdit(item['description'] if item else '')
        if kind=='shots':name.setText(item.get('original_name','') if item else '');f.addRow('镜头名称（编号自动保留）',name)
        else:f.addRow('名称',name)
        f.addRow('描述',desc)
        bb=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);bb.button(QDialogButtonBox.Cancel).setText('取消');bb.button(QDialogButtonBox.Ok if bb.button(QDialogButtonBox.Ok) else QDialogButtonBox.Save).setText('保存');bb.accepted.connect(d.accept);bb.rejected.connect(d.reject);f.addRow(bb)
        if d.exec():
            if item:
                item['description']=desc.toPlainText()
                item['original_name' if kind=='shots' else 'name']=name.text() or ('未命名' if kind!='shots' else '')
                self.project.mark_dependents(item['id'])
            else:self.project.add(kind,name.text(),desc.toPlainText())
            self.refresh()
    def import_image(self,item):
        path,_=QFileDialog.getOpenFileName(self,'导入图片','','图片 (*.png *.jpg *.jpeg *.webp)')
        if path:
            try:
                r=self.project.import_file(path);item['image']=r;item['versions'].append({'id':uid(),'time':now(),'kind':'image','file':r,'intent':'导入图片'});self.project.mark_dependents(item['id']);self.save();self.refresh()
            except Exception as e:message(self,e)
    def link_materials(self,item):
        d=QDialog(self);d.setWindowTitle('关联素材');v=QVBoxLayout(d);checks=[]
        for a in self.project.data['characters']+self.project.data['scenes']:
            cb=QCheckBox(a['name']);cb.setChecked(a['id'] in item['materials']);v.addWidget(cb);checks.append((a['id'],cb))
        bb=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);bb.button(QDialogButtonBox.Cancel).setText('取消');bb.button(QDialogButtonBox.Ok if bb.button(QDialogButtonBox.Ok) else QDialogButtonBox.Save).setText('保存');bb.accepted.connect(d.accept);bb.rejected.connect(d.reject);v.addWidget(bb)
        if d.exec():item['materials']=[i for i,c in checks if c.isChecked()];self.save();self.refresh()
    def versions(self,item):
        d=QDialog(self);d.setWindowTitle(item['name']+' · 生成历史');d.resize(820,650);v=QVBoxLayout(d);ls=QListWidget();v.addWidget(ls)
        detail=QPlainTextEdit();detail.setReadOnly(True);v.addWidget(detail)
        for x in item['versions']:
            row=QListWidgetItem(x['time'][:19]+' · '+x['kind']+' · '+x.get('intent','')[:90])
            try:
                path=video_poster(self.project,x['file']) if x['kind']=='video' else x['file']
                row.setIcon(QIcon(str(self.project.file(path))))
            except Exception:pass
            ls.addItem(row)
        if not item['versions']:v.addWidget(QLabel('还没有生成结果；生成成功后会自动保存到这里。'))
        def selected():return item['versions'][ls.currentRow()] if ls.currentRow()>=0 else None
        def details():
            x=selected()
            if x:
                job=next((j for j in self.project.data['jobs'] if j['id']==x.get('job')),None)
                detail.setPlainText(json.dumps({'version':x,'generation':job.get('generation') if job else None},ensure_ascii=False,indent=2))
        ls.currentRowChanged.connect(details)
        if ls.count():ls.setCurrentRow(ls.count()-1)
        pending=[j for j in self.project.data['jobs'] if j['target']==item['id'] and j['status']!='completed']
        if pending:
            v.addWidget(QLabel('其他生成记录（未产生可用版本）'))
            records=QPlainTextEdit('\n'.join(j.get('created','')[:19]+' · '+j['generation']['mode']+' · '+j['status']+' · '+j.get('error','')[:200] for j in pending));records.setReadOnly(True);records.setMaximumHeight(100);v.addWidget(records)
        def preview():
            x=selected()
            if x:
                if x['kind']=='image':self.show_image(x['file'])
                else:self.play(x['file'])
        ls.itemDoubleClicked.connect(lambda _:preview())
        def restore():
            x=selected()
            if x:item[x['kind']]=x['file'];self.project.mark_dependents(item['id']);self.save();d.accept();self.refresh()
        v.addWidget(button('查看文件',preview));v.addWidget(button('设为当前版本',restore));d.exec()
    def play(self,path):
        d=QDialog(self);d.setWindowTitle('视频预览');d.resize(900,600);v=QVBoxLayout(d);screen=QVideoWidget();v.addWidget(screen)
        player=QMediaPlayer(d);audio=QAudioOutput(d);player.setAudioOutput(audio);player.setVideoOutput(screen);player.setSource(QUrl.fromLocalFile(str(self.project.file(path))))
        v.addWidget(button('播放 / 暂停',lambda:player.pause() if player.playbackState()==QMediaPlayer.PlayingState else player.play()));player.play();d.exec();player.stop()
    def generate(self,item,mode,g=None):
        if mode.startswith('h3') and not any(s['id']==item['id'] for s in self.project.data['shots']):raise ValueError('视频只能在分镜中生成，请先新增分镜并关联素材。')
        if g is None:
            refs=[item['image']] if item['image'] and mode in ('h3_i2v','upscale','quad','qwen_edit') else []
            g=Generation(mode=mode,prompt=self.project.last_prompt(item['id'],mode) or item['description'],references=refs,megapixels=.2 if mode.startswith('h3') else 1,seconds=2 if mode.startswith('h3') else 5)
        d=GenerationDialog(self.project,g,self,target=item['id'])
        if d.exec():
            j={'id':uid(),'target':item['id'],'generation':asdict(d.g),'materials':copy.deepcopy([self.project.get(i) for i in item['materials']]),'status':'new','created':now()}
            item.setdefault('last_prompts',{})[d.g.mode]=d.g.prompt
            self.project.data['jobs'].append(j);self.save();self.start_next()
            return j
        return None
    def image_mode(self,item):
        for j in reversed(self.project.data['jobs']):
            if j['target']==item['id'] and j['generation']['mode'] in ('qwen','qwen_edit','krea','quad'):return j['generation']['mode']
        return 'qwen_edit' if item['image'] else 'qwen'
    def start_next(self):
        if self.active or self.project.data.get('queue_paused'):return
        j=next((j for j in self.project.data['jobs'] if j['status']=='new'),None)
        if not j:return
        self.start_job(j)
    def start_job(self,j):
        self.active=j;client=Comfy(self.settings.value('comfy','http://127.0.0.1:8188'))
        # Worker owns a snapshot, main thread owns mutable project and UI.
        snapshot=Project(self.project.root);job=copy.deepcopy(j)
        self.worker=Worker(lambda w:execute(client,snapshot,job,w.progress.emit,w.isInterruptionRequested))
        self.worker.progress.connect(lambda s:self.job_progress(j,s))
        self.worker.result.connect(lambda outputs:self.job_result(j,job,outputs));self.worker.failed.connect(lambda e:self.job_error(j,job,e));self.worker.finished.connect(self.job_finished);self.worker.start()
    def job_progress(self,j,status):
        journal=self.project.file('jobs/'+j['id']+'.json')
        if journal.exists():j.update(json.loads(journal.read_text(encoding='utf-8')))
        self.project.save();self.statusBar().showMessage('生成任务：'+status)
    def job_result(self,j,snapshot,outputs):
        j.update(snapshot)
        if j.get('cancelled_by_user') and not outputs:j['status']='cancelled';atomic_json(self.project.file('jobs/'+j['id']+'.json'),j)
        for p in outputs:self.project.attach_output(j,p)
        self.save();self.refresh()
    def job_error(self,j,snapshot,e):j.update(snapshot);self.save();message(self,e)
    def job_finished(self):self.active=None;self.worker.deleteLater();self.start_next()
    def update_task_status(self):
        jobs=self.project.data['jobs'] if self.project else []
        pending=sum(j['status']=='new' for j in jobs)
        if self.active:
            j=self.active;p=j.get('progress');stage={'submitting':'提交中','queued':'后端排队','running':'运行中','downloading':'保存结果'}.get(j['status'],j['status'])
            if p and p.get('max',0)>0:
                self.progress_bar.setRange(0,int(p['max']));self.progress_bar.setValue(int(p['value']));self.progress_bar.setFormat(f"当前节点 {j.get('node','')}：%v/%m (%p%)")
            else:self.progress_bar.setRange(0,0);self.progress_bar.setFormat(stage)
            self.statusBar().showMessage(f'{stage} · 本地待执行 {pending}')
        else:
            self.progress_bar.setRange(0,1);self.progress_bar.setValue(0)
            self.progress_bar.setFormat(('队列已暂停' if self.project and self.project.data.get('queue_paused') else '空闲')+f' · 待执行 {pending}')
        if self.jobs_dialog and self.jobs_dialog.isVisible():self.jobs_dialog.refresh_jobs()
        if self.project:
            for ident,card in self.card_widgets.items():card.state.setText(self.item_status(ident))
    def cancel_job(self,j):
        if j['status']=='new':
            j['status']='cancelled';self.save();return
        if not j.get('prompt_id') or j['status'] not in ('queued','running','cancel_requested'):return
        result=Comfy(self.settings.value('comfy','http://127.0.0.1:8188')).cancel(j['prompt_id'])
        if result=='cancelled':
            j['cancelled_by_user']=True;j['status']='cancelled'
            if self.active and self.active['id']==j['id']:self.worker.requestInterruption()
            else:atomic_json(self.project.file('jobs/'+j['id']+'.json'),j)
        elif result=='cancel_requested':j['status']='cancel_requested'
        self.save()
    def show_jobs(self):
        if not self.project:return
        if self.jobs_dialog:self.jobs_dialog.close()
        while self.tasks_layout.count():
            entry=self.tasks_layout.takeAt(0)
            if entry.widget():entry.widget().deleteLater()
        self.jobs_dialog=TaskDialog(self);self.jobs_dialog.setWindowFlags(Qt.Widget)
        self.tasks_layout.addWidget(label('任务与历史','pageTitle'));self.tasks_layout.addWidget(scroll(self.jobs_dialog))
        self.workspace_stack.setCurrentIndex(2);self.navigation.blockSignals(True);self.navigation.setCurrentRow(4);self.navigation.blockSignals(False);self.jobs_dialog.show()
    def add_context(self,item):
        if item['id'] not in self.context_ids:self.context_ids.append(item['id'])
        self.select_item(item['id']);self.dock.show()
    def configure(self):
        d=QDialog(self);d.setWindowTitle('设置');f=QFormLayout(d)
        url=QLineEdit(self.settings.value('comfy','http://127.0.0.1:8188'));model=QComboBox();model.addItems([self.model_picker.itemText(i) for i in range(self.model_picker.count())]);model.setCurrentText(self.model_picker.currentText());key=QLineEdit();key.setEchoMode(QLineEdit.Password);key.setPlaceholderText('留空保留现有密钥；保存到 Windows 凭据管理器')
        f.addRow('ComfyUI 地址',url);f.addRow('DeepSeek 模型',model);f.addRow('DeepSeek API Key',key)
        f.addRow(QLabel('对话会将故事、条目描述和相对文件名发送给 DeepSeek；不上传图片像素。'))
        bb=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);bb.button(QDialogButtonBox.Cancel).setText('取消');bb.button(QDialogButtonBox.Ok if bb.button(QDialogButtonBox.Ok) else QDialogButtonBox.Save).setText('保存');bb.accepted.connect(d.accept);bb.rejected.connect(d.reject);f.addRow(bb)
        if d.exec():
            try:
                if key.text():keyring.set_password('AIStoryStudio','deepseek',key.text().strip())
                self.settings.setValue('comfy',url.text().strip());self.model_picker.setCurrentText(model.currentText())
            except Exception as e:message(self,e)
    def refresh_models(self):
        if self.model_worker:return
        key=keyring.get_password('AIStoryStudio','deepseek')
        if not key:message(self,'请先在设置中保存 DeepSeek API Key');return
        self.model_refresh.setEnabled(False);self.agent_status.setText('正在读取账户可用模型……')
        self.model_worker=Worker(lambda w:list_models(key));self.model_worker.result.connect(self.models_loaded);self.model_worker.failed.connect(lambda e:message(self,e));self.model_worker.finished.connect(self.models_finished);self.model_worker.start()
    def models_loaded(self,models):
        current=self.model_picker.currentText();self.model_picker.blockSignals(True);self.model_picker.clear();self.model_picker.addItems(models)
        if current in models:self.model_picker.setCurrentText(current)
        self.model_picker.blockSignals(False);self.settings.setValue('model_list',models);self.settings.setValue('model',self.model_picker.currentText());self.agent_status.setText('账户模型列表已更新')
    def models_finished(self):
        self.model_worker.deleteLater();self.model_worker=None;self.model_refresh.setEnabled(True)
    def chat_link(self,url):
        if url.scheme()=='xychat':
            try:index=int(url.path().split('/')[-1])
            except ValueError:return
            if index in self.chat_expanded:self.chat_expanded.remove(index)
            else:self.chat_expanded.add(index)
            self.render_chat();self.transcript.scrollToAnchor('message-'+str(index))
        elif safe_link(url.toString()):QDesktopServices.openUrl(url)
    def jump_user(self,index):
        target=self.my_messages.itemData(index)
        if target is not None:self.transcript.scrollToAnchor('message-'+str(target))
    def chat_latest(self):
        bar=self.transcript.verticalScrollBar();bar.setValue(bar.maximum())
    def render_chat(self):
        messages=self.project.data['chat'] if self.project else []
        project_id=self.project.data['id'] if self.project else None
        if getattr(self,'chat_project_id',None)!=project_id:
            self.chat_expanded.clear();self.chat_render_key=None;self.chat_project_id=project_id
        rendered,users=transcript_html(messages,self.chat_expanded)
        key=(project_id,rendered)
        if key==self.chat_render_key:return
        previous=self.transcript.verticalScrollBar().value();old_count=getattr(self,'chat_message_count',0)
        self.transcript.setHtml(rendered);self.chat_render_key=key;self.chat_message_count=len(messages)
        self.my_messages.blockSignals(True);self.my_messages.clear();self.my_messages.addItem('定位我的消息…',None)
        for index,title in users:self.my_messages.addItem(title,index)
        self.my_messages.blockSignals(False)
        if len(messages)!=old_count and users:self.transcript.scrollToAnchor('message-'+str(users[-1][0]))
        else:self.transcript.verticalScrollBar().setValue(previous)
    def send_chat(self):
        if not self.project or self.chat_worker:return
        text=self.input.toPlainText().strip()
        if not text:return
        try:
            key=keyring.get_password('AIStoryStudio','deepseek')
            if not key:raise ValueError('请先在设置中填写 DeepSeek API Key；目前可手动创建素材和生成。')
        except Exception as e:message(self,e);return
        self.project.data['chat'].append({'role':'user','content':text});self.save();self.input.clear();self.render_chat();self.chat_rounds=0;self.start_chat_request(key)
    def start_chat_request(self,key=None):
        key=key or keyring.get_password('AIStoryStudio','deepseek')
        self.send.setEnabled(False);self.chat_continue=False;self.chat_rounds+=1
        context=copy.deepcopy({k:self.project.data[k] for k in ('story','characters','scenes','shots')});context['selected_ids']=list(dict.fromkeys(([self.selected_id] if self.selected_id else [])+self.context_ids))
        history=copy.deepcopy(self.project.data['chat']);model=self.model_picker.currentText();online=self.online.isChecked()
        self.chat_worker=Worker(lambda w:chat(key,model,history,context,online=online,notify=w.progress.emit))
        self.chat_worker.progress.connect(self.agent_status.setText)
        self.chat_worker.result.connect(self.chat_result);self.chat_worker.failed.connect(lambda e:message(self,e));self.chat_worker.finished.connect(self.chat_finished);self.chat_worker.start()
    def chat_finished(self):
        if self.applying_chat:
            self.chat_finish_pending=True;return
        if not self.chat_worker:return
        self.chat_finish_pending=False
        self.chat_worker.deleteLater();self.chat_worker=None
        if self.chat_continue and self.chat_rounds<4:
            self.agent_status.setText('操作完成，AI 正在继续处理你的要求…');self.start_chat_request();return
        self.send.setEnabled(True);self.agent_status.setText('达到连续操作上限，请继续对话' if self.chat_continue else '本轮结束 · 请查看操作结果')
    def chat_result(self,msg):
        self.applying_chat=True
        try:self.apply_chat_result(msg)
        finally:
            self.applying_chat=False
            if self.chat_finish_pending:QTimer.singleShot(0,self.chat_finished)
    def apply_chat_result(self,msg):
        self.project.data['chat'].append(msg)
        calls=msg.get('tool_calls',[]);created={};all_applied=bool(calls);had_generation=False
        self.render_chat()
        for call in calls:
            name=call['function']['name'];args=json.loads(call['function']['arguments']);result='用户未采用此建议'
            try:args=resolve_target(name,args,calls,created,self.project.data["characters"]+self.project.data["scenes"]+self.project.data["shots"])
            except ValueError as e:
                result='操作未执行：'+str(e)
                self.project.data['chat'].append({'role':'tool','tool_call_id':call['id'],'content':result})
                all_applied=False;message(self,e);continue
            title={'add_item':'创建条目','update_item':'修改条目','set_story':'保存故事','generate':'生成图片 / 视频'}.get(name,name)
            approved=name=='generate'
            if not approved:
                d=QMessageBox(self);d.setWindowTitle('确认 AI 操作');d.setText(title+'：'+args.get('name',''))
                d.setInformativeText(args.get('description',args.get('text',''))[:1200]);d.setDetailedText(json.dumps(args,ensure_ascii=False,indent=2));d.setStandardButtons(QMessageBox.Apply|QMessageBox.Cancel)
                d.button(QMessageBox.Apply).setText('确认'+title);d.button(QMessageBox.Cancel).setText('取消本次操作')
                approved=d.exec()==QMessageBox.Apply
            if approved:
                try:
                    result=self.apply_action(name,args)
                    if name=='generate':had_generation=True
                    if name=='add_item':
                        created[call['id']]=json.loads(result)['id']
                        alias=args['name']
                        matching=[c for c in calls if c['function']['name']=='add_item' and json.loads(c['function']['arguments']).get('name')==alias]
                        if alias and len(matching)==1:created[alias]=json.loads(result)['id']
                except Exception as e:all_applied=False;result='操作失败：'+str(e);message(self,e)
            else:all_applied=False
            display=('已创建：'+args['name']) if name=='add_item' and call['id'] in created else result
            self.project.data['chat'].append({'role':'tool','tool_call_id':call['id'],'content':result,'_display':display})
        self.chat_continue=all_applied and not had_generation and bool(self.chat_worker)
        self.save();self.refresh()
    def import_agent(self):
        if not self.project or self.chat_worker:return
        path,_=QFileDialog.getOpenFileName(self,'导入子 agent 建议','','建议 (*.json)')
        if not path:return
        try:
            bundle=json.loads(Path(path).read_text(encoding='utf-8'))
            if bundle.get('project_id')!=self.project.data['id']:raise ValueError('建议属于其他项目，请在对应项目中导入。')
            msg=bundle['message']
            if msg.get('role')!='assistant':raise ValueError('建议消息格式错误')
            for call in msg.get('tool_calls',[]):validate_action(call['function']['name'],json.loads(call['function']['arguments']))
            msg=copy.deepcopy(msg);msg['content']='[临时子 agent：'+str(bundle.get('provider','未知'))+']\n'+(msg.get('content') or '')
            self.chat_result(msg)
        except Exception as e:message(self,e)
    def apply_action(self,name,args):
        validate_action(name,args)
        if name=='set_story':self.set_story(args['text']);return '故事已保存'
        if name=='add_item':return json.dumps(self.project.add(args['kind'],args['name'],args['description']),ensure_ascii=False)
        if name=='update_item':
            item=self.project.get(args['id'])
            if 'materials' in args:
                if not any(s['id']==item['id'] for s in self.project.data['shots']):raise ValueError('只有分镜可以关联角色和场景')
                valid={a['id'] for a in self.project.data['characters']+self.project.data['scenes']}
                if any(i not in valid for i in args['materials']):raise ValueError('分镜只能关联已有角色或场景')
            item['description']=args['description']
            if 'materials' in args:item['materials']=args['materials']
            self.project.mark_dependents(item['id']);self.save();return '条目已更新'
        if name=='generate':
            item=self.project.get(args['target']);job=self.generate(item,args['mode'],Generation(mode=args['mode'],prompt=args['prompt'],references=args['references'],megapixels=.2 if args['mode'].startswith('h3') else 1,seconds=2))
            return '已加入队列：'+item['name']+'，任务 '+job['id']+'；尚未完成生成' if job else '用户取消了生成，未提交任务'
    def closeEvent(self,event):
        if self.busy():message(self,'仍有任务运行，请等待完成或在任务记录中取消后关闭。');event.ignore();return
        self.save();event.accept()

def main():
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('XiYi.XYStudio')
    app=QApplication(sys.argv);app.setStyle('Fusion');app.setApplicationName('XY Studio')
    app.zh_translator=QTranslator(app)
    if app.zh_translator.load(str(Path(__file__).parent/'assets'/'qtbase_zh_CN.qm')):app.installTranslator(app.zh_translator)
    app.setWindowIcon(QIcon(str(Path(__file__).parent/'assets'/'xy-studio.ico')))
    app.setStyleSheet(QSS)
    window=Studio(sys.argv[1] if len(sys.argv)>1 else None);window.show();return app.exec()
