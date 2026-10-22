from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea


class ImageThumbnail(QLabel):
    activated = Signal()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.activated.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)


class ImageViewer(QDialog):
    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.original = QPixmap(str(path))
        if self.original.isNull():
            raise ValueError('图片不存在或无法读取')
        self.setWindowTitle('图片查看 · '+path.name)
        self.resize(1000, 800)
        self.factor = 1.0
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        layout.addLayout(controls)
        for title, fn in [('缩小', lambda: self.zoom(self.factor/1.25)),
                          ('放大', lambda: self.zoom(self.factor*1.25)),
                          ('适应窗口', self.fit), ('原始大小 100%', lambda: self.zoom(1))]:
            button = QPushButton(title)
            button.clicked.connect(fn)
            controls.addWidget(button)
        self.info = QLabel()
        controls.addWidget(self.info)
        self.image = QLabel()
        self.area = QScrollArea()
        self.area.setAlignment(Qt.AlignCenter)
        self.area.setWidget(self.image)
        layout.addWidget(self.area)
        QTimer.singleShot(0, self.fit)

    def zoom(self, factor):
        # Bound the rendered pixmap allocation even for very large upscaled files.
        self.factor = max(.01, min(factor, 8, 12000/max(self.original.width(), self.original.height())))
        size = self.original.size()*self.factor
        self.image.setPixmap(self.original.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.image.resize(self.image.pixmap().size())
        self.info.setText(f'{self.original.width()} × {self.original.height()} · {self.factor:.0%}')

    def fit(self):
        self.zoom(min(self.area.viewport().width()/self.original.width(),
                      self.area.viewport().height()/self.original.height(), 1))
