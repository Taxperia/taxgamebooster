from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QProgressBar, QPushButton, QListWidget, QListWidgetItem, QFrame
from PySide6.QtGui import QIcon, QPainter, QColor, QBrush, QPen, QLinearGradient, QFont
from PySide6.QtCore import Qt, QTimer, QRectF
import os

ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icons")

def icon(name: str) -> QIcon:
    p = os.path.join(ICON_DIR, f"{name}.svg")
    return QIcon(p)

class MSIAfterburnerCard(QWidget):
    """MSI Afterburner tarzı kart tasarımı"""
    def __init__(self, title: str, icon_name: str, color: str = "#00ff88"):
        super().__init__()
        self.title = title
        self.icon_name = icon_name
        self.color = color
        self.value_text = "-"
        self.percent = 0.0
        self.setMinimumSize(280, 120)
        self.setMaximumSize(320, 140)
        
        # Styling
        self.setStyleSheet(f"""
            MSIAfterburnerCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 #1a1a1a, stop:1 #0a0a0a);
                border: 2px solid {color};
                border-radius: 12px;
                margin: 5px;
            }}
        """)

    def set_value(self, text: str, percent: float = 0.0):
        self.value_text = text
        self.percent = max(0.0, min(100.0, percent))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect().adjusted(10, 10, -10, -10)
        
        # Background gradient
        bg_gradient = QLinearGradient(0, 0, 0, rect.height())
        bg_gradient.setColorAt(0, QColor("#2a2a2a"))
        bg_gradient.setColorAt(1, QColor("#1a1a1a"))
        painter.setBrush(QBrush(bg_gradient))
        painter.setPen(QPen(QColor(self.color), 2))
        painter.drawRoundedRect(rect, 8, 8)
        
        # Title
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        title_rect = QRectF(rect.x() + 15, rect.y() + 10, rect.width() - 30, 20)
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter, self.title)
        
        # Value
        painter.setPen(QColor(self.color))
        painter.setFont(QFont("Arial", 16, QFont.Bold))
        value_rect = QRectF(rect.x() + 15, rect.y() + 35, rect.width() - 30, 30)
        painter.drawText(value_rect, Qt.AlignLeft | Qt.AlignVCenter, self.value_text)
        
        # Progress bar background
        progress_rect = QRectF(rect.x() + 15, rect.y() + rect.height() - 25, rect.width() - 30, 8)
        painter.setBrush(QBrush(QColor("#333333")))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(progress_rect, 4, 4)
        
        # Progress bar fill
        if percent is not None:
            fill_width = (progress_rect.width() * self.percent) / 100.0
            fill_rect = QRectF(progress_rect.x(), progress_rect.y(), fill_width, progress_rect.height())
            
            # Gradient based on percentage
            progress_gradient = QLinearGradient(fill_rect.x(), 0, fill_rect.x() + fill_rect.width(), 0)
            if self.percent < 50:
                progress_gradient.setColorAt(0, QColor("#4CAF50"))
                progress_gradient.setColorAt(1, QColor("#8BC34A"))
            elif self.percent < 80:
                progress_gradient.setColorAt(0, QColor("#FF9800"))
                progress_gradient.setColorAt(1, QColor("#FFC107"))
            else:
                progress_gradient.setColorAt(0, QColor("#F44336"))
                progress_gradient.setColorAt(1, QColor("#FF5722"))
            
            painter.setBrush(QBrush(progress_gradient))
            painter.drawRoundedRect(fill_rect, 4, 4)
        
        # Icon (simplified representation)
        icon_rect = QRectF(rect.x() + rect.width() - 40, rect.y() + 10, 30, 30)
        painter.setPen(QPen(QColor(self.color), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(icon_rect)

class DashboardWidget(QWidget):
    def __init__(self, system_monitor):
        super().__init__()
        self._mon = system_monitor
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Sistem Durumu")
        title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #00ff88;
                margin-bottom: 10px;
            }
        """)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)
        
        # Cards container
        cards_widget = QWidget()
        cards_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #0a0a0a, stop:1 #1a1a1a);
                border: 1px solid #333333;
                border-radius: 15px;
                padding: 20px;
            }
        """)
        grid = QVBoxLayout(cards_widget)
        grid.setSpacing(15)

        row1 = QHBoxLayout()
        row1.setSpacing(15)
        self.card_cpu = MSIAfterburnerCard("CPU", "cpu", "#00ff88")
        self.card_gpu = MSIAfterburnerCard("GPU", "gpu", "#ff8800")
        self.card_ram = MSIAfterburnerCard("RAM", "ram", "#0088ff")
        row1.addWidget(self.card_cpu)
        row1.addWidget(self.card_gpu)
        row1.addWidget(self.card_ram)
        grid.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(15)
        self.card_disk = MSIAfterburnerCard("Disk", "disk", "#ff0080")
        self.card_net = MSIAfterburnerCard("Ağ", "net", "#8800ff")
        row2.addWidget(self.card_disk)
        row2.addWidget(self.card_net)
        row2.addStretch(1)  # Add stretch to center the two cards
        grid.addLayout(row2)
        
        main_layout.addWidget(cards_widget)
        main_layout.addStretch(1)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def update_from_snapshot(self, s):
        # dış tetik gerekirse
        pass

    def _tick(self):
        s = self._mon.get()
        cpu_txt = f"{s.cpu_percent:.0f}% • {float(s.cpu_freq or 0):.0f} MHz"
        self.card_cpu.set_value(cpu_txt, s.cpu_percent or 0)

        if s.gpu_util is not None:
            gpu_parts = [f"{s.gpu_util:.0f}%"]
            if s.gpu_temp is not None:
                gpu_parts.append(f"{s.gpu_temp:.0f}°C")
            if getattr(s, 'gpu_power_w', None) is not None:
                gpu_parts.append(f"{s.gpu_power_w:.0f}W")
            gpu_txt = " • ".join(gpu_parts)
            self.card_gpu.set_value(gpu_txt, s.gpu_util or 0)
        else:
            self.card_gpu.set_value("—", 0)

        ram_pc = getattr(s, 'ram_percent', 0.0)
        ram_txt = f"{(s.ram_used or 0)/1_073_741_824:.1f}GB • {ram_pc:.0f}%"
        self.card_ram.set_value(ram_txt, ram_pc or 0)

        self.card_disk.set_value("—", 0)
        net_up = getattr(s, 'net_up', 0) / 1e6
        net_down = getattr(s, 'net_down', 0) / 1e6
        net_txt = f"↑ {net_up:.1f} • ↓ {net_down:.1f} MB/s"
        self.card_net.set_value(net_txt)