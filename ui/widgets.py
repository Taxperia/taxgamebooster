from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QProgressBar, QPushButton, QListWidget, QListWidgetItem
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QTimer
import os

ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icons")

def icon(name: str) -> QIcon:
    p = os.path.join(ICON_DIR, f"{name}.svg")
    return QIcon(p)

class StatCard(QWidget):
    def __init__(self, title: str, icon_name: str):
        super().__init__()
        root = QHBoxLayout(self)
        root.setContentsMargins(10,10,10,10)
        left = QVBoxLayout()
        self.lbl_title = QLabel(title)
        self.lbl_value = QLabel("-")
        self.lbl_title.setStyleSheet("font-weight:600;")
        self.lbl_value.setStyleSheet("font-size: 18px;")
        left.addWidget(self.lbl_title)
        left.addWidget(self.lbl_value)
        left.addStretch(1)
        root.addLayout(left)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        root.addWidget(self.progress, 1)
        self.lbl_icon = QLabel()
        self.lbl_icon.setPixmap(icon(icon_name).pixmap(28, 28))
        root.addWidget(self.lbl_icon)

    def set_value(self, text: str, percent: float | None = None):
        self.lbl_value.setText(text)
        if percent is not None:
            self.progress.setValue(int(max(0, min(100, percent))))

class DashboardWidget(QWidget):
    def __init__(self, system_monitor):
        super().__init__()
        self._mon = system_monitor
        grid = QVBoxLayout(self)

        row1 = QHBoxLayout()
        self.card_cpu = StatCard("CPU", "cpu")
        self.card_gpu = StatCard("GPU", "gpu")
        self.card_ram = StatCard("RAM", "ram")
        row1.addWidget(self.card_cpu)
        row1.addWidget(self.card_gpu)
        row1.addWidget(self.card_ram)
        grid.addLayout(row1)

        row2 = QHBoxLayout()
        self.card_disk = StatCard("Disk", "disk")
        self.card_net = StatCard("Ağ", "net")
        row2.addWidget(self.card_disk)
        row2.addWidget(self.card_net)
        grid.addLayout(row2)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def update_from_snapshot(self, s):
        # dış tetik gerekirse
        pass

    def _tick(self):
        s = self._mon.get()
        cpu_txt = f"{s.cpu_percent:.0f}% @ {float(s.cpu_freq or 0):.0f} MHz"
        self.card_cpu.set_value(cpu_txt, s.cpu_percent or 0)

        if s.gpu_util is not None:
            gpu_txt = f"{s.gpu_util:.0f}%"
            if s.gpu_temp is not None:
                gpu_txt += f" {s.gpu_temp:.0f}°C"
            if getattr(s, 'gpu_power_w', None) is not None:
                gpu_txt += f" {s.gpu_power_w:.0f}W"
            self.card_gpu.set_value(gpu_txt, s.gpu_util or 0)
        else:
            self.card_gpu.set_value("—", 0)

        ram_pc = getattr(s, 'ram_percent', 0.0)
        ram_txt = f"{(s.ram_used or 0)/1_073_741_824:.1f}/{(s.ram_total or 0)/1_073_741_824:.1f} GiB ({ram_pc:.0f}%)"
        self.card_ram.set_value(ram_txt, ram_pc or 0)

        self.card_disk.set_value("—")
        net_txt = f"↑ {getattr(s, 'net_up', 0)/1e6:.2f} MB/s ↓ {getattr(s, 'net_down', 0)/1e6:.2f} MB/s"
        self.card_net.set_value(net_txt)