"""Offscreen Qt logical geometry checks, run in separate DPI environments."""
import os,sys,json
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from studio.ui import Studio
from studio.storage import Project,uid
app=QApplication([]);p=Project(Path('local-data')/('dpi-'+uid()[:8]),True)
for kind in ('characters','scenes','shots'):
 for n in range(12):p.add(kind,f'测试 {n}','很长的无空格描述'*60)
w=Studio(p.root);w.show();checks=[]
for size in [(900,620),(1000,720),(1440,900),(1920,1000)]:
 w.resize(*size)
 for page in (1,2,3):
  w.navigation.setCurrentRow(page);app.processEvents()
  assert w.width()==size[0] and w.height()==size[1],(size,w.width(),w.height(),w.minimumSizeHint())
  assert w.dock.width()>=300
  sc=w.page_scrolls[('characters','scenes','shots')[page-1]]
  assert sc.horizontalScrollBar().maximum()==0,(size,page,sc.horizontalScrollBar().maximum())
  checks.append({'size':size,'page':page,'horizontal_overflow':0})
w.close();print(json.dumps({'scale':os.environ.get('QT_SCALE_FACTOR','1'),'dpr':app.devicePixelRatio(),'checks':checks}))
