from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QDialog, QListWidget, QListWidgetItem
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from core.internet_speed import run_speedtest, list_servers
from core.settings import Settings
import threading
import math

class Gauge(QWidget):
    def __init__(self):
        super().__init__()
        self._value = 0.0
        self._max = 1000.0  # Mbps max ölçek
        self.setMinimumSize(260, 260)

    def setValue(self, v: float):
        self._value = max(0.0, min(self._max, float(v)))
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(10, 10, -10, -10)
        center = r.center()
        radius = min(r.width(), r.height())/2

        # kadran
        p.setPen(QPen(QColor("#3b4261"), 14))
        p.drawArc(QRectF(center.x()-radius, center.y()-radius, radius*2, radius*2), 225*16, 270*16)

        # ibre
        angle_start = 225
        angle_span = 270
        frac = min(1.0, self._value / self._max)
        angle = math.radians(angle_start + angle_span*frac)
        p.setPen(QPen(QColor("#e6b422"), 6))
        p.drawLine(center, QPointF(center.x() + math.cos(angle)*radius*0.85, center.y() + math.sin(angle)*radius*0.85))

        # değer
        p.setPen(QColor("#c0caf5"))
        p.drawText(self.rect(), Qt.AlignCenter, f"{self._value:.0f} Mbps")

class ServerSelectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sunucu Seç")
        self.selected_id = None
        v = QVBoxLayout(self)
        self.listw = QListWidget()
        v.addWidget(self.listw)
        btn = QPushButton("Seç")
        btn.clicked.connect(self.accept)
        v.addWidget(btn)

        servers = list_servers(200)
        for s in servers:
            it = QListWidgetItem(f"{s['country']} - {s['sponsor']} ({s['name']})  id:{s['id']}")
            it.setData(Qt.UserRole, s["id"])
            self.listw.addItem(it)

    def accept(self):
        it = self.listw.currentItem()
        if it:
            self.selected_id = int(it.data(Qt.UserRole))
        super().accept()

class SpeedtestWidget(QWidget):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        v = QVBoxLayout(self)

        top = QHBoxLayout()
        self.btn_server = QPushButton("Sunucu Seç")
        self.btn_server.clicked.connect(self._choose_server)
        self.btn_start = QPushButton("Testi Başlat")
        self.btn_start.clicked.connect(self._start_test)
        self.lbl_server = QLabel("Seçili sunucu: (otomatik)")
        top.addWidget(self.lbl_server)
        top.addStretch(1)
        top.addWidget(self.btn_server)
        top.addWidget(self.btn_start)
        v.addLayout(top)

        self.gauge = Gauge()
        v.addWidget(self.gauge)

        self.lbl_result = QLabel("-")
        v.addWidget(self.lbl_result)

        self._anim = QTimer(self)
        self._anim.timeout.connect(self._anim_tick)
        self._anim.start(50)
        self._anim_phase = 0.0
        self._testing = False
        self._target_value = 0.0

        self._refresh_label()

    def _refresh_label(self):
        sid = self.settings.speedtest.preferred_server_id
        self.lbl_server.setText(f"Seçili sunucu: {(sid if sid else 'otomatik')}")

    def _choose_server(self):
        dlg = ServerSelectDialog(self)
        if dlg.exec():
            self.settings.speedtest.preferred_server_id = dlg.selected_id
            self.settings.save()
            self._refresh_label()

    def _start_test(self):
        if self._testing:
            return
        self._testing = True
        self.btn_start.setEnabled(False)
        self.lbl_result.setText("Test çalışıyor...")
        def run():
            try:
                r = run_speedtest(self.settings.speedtest.preferred_server_id)
                def ui():
                    self.lbl_result.setText(f"Sunucu: {r['server']} | Ping: {r['ping_ms']} ms | İndirme: {r['download_mbps']} Mbps | Yükleme: {r['upload_mbps']} Mbps")
                    self._target_value = max(r['download_mbps'], r['upload_mbps'])
                    self.btn_start.setEnabled(True)
                    self._testing = False
                self._post(ui)
            except Exception as e:
                self._post(lambda: (self.lbl_result.setText(f"Hata: {e}"), self.btn_start.setEnabled(True), setattr(self, "_testing", False)))
        threading.Thread(target=run, daemon=True).start()

    def _post(self, fn):
        # basit main-thread post
        self._anim.singleShot(0, fn) if hasattr(self._anim, "singleShot") else fn()

    def _anim_tick(self):
        # test sırasında ibre/sweep animasyonu
        if self._testing:
            self.gauge.setValue((self.gauge._value + 25) % self.gauge._max)
        else:
            # hedef değere ease ile yaklaş
            diff = self._target_value - self.gauge._value
            self.gauge.setValue(self.gauge._value + diff * 0.05)