from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QDialog, QListWidget, QListWidgetItem
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QLinearGradient
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, QPropertyAnimation, QEasingCurve, pyqtProperty
from core.internet_speed import run_speedtest, list_servers
from core.settings import Settings
import threading
import math

class Gauge(QWidget):
    def __init__(self):
        super().__init__()
        self._value = 0.0
        self._animated_value = 0.0
        self._max = 1000.0  # Mbps max ölçek
        self.setMinimumSize(320, 320)
        
        # Animation
        self._animation = QPropertyAnimation(self, b"animatedValue")
        self._animation.setDuration(1500)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)

    def setValue(self, v: float):
        new_value = max(0.0, min(self._max, float(v)))
        if new_value != self._value:
            self._value = new_value
            self._animation.setStartValue(self._animated_value)
            self._animation.setEndValue(self._value)
            self._animation.start()
    
    @pyqtProperty(float)
    def animatedValue(self):
        return self._animated_value
    
    @animatedValue.setter
    def animatedValue(self, value):
        self._animated_value = value
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(20, 20, -20, -20)
        center = r.center()
        radius = min(r.width(), r.height()) / 2 - 10
        
        # Outer ring (background)
        p.setPen(QPen(QColor("#2a2a2a"), 8))
        p.drawEllipse(QRectF(center.x()-radius, center.y()-radius, radius*2, radius*2))
        
        # Speed markings
        p.setPen(QPen(QColor("#666666"), 2))
        for i in range(0, 11):  # 0-1000 Mbps in 100 Mbps increments
            angle = math.radians(225 + (270 * i / 10))
            inner_radius = radius - 15
            outer_radius = radius - 5
            x1 = center.x() + math.cos(angle) * inner_radius
            y1 = center.y() + math.sin(angle) * inner_radius
            x2 = center.x() + math.cos(angle) * outer_radius
            y2 = center.y() + math.sin(angle) * outer_radius
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            
            # Speed labels
            if i % 2 == 0:  # Every other marking
                label_radius = radius - 30
                label_x = center.x() + math.cos(angle) * label_radius
                label_y = center.y() + math.sin(angle) * label_radius
                p.setPen(QColor("#888888"))
                p.setFont(QFont("Arial", 8))
                p.drawText(QPointF(label_x - 10, label_y + 5), f"{i * 100}")
        
        # Progress arc
        frac = min(1.0, self._animated_value / self._max)
        if frac > 0:
            # Create gradient for the arc
            gradient = QLinearGradient(0, 0, radius * 2, 0)
            if frac < 0.3:
                gradient.setColorAt(0, QColor("#4CAF50"))  # Green for low speeds
                gradient.setColorAt(1, QColor("#8BC34A"))
            elif frac < 0.7:
                gradient.setColorAt(0, QColor("#FF9800"))  # Orange for medium speeds
                gradient.setColorAt(1, QColor("#FFC107"))
            else:
                gradient.setColorAt(0, QColor("#F44336"))  # Red for high speeds
                gradient.setColorAt(1, QColor("#FF5722"))
            
            p.setPen(QPen(QBrush(gradient), 12, Qt.SolidLine, Qt.RoundCap))
            span_angle = int(270 * frac * 16)  # Convert to 1/16th degrees
            p.drawArc(QRectF(center.x()-radius, center.y()-radius, radius*2, radius*2), 
                     225 * 16, span_angle)

        # Needle
        if frac > 0:
            angle = math.radians(225 + 270 * frac)
            needle_length = radius * 0.8
            needle_end = QPointF(
                center.x() + math.cos(angle) * needle_length,
                center.y() + math.sin(angle) * needle_length
            )
            
            # Needle shadow
            p.setPen(QPen(QColor(0, 0, 0, 100), 4))
            p.drawLine(QPointF(center.x() + 2, center.y() + 2), 
                      QPointF(needle_end.x() + 2, needle_end.y() + 2))
            
            # Needle
            p.setPen(QPen(QColor("#ffffff"), 3))
            p.drawLine(center, needle_end)
        
        # Center hub
        p.setBrush(QBrush(QColor("#444444")))
        p.setPen(QPen(QColor("#666666"), 2))
        p.drawEllipse(QPointF(center.x(), center.y()), 8, 8)

        # Digital display
        display_rect = QRectF(center.x() - 60, center.y() + 40, 120, 40)
        p.setBrush(QBrush(QColor("#1a1a1a")))
        p.setPen(QPen(QColor("#333333"), 1))
        p.drawRoundedRect(display_rect, 8, 8)
        
        # Speed text
        p.setPen(QColor("#00ff88"))
        p.setFont(QFont("Arial", 16, QFont.Bold))
        p.drawText(display_rect, Qt.AlignCenter, f"{self._animated_value:.1f}")
        
        # Unit text
        unit_rect = QRectF(center.x() - 30, center.y() + 85, 60, 20)
        p.setPen(QColor("#888888"))
        p.setFont(QFont("Arial", 10))
        p.drawText(unit_rect, Qt.AlignCenter, "Mbps")

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
        v.setSpacing(20)
        v.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("İnternet Hız Testi")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #00ff88; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)

        top = QHBoxLayout()
        self.btn_server = QPushButton("Sunucu Seç")
        self.btn_server.setStyleSheet("QPushButton { min-width: 120px; }")
        self.btn_server.clicked.connect(self._choose_server)
        self.btn_start = QPushButton("Testi Başlat")
        self.btn_start.setStyleSheet("QPushButton { min-width: 120px; font-weight: bold; }")
        self.btn_start.clicked.connect(self._start_test)
        self.lbl_server = QLabel("Seçili sunucu: (otomatik)")
        self.lbl_server.setStyleSheet("color: #888888;")
        top.addWidget(self.lbl_server)
        top.addStretch(1)
        top.addWidget(self.btn_server)
        top.addWidget(self.btn_start)
        v.addLayout(top)

        # Gauge container
        gauge_container = QHBoxLayout()
        gauge_container.addStretch(1)
        self.gauge = Gauge()
        gauge_container.addWidget(self.gauge)
        gauge_container.addStretch(1)
        v.addLayout(gauge_container)

        # Results container
        results_container = QVBoxLayout()
        self.lbl_result = QLabel("-")
        self.lbl_result.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 15px;
                font-size: 14px;
                color: #ffffff;
            }
        """)
        self.lbl_result.setAlignment(Qt.AlignCenter)
        results_container.addWidget(self.lbl_result)
        v.addLayout(results_container)

        self._testing = False

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
        self.btn_start.setText("Test Çalışıyor...")
        self.lbl_result.setText("Test çalışıyor...")
        self.gauge.setValue(0)
        
        def run():
            try:
                r = run_speedtest(self.settings.speedtest.preferred_server_id)
                def ui():
                    result_text = f"""
                    <div style='text-align: center;'>
                        <h3 style='color: #00ff88; margin-bottom: 10px;'>Test Sonuçları</h3>
                        <p><strong>Sunucu:</strong> {r['server']}</p>
                        <p><strong>Ping:</strong> {r['ping_ms']} ms</p>
                        <p><strong>İndirme:</strong> <span style='color: #00ff88; font-size: 18px;'>{r['download_mbps']} Mbps</span></p>
                        <p><strong>Yükleme:</strong> <span style='color: #ff8800; font-size: 18px;'>{r['upload_mbps']} Mbps</span></p>
                    </div>
                    """
                    self.lbl_result.setText(result_text)
                    # Show download speed on gauge
                    self.gauge.setValue(r['download_mbps'])
                    self.btn_start.setEnabled(True)
                    self.btn_start.setText("Testi Başlat")
                    self._testing = False
                self._post(ui)
            except Exception as e:
                def error_ui():
                    self.lbl_result.setText(f"<div style='color: #ff4444; text-align: center;'><h3>Hata</h3><p>{e}</p></div>")
                    self.btn_start.setEnabled(True)
                    self.btn_start.setText("Testi Başlat")
                    self._testing = False
                self._post(error_ui)
        threading.Thread(target=run, daemon=True).start()

    def _post(self, fn):
        # basit main-thread post
        QTimer.singleShot(0, fn)