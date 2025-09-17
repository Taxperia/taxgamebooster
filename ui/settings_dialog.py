import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QFileDialog, QComboBox, QSpinBox, QLineEdit
from PySide6.QtCore import Qt
from core.settings import Settings
from ui.controls import ToggleSwitch

QUALITY_TO_BITRATE = {
    "low": 6.0,
    "medium": 12.0,
    "high": 20.0
}

def _list_tray_icons() -> list[str]:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dirp = os.path.join(base, "assets", "icons", "tray")
    names = []
    try:
        for fn in os.listdir(dirp):
            if fn.lower().endswith(".svg"):
                names.append(os.path.splitext(fn)[0])
    except Exception:
        pass
    # Fallback icons if directory doesn't exist
    if not names:
        names = ["tray1", "tray2", "tray3", "modern1", "modern2", "cyberpunk1", "minimal1"]
    return sorted(names)

class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ayarlar")
        self.settings = settings
        root = QVBoxLayout(self)

        # Tepsi ikonu
        root.addWidget(QLabel("Görünüm"))
        rowti = QHBoxLayout()
        rowti.addWidget(QLabel("Tepsi ikonu:"))
        self.combo_tray = QComboBox()
        self.combo_tray.addItems(_list_tray_icons())
        if self.settings.ui.tray_icon in [self.combo_tray.itemText(i) for i in range(self.combo_tray.count())]:
            self.combo_tray.setCurrentText(self.settings.ui.tray_icon)
        rowti.addWidget(self.combo_tray)
        root.addLayout(rowti)

        # Kayıt yolları
        root.addWidget(QLabel("Yollar"))
        rowp = QHBoxLayout()
        btn_vid = QPushButton(f"Video klasörü: {settings.paths.video_dir}")
        btn_ss = QPushButton(f"Screenshot klasörü: {settings.paths.screenshot_dir}")
        def _choose_video():
            d = QFileDialog.getExistingDirectory(self, "Video klasörü seç")
            if d:
                settings.paths.video_dir = d
                btn_vid.setText(f"Video klasörü: {d}")
        def _choose_ss():
            d = QFileDialog.getExistingDirectory(self, "Screenshot klasörü seç")
            if d:
                settings.paths.screenshot_dir = d
                btn_ss.setText(f"Screenshot klasörü: {d}")
        btn_vid.clicked.connect(_choose_video)
        btn_ss.clicked.connect(_choose_ss)
        rowp.addWidget(btn_vid)
        rowp.addWidget(btn_ss)
        root.addLayout(rowp)

        # Kayıt/Replay
        root.addWidget(QLabel("Kayıt ve Anında Yeniden Oynatma"))
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Konteyner:"))
        self.combo_container = QComboBox()
        self.combo_container.addItems(["mp4","mkv","mov"])
        self.combo_container.setCurrentText(settings.recording.container)
        row1.addWidget(self.combo_container)

        row1.addWidget(QLabel("Kalite:"))
        self.combo_quality = QComboBox()
        self.combo_quality.addItems(["low","medium","high","custom"])
        self.combo_quality.setCurrentText(settings.recording.quality_preset)
        row1.addWidget(self.combo_quality)

        row1.addWidget(QLabel("Bitrate (Mb/sn):"))
        self.spin_bitrate = QSpinBox()
        self.spin_bitrate.setRange(2, 100)
        self.spin_bitrate.setValue(int(settings.recording.bitrate_mbps))
        row1.addWidget(self.spin_bitrate)
        root.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Anında Tekrar (dk):"))
        self.spin_replay = QSpinBox()
        self.spin_replay.setRange(1, 10)
        self.spin_replay.setValue(int(settings.recording.replay_minutes))
        row2.addWidget(self.spin_replay)

        self.lbl_est = QLabel("Tahmini boyut: -")
        row2.addWidget(self.lbl_est)
        root.addLayout(row2)

        def _update_bitrate_from_quality():
            q = self.combo_quality.currentText()
            if q in QUALITY_TO_BITRATE:
                self.spin_bitrate.setValue(int(QUALITY_TO_BITRATE[q]))
        self.combo_quality.currentTextChanged.connect(_update_bitrate_from_quality)
        def _update_estimate():
            mins = self.spin_replay.value()
            br = self.spin_bitrate.value()
            est_mb = int((br * 60 * mins) / 8)
            self.lbl_est.setText(f"Tahmini boyut: ~{est_mb} MB")
        self.spin_replay.valueChanged.connect(lambda _: _update_estimate())
        self.spin_bitrate.valueChanged.connect(lambda _: _update_estimate())
        _update_estimate()

        # Hotkeys
        root.addWidget(QLabel("Kısayol Tuşları"))
        rowhk1 = QHBoxLayout()
        rowhk1.addWidget(QLabel("Kayıt Başlat/Durdur:"))
        self.edit_hk_rec = QLineEdit(settings.hotkeys.start_stop_record)
        rowhk1.addWidget(self.edit_hk_rec)
        root.addLayout(rowhk1)

        rowhk2 = QHBoxLayout()
        rowhk2.addWidget(QLabel("Ekran Görüntüsü:"))
        self.edit_hk_ss = QLineEdit(settings.hotkeys.screenshot)
        rowhk2.addWidget(self.edit_hk_ss)
        root.addLayout(rowhk2)

        rowhk3 = QHBoxLayout()
        rowhk3.addWidget(QLabel("Anında Tekrar Kaydet:"))
        self.edit_hk_rep = QLineEdit(settings.hotkeys.save_replay)
        rowhk3.addWidget(self.edit_hk_rep)
        root.addLayout(rowhk3)

        rowhk4 = QHBoxLayout()
        rowhk4.addWidget(QLabel("Global Hotkey:"))
        self.sw_global = ToggleSwitch(checked=settings.hotkeys.enable_global)
        def _toggle(v=None):
            self.sw_global.setChecked(not self.sw_global.isChecked() if v is None else v)
        self.sw_global.mousePressEvent = lambda e: (_toggle(), super(ToggleSwitch,self.sw_global).mousePressEvent(e) if False else None)
        rowhk4.addWidget(self.sw_global)
        root.addLayout(rowhk4)

        # Kaydet & Kapat
        rowb = QHBoxLayout()
        rowb.addStretch(1)
        btn_ok = QPushButton("Kaydet")
        btn_cancel = QPushButton("Vazgeç")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        rowb.addWidget(btn_cancel)
        rowb.addWidget(btn_ok)
        root.addLayout(rowb)

    def apply_to_settings(self):
        s = self.settings
        # tray icon
        s.ui.tray_icon = self.combo_tray.currentText()
        # recording
        s.recording.container = self.combo_container.currentText()
        s.recording.quality_preset = self.combo_quality.currentText()
        s.recording.bitrate_mbps = float(self.spin_bitrate.value())
        s.recording.replay_minutes = int(self.spin_replay.value())
        # hotkeys
        s.hotkeys.start_stop_record = self.edit_hk_rec.text().strip()
        s.hotkeys.screenshot = self.edit_hk_ss.text().strip()
        s.hotkeys.save_replay = self.edit_hk_rep.text().strip()
        s.hotkeys.enable_global = self.sw_global.isChecked()