from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QGuiApplication

# Bu overlay artık skin/renk/konum ayarlarını Settings.overlay içinden okur.

class SimpleOverlay(QWidget):
    def __init__(self, system_monitor, presentmon, settings):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlag(Qt.WindowTransparentForInput, True)  # click-through
        self._mon = system_monitor
        self._pm = presentmon
        self._settings = settings

        self.label = QLabel("", self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.label)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(500)

        self.apply_config()

    def apply_config(self):
        o = self._settings.overlay
        # Stil
        bg = f"rgba(0,0,0,{int(o.bg_opacity*255)})"
        fs = f"{o.font_size}pt"
        self.label.setStyleSheet(f"color: {o.colors.get('cpu','#00ff88')}; font: {fs} 'Consolas'; "
                                 f"background: {bg}; padding: 8px; border-radius: {o.border_radius}px;")
        # Boyut ve konum
        self.adjustSize()
        self._reposition()

    def _reposition(self):
        scr = QGuiApplication.primaryScreen().availableGeometry()  # QRect
        o = self._settings.overlay
        m = o.margin
        self.adjustSize()
        w, h = self.width(), self.height()
        x, y = m, m
        if o.position == "top-left":
            x, y = m, m
        elif o.position == "top-right":
            x, y = scr.width() - w - m, m
        elif o.position == "bottom-left":
            x, y = m, scr.height() - h - m
        elif o.position == "bottom-right":
            x, y = scr.width() - w - m, scr.height() - h - m
        self.move(scr.x() + x, scr.y() + y)

    def _format_lines(self, s):
        # Skin’e göre satırları oluştur
        o = self._settings.overlay
        colors = o.colors
        cpu = f"<span style='color:{colors.get('cpu','#7cff6b')}'>CPU {s.cpu_percent:.0f}% @ {float(s.cpu_freq or 0):.0f}MHz</span>"
        ram = f"<span style='color:{colors.get('ram','#00bcd4')}'>RAM {(s.ram_used or 0)/1_073_741_824:.1f}/{(s.ram_total or 0)/1_073_741_824:.1f}GiB ({getattr(s,'ram_percent',0):.0f}%)</span>"
        gpu_parts = []
        if s.gpu_util is not None:
            gpu_parts.append(f"{s.gpu_util:.0f}%")
        if getattr(s, 'gpu_temp', None) is not None:
            gpu_parts.append(f"{s.gpu_temp:.0f}°C")
        if getattr(s, 'gpu_power_w', None) is not None:
            gpu_parts.append(f"{s.gpu_power_w:.0f}W")
        gpu_txt = " ".join(gpu_parts) if gpu_parts else "—"
        gpu = f"<span style='color:{colors.get('gpu','#ffb74d')}'>GPU {gpu_txt}</span>"
        net = f"<span style='color:{colors.get('net','#90caf9')}'>↑ {getattr(s,'net_up',0)/1e6:.2f}MB/s ↓ {getattr(s,'net_down',0)/1e6:.2f}MB/s</span>"
        fps = ""
        try:
            if self._pm and self._pm.sample.fps > 0:
                fps = f"<span style='color:{colors.get('fps','#e0e0e0')}'>FPS {self._pm.sample.fps:.0f}</span>"
        except Exception:
            pass

        skin = o.skin
        cols = o.grid_columns
        if skin in ("minimal","mono"):
            return "<br>".join([cpu, ram, gpu, net, fps])
        elif skin in ("stacked","neon"):
            parts = [cpu, gpu, ram, net, fps]
            return "<br>".join([p for p in parts if p])
        elif skin in ("grid2","grid3","cards","bars","compact-corners","afterburner-like"):
            # basit grid: cols kadar yan yana, <table> ile
            items = [cpu, gpu, ram, net]
            if fps: items.append(fps)
            rows = []
            for i in range(0, len(items), cols):
                row = items[i:i+cols]
                tds = "".join([f"<td style='padding:4px 10px;'>{cell}</td>" for cell in row])
                rows.append(f"<tr>{tds}</tr>")
            return f"<table style='border-spacing:0px 2px'>{''.join(rows)}</table>"
        else:
            return "<br>".join([cpu, ram, gpu, net, fps])

    def _tick(self):
        try:
            s = self._mon.get()
            html = self._format_lines(s)
            self.label.setText(f"<div>{html}</div>")
            self._reposition()
        except Exception:
            pass