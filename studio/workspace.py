"""Presentation-only cards, reflowing asset grid and shot navigation.

IDs and callbacks are supplied by Studio; these widgets never write projects or submit jobs.
"""
from pathlib import Path
from PySide6.QtCore import Qt,Signal,QSize
from PySide6.QtGui import QImageReader,QPixmap,QColor
from PySide6.QtWidgets import QWidget,QFrame,QLabel,QPushButton,QVBoxLayout,QHBoxLayout,QGridLayout,QBoxLayout,QScrollArea,QSizePolicy,QMenu,QGraphicsDropShadowEffect
from .image_viewer import ImageThumbnail


def label(text,style='muted'):
    result=QLabel(text);result.setObjectName(style);result.setWordWrap(True);result.setTextFormat(Qt.PlainText);result.setMinimumWidth(0);result.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred);return result


def action_button(text,fn,primary=False):
    result=QPushButton(text);result.clicked.connect(fn);result.setProperty('primary',primary);return result


class Preview(ImageThumbnail):
    def __init__(self,path=None,empty='尚未生成',height=170):
        super().__init__(empty);self.setAlignment(Qt.AlignCenter);self.setMinimumWidth(120);self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
        self.setStyleSheet('background:#eff1f3;border:1px solid #e3e7eb;border-radius:7px;color:#697789;')
        self.path=Path(path) if path else None;self.source=None;self.loaded=False
        if self.path:self.setToolTip('双击查看原图');self.setCursor(Qt.PointingHandCursor)
    def showEvent(self,event):
        super().showEvent(event)
        if not self.loaded:
            self.loaded=True
            if self.path:
                reader=QImageReader(str(self.path));size=reader.size()
                if size.isValid():reader.setScaledSize(size.scaled(QSize(800,500),Qt.KeepAspectRatio))
                img=reader.read()
                if img.isNull():self.setText('图片无法读取');self.setToolTip(str(self.path))
                else:self.source=QPixmap.fromImage(img);self.draw()
    def resizeEvent(self,event):super().resizeEvent(event);self.draw()
    def draw(self):
        if self.source:
            dpr=self.devicePixelRatioF();pix=self.source.scaled((self.size()-QSize(12,12))*dpr,Qt.KeepAspectRatio,Qt.SmoothTransformation);pix.setDevicePixelRatio(dpr);self.setPixmap(pix)


class AssetGrid(QWidget):
    def __init__(self,cards):
        super().__init__();self.cards=cards;self.columns=0;self.grid=QGridLayout(self);self.grid.setContentsMargins(0,0,0,0);self.grid.setSpacing(16);self.reflow(1)
    def resizeEvent(self,event):
        super().resizeEvent(event);self.reflow(max(1,min(4,self.width()//280)))
    def reflow(self,columns):
        if columns==self.columns:return
        self.columns=columns
        for card in self.cards:self.grid.removeWidget(card)
        for i,card in enumerate(self.cards):self.grid.addWidget(card,i//columns,i%columns)
        for i in range(4):self.grid.setColumnStretch(i,1 if i<columns else 0)


class WorkspaceCard(QFrame):
    selected=Signal(str);action=Signal(str,str);folded=Signal(str,bool);file_requested=Signal(str)
    def __init__(self,kind,item,root,linked,poster,status,collapsed=False,references=()):
        super().__init__();self.kind=kind;self.item_id=item['id'];self.setObjectName('shotCard' if kind=='shots' else 'assetCard');self.setProperty('selected',False)
        shadow=QGraphicsDropShadowEffect(self);shadow.setBlurRadius(10);shadow.setOffset(0,2);shadow.setColor(QColor(30,45,65,14));self.setGraphicsEffect(shadow)
        self.setMinimumWidth(250);self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred)
        # One outer row keeps a common card interface; the internal shot body reflows.
        outer=QHBoxLayout(self);outer.setContentsMargins(14,14,14,14);wrapper=QWidget();outer.addWidget(wrapper);layout=QVBoxLayout(wrapper);layout.setContentsMargins(0,0,0,0);layout.setSpacing(10)
        head=QHBoxLayout();layout.addLayout(head)
        display_name=item['name']
        if kind=='shots' and item.get('original_name') not in (None,'','未命名',item['name']):display_name+=' · '+item['original_name']
        self.title=action_button(display_name[:44],lambda:self.selected.emit(self.item_id));self.title.setToolTip(display_name);self.title.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred);self.title.setMinimumWidth(40);self.title.setObjectName('cardTitle');self.title.setStyleSheet('text-align:left;font-weight:600;border:none;background:transparent;');head.addWidget(self.title,1)
        self.state=label(status,'status');self.state.setMinimumWidth(84);self.state.setMaximumWidth(160);self.state.setSizePolicy(QSizePolicy.Preferred,QSizePolicy.Preferred);head.addWidget(self.state)
        self.body=QWidget();self.body.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Maximum);self.body_layout=QHBoxLayout(self.body);self.body_layout.setContentsMargins(0,0,0,0);self.body_layout.setSpacing(16)
        if kind=='shots':
            self.fold=action_button('展开' if collapsed else '收起',self.toggle);head.addWidget(self.fold)
            self.body.setVisible(not collapsed)
        layout.addWidget(self.body)
        if kind=='shots':
            details=QWidget();dl=QVBoxLayout(details);dl.setContentsMargins(0,0,0,0)
            dl.addWidget(label(item['description'][:220]+('…' if len(item['description'])>220 else '') or '添加镜头描述，明确画面与动作。','sectionTitle'))
            dl.addWidget(action_button('编辑描述',lambda:self.emit_action('edit')))
            dl.addWidget(label('关联角色与场景','sectionTitle'))
            for asset in linked:
                row=QHBoxLayout();small=Preview(root/asset['image'] if asset.get('image') else None,height=52);small.setFixedWidth(76);small.setMinimumWidth(76);small.activated.connect(lambda a=asset:self.action.emit('view',a['id']));row.addWidget(small);row.addWidget(label(asset['name']));dl.addLayout(row)
            if not linked:dl.addWidget(label('尚未关联素材'))
            dl.addWidget(action_button('关联角色 / 场景',lambda:self.emit_action('link')))
            if references:
                dl.addWidget(label('最近生成使用的参考图','sectionTitle'))
                reference_area=QScrollArea();reference_area.setWidgetResizable(True);reference_area.setFixedHeight(82)
                reference_content=QWidget();reference_row=QHBoxLayout(reference_content);reference_row.setContentsMargins(0,0,0,0)
                for number,path in enumerate(references,1):
                    thumb=Preview(root/path,height=54);thumb.setFixedWidth(76);thumb.setMinimumWidth(76);thumb.setToolTip(f'参考 {number} · {path}');thumb.activated.connect(lambda p=path:self.file_requested.emit(p));reference_row.addWidget(thumb)
                reference_row.addStretch();reference_area.setWidget(reference_content);dl.addWidget(reference_area)
            if item.get('needs_review'):
                dl.addWidget(label('素材已修改，请检查镜头','status'));dl.addWidget(action_button('已检查，保留当前结果',lambda:self.emit_action('review')))
            dl.addStretch();self.body_layout.addWidget(details,1)
        image_column=QWidget();images=QVBoxLayout(image_column);images.setContentsMargins(0,0,0,0)
        images.addWidget(label('分镜图' if kind=='shots' else '角色形象' if kind=='characters' else '场景参考','sectionTitle'))
        self.preview=Preview(root/item['image'] if item['image'] else None,height=180 if kind=='shots' else 200)
        self.preview.activated.connect(lambda:self.emit_action('view'));images.addWidget(self.preview)
        if kind!='shots':
            description=label(item['description'][:64]+('…' if len(item['description'])>64 else '') or '添加描述，建立可复用的创作资产。');description.setFixedHeight(62);description.setToolTip('编辑描述可查看完整内容');images.addWidget(description)
            images.addWidget(action_button('编辑描述',lambda:self.emit_action('edit')))
        images.addWidget(action_button('生成 / 编辑图片',lambda:self.emit_action('image'),True));images.addWidget(action_button('导入图片',lambda:self.emit_action('import')))
        self.body_layout.addWidget(image_column,1)
        if kind=='shots':
            video_column=QWidget();videos=QVBoxLayout(video_column);videos.setContentsMargins(0,0,0,0);videos.addWidget(label('生成视频','sectionTitle'))
            video=Preview(root/poster if poster else None,'视频首帧读取失败' if item['video'] else '等待生成视频',180);video.activated.connect(lambda:self.emit_action('play'));videos.addWidget(video)
            videos.addWidget(action_button('生成视频',lambda:self.emit_action('video'),True))
            play=action_button('播放视频',lambda:self.emit_action('play'));play.setEnabled(bool(item['video']));videos.addWidget(play);self.body_layout.addWidget(video_column,1)
        self.history=QWidget();history=QVBoxLayout(self.history);history.setContentsMargins(0,0,0,0);history.setSpacing(4)
        history.addWidget(label(f'生成版本 · {len(item["versions"])} 个版本保存在此条目','muted'))
        for version in item['versions'][-2:]:
            text=('视频' if version['kind']=='video' else '图片')+' · '+version.get('time','')[:16].replace('T',' ')+' · '+version.get('intent','')[:55].replace('\n',' ')
            entry=label(text);entry.setToolTip(version.get('intent',''));history.addWidget(entry)
        self.history.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Maximum);layout.addWidget(self.history);self.history.setVisible(not collapsed)
        if kind!='shots':layout.addStretch()
        footer=QHBoxLayout();layout.addLayout(footer)
        footer.addWidget(action_button('生成历史',lambda:self.emit_action('history')))
        footer.addWidget(action_button('发送给 AI',lambda:self.emit_action('context')))
        delete=action_button('删除'+{'characters':'角色','scenes':'场景','shots':'分镜'}[kind],lambda:self.emit_action('delete'));delete.setProperty('danger',True);footer.addWidget(delete)
        self.setContextMenuPolicy(Qt.CustomContextMenu);self.customContextMenuRequested.connect(self.menu)
    def emit_action(self,action):self.selected.emit(self.item_id);self.action.emit(action,self.item_id)
    def mousePressEvent(self,event):self.selected.emit(self.item_id);super().mousePressEvent(event)
    def set_selected(self,value):
        if self.property('selected')!=value:self.setProperty('selected',value);self.style().unpolish(self);self.style().polish(self);self.update()
    def toggle(self):
        collapsed=not self.body.isHidden();self.body.setVisible(not collapsed);self.history.setVisible(not collapsed);self.fold.setText('展开' if collapsed else '收起');self.folded.emit(self.item_id,collapsed)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.kind=='shots':self.body_layout.setDirection(QBoxLayout.TopToBottom if self.width()<720 else QBoxLayout.LeftToRight)
    def menu(self,pos):
        menu=QMenu(self)
        for name,action in [('查看详情 / 编辑描述','edit'),('生成新版本','image'),('生成历史','history'),('发送给 AI','context'),('删除条目','delete')]:menu.addAction(name,lambda checked=False,a=action:self.emit_action(a))
        menu.exec(self.mapToGlobal(pos))


class ShotTimeline(QScrollArea):
    selected=Signal(str)
    def __init__(self,shots,durations):
        super().__init__();self.setWidgetResizable(True);self.setFixedHeight(86);self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content=QWidget();row=QHBoxLayout(content);row.setContentsMargins(0,6,0,6);self.buttons={}
        for shot in shots:
            title=shot['name']+(' · '+shot['original_name'] if shot.get('original_name') not in (None,'','未命名',shot['name']) else '')
            b=action_button(title[:22]+'\n'+durations.get(shot['id'],'时长待定'),lambda checked=False,ident=shot['id']:self.selected.emit(ident));b.setToolTip(title);b.setCheckable(True);b.setMinimumWidth(135);row.addWidget(b);self.buttons[shot['id']]=b
        if not shots:row.addWidget(label('添加第一个分镜后，这里会显示镜头顺序与时长。'))
        row.addStretch();self.setWidget(content)
    def select(self,ident):
        for key,b in self.buttons.items():b.setChecked(key==ident)
        if ident in self.buttons:self.ensureWidgetVisible(self.buttons[ident])
