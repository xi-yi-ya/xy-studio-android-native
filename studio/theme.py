"""Shared design tokens. Qt uses device-independent pixels for Widgets and QSS."""
QSS = '''
QWidget { color:#263246; font-family:"Microsoft YaHei UI","Segoe UI"; font-size:13px; }
QMainWindow,QDialog { background:#f4f3f0; }
QWidget#workspaceShell,QWidget#pageBody { background:#f4f3f0; }
QWidget#sidebar { background:#ebece9; border-right:1px solid #dfe2e4; }
QLabel#brand { font-size:21px; font-weight:700; padding:12px 0; }
QLabel#pageTitle { font-size:23px; font-weight:650; }
QLabel#muted { color:#637083; font-size:12px; }
QLabel#cardTitle { font-size:15px; font-weight:650; }
QLabel#sectionTitle { font-size:13px; font-weight:600; }
QLabel#status { color:#466484; font-size:12px; }
QListWidget#navigation { background:transparent; border:none; outline:none; }
QListWidget#navigation::item { padding:12px 10px; margin:3px 0; border-radius:8px; }
QListWidget#navigation::item:selected { background:#dce8f8; color:#245dac; }
QFrame#assetCard,QFrame#shotCard,QFrame#overviewCard { background:#ffffff; border:1px solid #dfe3e8; border-radius:10px; }
QFrame#assetCard[selected="true"],QFrame#shotCard[selected="true"] { border:2px solid #6592d2; }
QPushButton { background:#ffffff; border:1px solid #dce1e7; border-radius:6px; padding:7px 10px; min-height:18px; }
QPushButton:hover { background:#f0f5fc; border-color:#a9bfdc; }
QPushButton:pressed,QPushButton:checked { background:#e0ebfa; color:#245dac; }
QPushButton:disabled { color:#9099a5; background:#f0f1f2; }
QPushButton[primary="true"] { background:#356bc2; border-color:#356bc2; color:white; }
QPushButton[primary="true"]:hover { background:#2a5aad; }
QPushButton[danger="true"] { color:#9f4343; }
QLineEdit,QPlainTextEdit,QTextEdit,QTextBrowser,QComboBox,QSpinBox,QDoubleSpinBox,QListWidget,QTableWidget { background:#ffffff; border:1px solid #dce1e7; border-radius:6px; padding:5px; selection-background-color:#dce9fc; selection-color:#203c62; }
QTextBrowser { padding:8px; }
QComboBox { min-height:24px; }
QScrollArea,QTabWidget::pane { border:none; background:transparent; }
QScrollBar:vertical { background:#f0f1ef; width:10px; margin:0; }
QScrollBar::handle:vertical { background:#c4cbd2; min-height:28px; border-radius:5px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QToolBar { background:#ffffff; border:none; border-bottom:1px solid #e0e4e8; spacing:6px; padding:6px; }
QToolButton { border:none; padding:6px 10px; border-radius:5px; }
QToolButton:hover { background:#eaf0f8; }
QDockWidget { background:#f7f8fa; }
QDockWidget::title { background:#f7f8fa; padding:12px; font-weight:600; }
QGroupBox { border:1px solid #dfe3e8; border-radius:8px; margin-top:12px; padding:12px; background:#ffffff; }
QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 4px; }
QHeaderView::section { background:#f0f3f6; border:none; padding:8px; }
QProgressBar { border:1px solid #dce1e7; border-radius:5px; background:#edf0f4; text-align:center; min-height:18px; }
QProgressBar::chunk { background:#9ab8e4; border-radius:4px; }
QStatusBar { background:#ebece9; color:#637083; }
QMenu { background:white; border:1px solid #dce1e7; padding:5px; }
QMenu::item { padding:7px 18px; }
QMenu::item:selected { background:#e7effa; }
QToolTip { background:#263246; color:white; border:none; padding:5px; }
'''
