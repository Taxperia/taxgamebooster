from __future__ import annotations

import os
import subprocess
import threading
import json
import time
from typing import Optional, Callable

import psutil
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QTabWidget,
    QFileDialog, QSpinBox, QComboBox, QListWidget, QListWidgetItem, QLineEdit,
    QMessageBox, QAbstractItemView, QTableWidget, QTableWidgetItem, QToolBar
)

from core.settings import Settings
from core.system_monitor import SystemMonitor
from core.temp_cleaner import clean_temp_and_prefetch
from core.power import AutoPowerPlanManager
from core.startup_programs import list_startup_items, set_startup_item_enabled
from recording.recorder import ScreenRecorder
from recording.instant_replay import InstantReplay, estimate_replay_size_mb
from recording.screenshot import take_screenshot
from core.benchmark import cpu_stress, gpu_nvenc_stress
from core.fps_presentmon import PresentMonMonitor
from core.process_manager import PerformanceMode
from core.services import list_services, stop_service, get_service_description
from overlay.transparent_overlay import SimpleOverlay
from overlay.rtss_osd import RTSSOSDClient
from ui.widgets import DashboardWidget, icon
from ui.settings_dialog import SettingsDialog
from core.hotkeys import HotkeyManager
from ui.speedtest_widget import SpeedtestWidget


class MainWindow(QMainWindow):
    # Ana thread'e güvenli UI işlemleri için sinyaller
    sig_status = Signal(str, int)
    sig_call = Signal(object)

    def __init__(self, system_monitor: SystemMonitor, settings: Settings, power_manager: AutoPowerPlanManager):
        super().__init__()
        self.setWindowTitle("PulseBoost")
        self.resize(1360, 900)

        # Bağımlılıklar
        self.system_monitor = system_monitor
        self.settings = settings
        self.power_manager = power_manager

        # Thread-safe UI
        self.sig_status.connect(lambda msg, ms: self.statusBar().showMessage(msg, ms))
        self.sig_call.connect(lambda fn: fn())

        # Üst araç çubuğu: Ayarlar modal butonu
        tb = QToolBar()
        btn_settings = QPushButton(icon("settings"), "Ayarlar")
        btn_settings.clicked.connect(self._open_settings)
        tb.addWidget(btn_settings)
        self.addToolBar(Qt.TopToolBarArea, tb)

        # Sekme kökü
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # FPS için PresentMon ve Performans modu kontrolcüsü
        self._pm = PresentMonMonitor(self.settings.tools.presentmon_path or "")
        self._perf_mode = PerformanceMode(
            self.settings.performance.whitelist_processes,
            self.settings.performance.suspend_cpu_threshold
        )

        # Leaderboard dosyası (her zaman geçerli bir yol)
        self.leaderboard_file = self.settings.benchmark.leaderboard_path or os.path.join(
            os.path.expanduser("~"), "AppData", "Roaming", "PulseBoost", "benchmarks.json"
        )
        os.makedirs(os.path.dirname(self.leaderboard_file), exist_ok=True)

        # Sekmeler
        self._build_dashboard_tab()
        self._build_tools_tab()
        self._build_recording_tab()
        self._build_benchmark_tab()
        self._build_speedtest_tab()
        self._build_game_mode_tab()
        self._build_services_tab()

        # Kayıt ve Anında Tekrar
        self._recorder = ScreenRecorder(self.settings)
        self._replay = InstantReplay(self.settings)
        if self.settings.recording.instant_replay:
            threading.Thread(target=self._safe_start_replay, daemon=True).start()

        # Overlay/OSD
        self._overlay: Optional[SimpleOverlay] = None
        self._rtss: Optional[RTSSOSDClient] = None
        if self.settings.ui.show_overlay:
            self._init_overlay()

        # Zamanlayıcılar
        self._metrics_timer = QTimer(self)
        self._metrics_timer.timeout.connect(self._update_metrics)
        self._metrics_timer.start(1000)

        self._perf_timer = QTimer(self)
        self._perf_timer.timeout.connect(self._maintain_perf_mode)
        self._perf_timer.start(2000)

        # Global Hotkeys
        self._hk = HotkeyManager()
        self._install_hotkeys()

        self.statusBar().showMessage("Hazır")

    # =================== Yardımcılar (thread-safe) ===================
    def _status(self, msg: str, ms: int = 5000):
        self.sig_status.emit(msg, ms)

    def _post(self, fn: Callable[[], None]):
        self.sig_call.emit(fn)

    # =================== Ayarlar (Modal) ===================
    def _open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            dlg.apply_to_settings()
            self.settings.save()
            # Tepsi ikonu canlı yenile (app.py MainWindow._tray atıyor)
            if hasattr(self, "_tray") and self._tray:
                try:
                    self._tray.refresh_icon()
                except Exception:
                    pass
            # Hotkeys yeniden kur
            self._install_hotkeys()
            self._status("Ayarlar kaydedildi", 3000)

    # =================== Global Hotkeys ===================
    def _install_hotkeys(self):
        # Her durumda eski kayıtları temizle
        self._hk.clear()
        # Global hotkey desteği yoksa veya devre dışı ise çık
        if not self.settings.hotkeys.enable_global or not self._hk.active():
            return
        # Kayıt/durdur
        self._hk.register(self.settings.hotkeys.start_stop_record, self._hotkey_toggle_record)
        # Ekran görüntüsü
        self._hk.register(self.settings.hotkeys.screenshot, self._hotkey_screenshot)
        # Anında tekrar kaydet
        self._hk.register(self.settings.hotkeys.save_replay, self._hotkey_save_replay)

    def _hotkey_toggle_record(self):
        try:
            if getattr(self._recorder, "_running", False):
                self._recorder.stop()
                self._status("Kayıt durduruldu", 3000)
            else:
                self._recorder.start()
                self._status("Kayıt başladı", 3000)
        except Exception as e:
            print("Hotkey record error:", e)

    def _hotkey_screenshot(self):
        try:
            path = take_screenshot(self.settings)
            self._status(f"Ekran görüntüsü: {path}", 4000)
        except Exception as e:
            print("Hotkey screenshot error:", e)

    def _hotkey_save_replay(self):
        try:
            out = self._replay.save_replay()
            if out:
                self._status(f"Anında tekrar: {out}", 4000)
        except Exception as e:
            print("Hotkey replay error:", e)

    # =================== Overlay / OSD ===================
    def _init_overlay(self):
        try:
            if self.settings.ui.use_rtss:
                self._rtss = RTSSOSDClient("PulseBoost")
            self._overlay = SimpleOverlay(
                system_monitor=self.system_monitor,
                presentmon=self._pm,
                settings=self.settings
            )
            self._overlay.apply_config()
            self._overlay.show()
        except Exception as e:
            print("Overlay başlatma hatası:", e)

    def _toggle_overlay(self):
        self.settings.ui.show_overlay = not self.settings.ui.show_overlay
        self.settings.save()
        if self.settings.ui.show_overlay:
            self._init_overlay()
        else:
            try:
                if self._overlay:
                    self._overlay.close()
            except Exception:
                pass
            self._overlay = None

    # =================== Dashboard ===================
    def _build_dashboard_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)

        self.dashboard = DashboardWidget(self.system_monitor)
        v.addWidget(self.dashboard)

        row = QHBoxLayout()
        btn_clean = QPushButton(icon("disk"), "Temp/Prefetch Temizle")
        btn_clean.clicked.connect(self._clean_temp_async)
        row.addWidget(btn_clean)

        btn_overlay = QPushButton(icon("gauge"), "Overlay Aç/Kapat")
        btn_overlay.clicked.connect(self._toggle_overlay)
        row.addWidget(btn_overlay)

        row.addStretch(1)
        v.addLayout(row)

        self.tabs.addTab(w, "Gösterge")

    def _clean_temp_async(self):
        self._status("Geçici dosyalar temizleniyor...")
        def run():
            try:
                clean_temp_and_prefetch()
                self._status("Geçici dosyalar temizlendi", 4000)
            except Exception as e:
                self._status(f"Temizlik hatası: {e}", 8000)
        threading.Thread(target=run, daemon=True).start()

    # =================== Araçlar (Başlangıç Programları) ===================
    def _build_tools_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)

        top = QHBoxLayout()
        top.addWidget(QLabel("Başlangıç Programları"))
        top.addStretch(1)
        self.edit_startup_filter = QLineEdit()
        self.edit_startup_filter.setPlaceholderText("Ara (ad/komut)")
        self.edit_startup_filter.textChanged.connect(self._refresh_startup)
        btn_refresh = QPushButton("Yenile")
        btn_refresh.clicked.connect(self._refresh_startup)
        btn_enable_all = QPushButton("Tümünü Etkinleştir")
        btn_enable_all.clicked.connect(lambda: self._toggle_startup_all(True))
        btn_disable_all = QPushButton("Tümünü Devre Dışı")
        btn_disable_all.clicked.connect(lambda: self._toggle_startup_all(False))
        top.addWidget(self.edit_startup_filter)
        top.addWidget(btn_refresh)
        top.addWidget(btn_enable_all)
        top.addWidget(btn_disable_all)
        v.addLayout(top)

        self.tbl_startup = QTableWidget(0, 4)
        self.tbl_startup.setHorizontalHeaderLabels(["Ad", "Durum", "Konum", "Komut"])
        self.tbl_startup.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_startup.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tbl_startup.horizontalHeader().setStretchLastSection(True)
        v.addWidget(self.tbl_startup)

        row = QHBoxLayout()
        btn_enable = QPushButton("Seçileni Etkinleştir")
        btn_enable.clicked.connect(lambda: self._toggle_startup_item(True))
        btn_disable = QPushButton("Seçileni Devre Dışı")
        btn_disable.clicked.connect(lambda: self._toggle_startup_item(False))
        row.addStretch(1)
        row.addWidget(btn_enable)
        row.addWidget(btn_disable)
        v.addLayout(row)

        self.tabs.addTab(w, "Araçlar")
        self._refresh_startup()

    def _refresh_startup(self):
        filt = (self.edit_startup_filter.text() or "").lower()
        self.tbl_startup.setRowCount(0)
        try:
            items = list_startup_items()
            for it in items:
                if filt and (filt not in it.name.lower()) and (filt not in (it.command or "").lower()):
                    continue
                r = self.tbl_startup.rowCount()
                self.tbl_startup.insertRow(r)
                self.tbl_startup.setItem(r, 0, QTableWidgetItem(it.name))
                self.tbl_startup.setItem(r, 1, QTableWidgetItem("Etkin" if it.enabled else "Pasif"))
                self.tbl_startup.setItem(r, 2, QTableWidgetItem(it.location))
                self.tbl_startup.setItem(r, 3, QTableWidgetItem(it.command))
                self.tbl_startup.item(r, 0).setData(Qt.UserRole, it)
        except Exception as e:
            QMessageBox.warning(self, "Başlangıç Programları", f"Liste alınamadı:\n{e}")

    def _selected_startup_item(self):
        row = self.tbl_startup.currentRow()
        if row < 0:
            return None
        return self.tbl_startup.item(row, 0).data(Qt.UserRole)

    def _toggle_startup_item(self, enable: bool):
        it = self._selected_startup_item()
        if not it:
            return
        try:
            hive_str, _path = it.location.split("-", 1)
            import winreg
            hive = winreg.HKEY_CURRENT_USER if "HKEY_CURRENT_USER" in hive_str else winreg.HKEY_LOCAL_MACHINE
            set_startup_item_enabled(hive, r"Software\Microsoft\Windows\CurrentVersion\Run", it.name, enable)
            self._refresh_startup()
            self._status(f"{it.name}: {'Etkinleştirildi' if enable else 'Devre dışı'}", 4000)
        except Exception as e:
            QMessageBox.warning(self, "Başlangıç Programları", f"Değiştirilemedi:\n{e}")

    def _toggle_startup_all(self, enable: bool):
        try:
            items = list_startup_items()
            import winreg
            for it in items:
                try:
                    hive_str, _path = it.location.split("-", 1)
                    hive = winreg.HKEY_CURRENT_USER if "HKEY_CURRENT_USER" in hive_str else winreg.HKEY_LOCAL_MACHINE
                    set_startup_item_enabled(hive, r"Software\Microsoft\Windows\CurrentVersion\Run", it.name, enable)
                except Exception:
                    continue
            self._refresh_startup()
            self._status("Tümü güncellendi", 3000)
        except Exception as e:
            QMessageBox.warning(self, "Başlangıç Programları", f"Toplu işlem başarısız:\n{e}")

    # =================== Kayıt ===================
    def _build_recording_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)

        header = QHBoxLayout()
        header.addWidget(QLabel("Kayıt"))
        header.addStretch(1)
        self.lbl_est = QLabel("-")
        header.addWidget(self.lbl_est)
        v.addLayout(header)

        # Satır 1: FPS, Encoder, Format
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("FPS:"))
        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(15, 240)
        self.spin_fps.setValue(self.settings.recording.fps)
        row1.addWidget(self.spin_fps)

        row1.addWidget(QLabel("Encoder:"))
        self.combo_encoder = QComboBox()
        self.combo_encoder.addItems(["h264_nvenc", "hevc_nvenc", "h264_qsv", "libx264"])
        self.combo_encoder.setCurrentText(self.settings.recording.encoder)
        row1.addWidget(self.combo_encoder)

        row1.addWidget(QLabel("Format:"))
        self.combo_container = QComboBox()
        self.combo_container.addItems(["mp4", "mkv", "mov"])
        self.combo_container.setCurrentText(self.settings.recording.container)
        row1.addWidget(self.combo_container)

        row1.addStretch(1)
        v.addLayout(row1)

        # Satır 2: Kalite, Bitrate, Replay (dk)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Kalite:"))
        self.combo_quality = QComboBox()
        self.combo_quality.addItems(["low", "medium", "high", "custom"])
        self.combo_quality.setCurrentText(self.settings.recording.quality_preset)
        row2.addWidget(self.combo_quality)

        row2.addWidget(QLabel("Bitrate (Mb/sn):"))
        self.spin_bitrate = QSpinBox()
        self.spin_bitrate.setRange(2, 100)
        self.spin_bitrate.setValue(int(self.settings.recording.bitrate_mbps))
        row2.addWidget(self.spin_bitrate)

        row2.addWidget(QLabel("Anında Tekrar (dk):"))
        self.spin_replay = QSpinBox()
        self.spin_replay.setRange(1, 10)
        self.spin_replay.setValue(self.settings.recording.replay_minutes)
        row2.addWidget(self.spin_replay)

        def _update_est():
            mb = estimate_replay_size_mb(self.spin_replay.value(), float(self.spin_bitrate.value()))
            self.lbl_est.setText(f"Tahmini boyut (replay): ~{mb} MB")
        self.spin_replay.valueChanged.connect(lambda _: _update_est())
        self.spin_bitrate.valueChanged.connect(lambda _: _update_est())
        _update_est()

        v.addLayout(row2)

        # Butonlar
        row3 = QHBoxLayout()
        btn_start = QPushButton("Kaydı Başlat")
        btn_start.clicked.connect(self._start_record)
        row3.addWidget(btn_start)

        btn_stop = QPushButton("Kaydı Durdur")
        btn_stop.clicked.connect(self._stop_record)
        row3.addWidget(btn_stop)

        btn_ss = QPushButton("Ekran Görüntüsü")
        btn_ss.clicked.connect(self._screenshot)
        row3.addWidget(btn_ss)

        btn_replay = QPushButton("Anında Tekrar Kaydet")
        btn_replay.clicked.connect(self._save_replay)
        row3.addWidget(btn_replay)

        row3.addStretch(1)
        v.addLayout(row3)

        self.tabs.addTab(w, "Kayıt")

    def _apply_recording_from_ui(self):
        self.settings.recording.fps = self.spin_fps.value()
        self.settings.recording.encoder = self.combo_encoder.currentText()
        self.settings.recording.container = self.combo_container.currentText()
        self.settings.recording.quality_preset = self.combo_quality.currentText()
        self.settings.recording.bitrate_mbps = float(self.spin_bitrate.value())
        self.settings.recording.replay_minutes = self.spin_replay.value()
        self.settings.save()

    def _start_record(self):
        self._apply_recording_from_ui()
        try:
            out = self._recorder.start()
            self._status(f"Kayıt başladı: {out}", 6000)
        except Exception as e:
            QMessageBox.critical(self, "Kayıt", f"Kayıt başlatılamadı:\n{e}")

    def _stop_record(self):
        try:
            self._recorder.stop()
            self._status("Kayıt durdu", 4000)
        except Exception as e:
            QMessageBox.warning(self, "Kayıt", f"Kapatılamadı:\n{e}")

    def _screenshot(self):
        def run():
            try:
                out = take_screenshot(self.settings)
                self._status(f"Ekran görüntüsü: {out}", 6000)
            except Exception as e:
                self._status(f"Ekran görüntüsü hatası: {e}", 8000)
        threading.Thread(target=run, daemon=True).start()

    def _save_replay(self):
        def run():
            try:
                out = self._replay.save_replay()
                if out:
                    self._status(f"Anında tekrar: {out}", 6000)
                else:
                    self._status("Segment bulunamadı", 5000)
            except Exception as e:
                self._status(f"Anında tekrar hatası: {e}", 8000)
        threading.Thread(target=run, daemon=True).start()

    # =================== Benchmark ===================
    def _build_benchmark_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)

        v.addWidget(QLabel("Benchmark — CPU/GPU testleri; skor hesaplanır ve yerel liderlik tablosuna eklenir."))

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("CPU Süre (sn):"))
        self.spin_cpu_sec = QSpinBox()
        self.spin_cpu_sec.setRange(5, 240)
        self.spin_cpu_sec.setValue(self.settings.benchmark.cpu_seconds)
        row1.addWidget(self.spin_cpu_sec)

        btn_cpu = QPushButton("CPU Test")
        btn_cpu.clicked.connect(self._run_cpu_bench)
        row1.addWidget(btn_cpu)

        self.lbl_cpu_res = QLabel("-")
        row1.addWidget(self.lbl_cpu_res)
        row1.addStretch(1)
        v.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("GPU Süre (sn):"))
        self.spin_gpu_sec = QSpinBox()
        self.spin_gpu_sec.setRange(10, 240)
        self.spin_gpu_sec.setValue(self.settings.benchmark.gpu_seconds)
        row2.addWidget(self.spin_gpu_sec)

        btn_gpu = QPushButton("GPU (NVENC) Test")
        btn_gpu.clicked.connect(self._run_gpu_bench)
        row2.addWidget(btn_gpu)

        self.lbl_gpu_res = QLabel("-")
        row2.addWidget(self.lbl_gpu_res)
        row2.addStretch(1)
        v.addLayout(row2)

        self.lbl_score = QLabel("Skor: -")
        v.addWidget(self.lbl_score)

        self.list_lb = QListWidget()
        v.addWidget(self.list_lb)
        self._load_leaderboard()

        self.tabs.addTab(w, "Benchmark")

    def _calc_score_and_save(self, cpu_gflops: float, gpu_ok: bool):
        score = int(cpu_gflops * 10 + (100 if gpu_ok else 0))
        self.lbl_score.setText(f"Skor: {score}")
        try:
            lb = []
            if os.path.exists(self.leaderboard_file):
                with open(self.leaderboard_file, "r", encoding="utf-8") as f:
                    lb = json.load(f)
            lb.append({"ts": int(time.time()), "score": score})
            lb = sorted(lb, key=lambda x: x["score"], reverse=True)[:50]
            with open(self.leaderboard_file, "w", encoding="utf-8") as f:
                json.dump(lb, f, ensure_ascii=False, indent=2)
            self._load_leaderboard()
        except Exception as e:
            print("Leaderboard save err:", e)

    def _load_leaderboard(self):
        self.list_lb.clear()
        try:
            if self.leaderboard_file and os.path.exists(self.leaderboard_file):
                with open(self.leaderboard_file, "r", encoding="utf-8") as f:
                    lb = json.load(f)
                for i, it in enumerate(lb, 1):
                    self.list_lb.addItem(f"#{i} — Skor {it['score']}")
        except Exception as e:
            print("Leaderboard load err:", e)

    def _run_cpu_bench(self):
        sec = self.spin_cpu_sec.value()
        self.lbl_cpu_res.setText("Çalışıyor...")
        def run():
            try:
                res = cpu_stress(sec)
                self._post(lambda: self.lbl_cpu_res.setText(f"CPU: {res['gflops']} GFLOPS"))
                self._calc_score_and_save(res["gflops"], gpu_ok=False)
            except Exception as e:
                self._post(lambda: self.lbl_cpu_res.setText(f"Hata: {e}"))
        threading.Thread(target=run, daemon=True).start()

    def _run_gpu_bench(self):
        sec = self.spin_gpu_sec.value()
        self.lbl_gpu_res.setText("Çalışıyor...")
        def run():
            try:
                res = gpu_nvenc_stress(sec, self.settings.recording.encoder)
                if res.get("ok"):
                    self._post(lambda: self.lbl_gpu_res.setText(f"NVENC OK ({res['seconds']} sn)"))
                    self._calc_score_and_save(cpu_gflops=0.0, gpu_ok=True)
                else:
                    self._post(lambda: self.lbl_gpu_res.setText(f"Hata: {res.get('error')}"))
            except Exception as e:
                self._post(lambda: self.lbl_gpu_res.setText(f"Hata: {e}"))
        threading.Thread(target=run, daemon=True).start()

    # =================== İnternet Hızı ===================
    def _build_speedtest_tab(self):
        w = SpeedtestWidget(self.settings)
        self.tabs.addTab(w, "İnternet Hızı")

    # =================== Oyun Modu ===================
    def _build_game_mode_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)

        v.addWidget(QLabel("Oyun Modu — Oyunu başlat, FPS izleme ve performans modunu etkinleştir."))

        row = QHBoxLayout()
        row.addWidget(QLabel("PresentMon.exe Yolu:"))
        self.edit_pm_path = QLineEdit(self.settings.tools.presentmon_path or "")
        row.addWidget(self.edit_pm_path)
        btn_browse_pm = QPushButton("Gözat")
        btn_browse_pm.clicked.connect(self._browse_presentmon)
        row.addWidget(btn_browse_pm)
        v.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Oyun EXE:"))
        self.edit_game_exe = QLineEdit("")
        row2.addWidget(self.edit_game_exe)
        btn_browse_game = QPushButton("Seç")
        btn_browse_game.clicked.connect(self._browse_game_exe)
        row2.addWidget(btn_browse_game)
        v.addLayout(row2)

        row3 = QHBoxLayout()
        btn_launch = QPushButton("Oyunu Başlat (Performans Modu)")
        btn_launch.clicked.connect(self._launch_game_perf)
        row3.addWidget(btn_launch)

        btn_stop_perf = QPushButton("Performans Modunu Kapat")
        btn_stop_perf.clicked.connect(self._stop_perf_mode)
        row3.addWidget(btn_stop_perf)
        row3.addStretch(1)
        v.addLayout(row3)

        row4 = QHBoxLayout()
        self.combo_procs = QComboBox()
        self._refresh_proc_list()
        btn_refresh_list = QPushButton("Süreçleri Yenile")
        btn_refresh_list.clicked.connect(self._refresh_proc_list)
        btn_attach = QPushButton("FPS İzlemeye Başla")
        btn_attach.clicked.connect(self._attach_presentmon_to_selected)
        row4.addWidget(self.combo_procs)
        row4.addWidget(btn_refresh_list)
        row4.addWidget(btn_attach)
        row4.addStretch(1)
        v.addLayout(row4)

        self.tabs.addTab(w, "Oyun Modu")

    def _browse_presentmon(self):
        p = QFileDialog.getOpenFileName(self, "PresentMon.exe seç", "", "Executable (*.exe)")[0]
        if p:
            self.edit_pm_path.setText(p)
            self.settings.tools.presentmon_path = p
            self.settings.save()
            self._pm = PresentMonMonitor(p)
            self._status("PresentMon yolu güncellendi", 3000)

    def _browse_game_exe(self):
        p = QFileDialog.getOpenFileName(self, "Oyun EXE seç", "", "Executable (*.exe)")[0]
        if p:
            self.edit_game_exe.setText(p)

    def _launch_game_perf(self):
        exe = self.edit_game_exe.text().strip()
        if not exe or not os.path.isfile(exe):
            QMessageBox.warning(self, "Oyun", "Geçerli bir oyun EXE seçin.")
            return
        try:
            proc = subprocess.Popen([exe], cwd=os.path.dirname(exe))
            pid = proc.pid
            # Ayarları not al
            self.settings.performance.enable_performance_mode = True
            self.settings.performance.target_process_name = os.path.basename(exe)
            self.settings.save()
            # PresentMon bağla
            try:
                if self._pm and self._pm.available():
                    self._pm.stop()
                    self._pm.start(process_name=os.path.basename(exe))
            except Exception as e:
                print("PresentMon başlatılamadı:", e)
            # Performans modu
            self._perf_mode.start_for_process(pid)
            self._status(f"Oyun başlatıldı (PID {pid}) ve performans modu etkin", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Oyun", f"Başlatılamadı:\n{e}")

    def _refresh_proc_list(self):
        self.combo_procs.clear()
        data = []
        for p in psutil.process_iter(["pid", "name"]):
            try:
                name = p.info.get("name") or ""
                if name:
                    data.append((f"{name} (PID {p.info['pid']})", p.info["pid"]))
            except Exception:
                continue
        for label, pid in sorted(data, key=lambda x: x[0].lower()):
            self.combo_procs.addItem(label, pid)

    def _attach_presentmon_to_selected(self):
        if not self._pm or not self._pm.available():
            QMessageBox.information(self, "PresentMon", "PresentMon yolu ayarlı değil.")
            return
        idx = self.combo_procs.currentIndex()
        pid = self.combo_procs.itemData(idx)
        try:
            self._pm.stop()
        except Exception:
            pass
        try:
            self._pm.start(pid=int(pid))
            self._status(f"PresentMon PID {pid} ile başladı", 4000)
        except Exception as e:
            QMessageBox.warning(self, "PresentMon", f"Başlatılamadı:\n{e}")

    def _maintain_perf_mode(self):
        try:
            if self.settings.performance.enable_performance_mode:
                self._perf_mode.maintain()
        except Exception as e:
            print("Perf mode maintain hatası:", e)

    def _stop_perf_mode(self):
        try:
            self.settings.performance.enable_performance_mode = False
            self.settings.save()
            try:
                if self._pm:
                    self._pm.stop()
            except Exception:
                pass
            self._perf_mode.stop()
            self._status("Performans modu kapatıldı", 4000)
        except Exception as e:
            QMessageBox.warning(self, "Performans Modu", f"Kapatılamadı:\n{e}")

    # =================== Servisler ===================
    def _build_services_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)

        v.addWidget(QLabel("Servisler — Bilgi (i) butonuna tıklayarak açıklamayı görüntüleyin."))

        self.list_services_widget = QListWidget()
        v.addWidget(self.list_services_widget)

        row = QHBoxLayout()
        btn_refresh = QPushButton("Yenile")
        btn_refresh.clicked.connect(self._refresh_services)
        btn_stop = QPushButton("Seçileni Durdur")
        btn_stop.clicked.connect(self._stop_selected_service)
        row.addStretch(1)
        row.addWidget(btn_refresh)
        row.addWidget(btn_stop)
        v.addLayout(row)

        self.tabs.addTab(w, "Servisler")
        self._refresh_services()

    def _refresh_services(self):
        self.list_services_widget.clear()
        try:
            for svc in list_services():
                item = QListWidgetItem(f"{svc.display_name} [{svc.status}]")
                item.setData(Qt.UserRole, svc)
                item.setIcon(icon("service_info"))
                self.list_services_widget.addItem(item)
        except Exception as e:
            QMessageBox.warning(self, "Servisler", f"Liste alınamadı:\n{e}")

    def _stop_selected_service(self):
        it = self.list_services_widget.currentItem()
        if not it:
            return
        svc = it.data(Qt.UserRole)
        desc = get_service_description(svc.name)
        ask = QMessageBox.question(self, "Servisi Durdur?",
                                   f"{svc.display_name}\n\n{desc}\n\nDurdurulsun mu?")
        if ask != QMessageBox.Yes:
            return
        if not getattr(svc, "can_stop", True):
            QMessageBox.information(self, "Servis", "Bu servis kritik olabilir, durdurulması önerilmez.")
            return
        ok = stop_service(svc.name)
        self._status(("Durduruldu" if ok else "Durdurulamadı") + f": {svc.name}", 5000)
        self._refresh_services()

    # =================== Döngüler / Kapanış ===================
    def _safe_start_replay(self):
        try:
            self._replay.start()
        except Exception as e:
            print("Instant Replay başlatılamadı:", e)

    def _update_metrics(self):
        try:
            # Dashboard kendi timer'ı ile yenileniyor; tetikleyici fonksiyon kalabilir
            self.dashboard.update_from_snapshot(self.system_monitor.get())
        except Exception as e:
            print("Metrik güncelleme hatası:", e)

    def closeEvent(self, event):
        # Kaynakları güvenle kapat
        try:
            if self._overlay:
                self._overlay.close()
        except Exception:
            pass
        try:
            if self._rtss:
                self._rtss.close()
        except Exception:
            pass
        try:
            if self._replay:
                self._replay.stop()
        except Exception:
            pass
        try:
            if self._pm:
                self._pm.stop()
        except Exception:
            pass
        try:
            self._perf_mode.stop()
        except Exception:
            pass
        super().closeEvent(event)