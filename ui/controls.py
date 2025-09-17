from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Property, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush

class ToggleSwitch(QWidget):
    def __init__(self, parent=None, checked=False):
        super().__init__(parent)
        self._checked = checked
        self.setFixedSize(46, 24)

    def isChecked(self):
        return self._checked

    def setChecked(self, v: bool):
        if self._checked != v:
            self._checked = v
            self.update()

    checked = Property(bool, isChecked, setChecked)

    def mousePressEvent(self, e):
        self._checked = not self._checked
        self.update()
        self.toggled(self._checked)

    def toggled(self, state: bool):
        # placeholder; MainWindow bağlayacak
        pass

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bg = QColor("#4caf50") if self._checked else QColor("#9e9e9e")
        p.setBrush(QBrush(bg))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(self.rect(), 12, 12)
        # knob
        r = self.rect()
        x = r.right()-20 if self._checked else r.left()+2
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QPointF(x+10, r.center().y()), 10, 10)