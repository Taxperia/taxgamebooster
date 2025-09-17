import sys
import os
import ctypes
import argparse
import signal
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.tray import SystemTray
from core.system_monitor import SystemMonitor
from core.power import AutoPowerPlanManager
from core.settings import Settings
from ui.theming import apply_theme
from ui.i18n import install_translator

APP_NAME = "PulseBoost"
VERSION = "0.2.1"

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

def main():
    if os.name != "nt":
        print("This application is Windows-only.")
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("--minimized", action="store_true", help="Tepsiye küçültülmüş başlat")
    args, _ = parser.parse_known_args()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("PulseBoost")
    app.setApplicationVersion(VERSION)

    signal.signal(signal.SIGINT, lambda *a: QApplication.quit())

    settings = Settings.load()
    install_translator(app, settings.ui.language)
    apply_theme(app, settings.ui.theme)

    system_monitor = SystemMonitor()
    system_monitor.start()

    power_manager = AutoPowerPlanManager(system_monitor)
    if settings.power.auto_switch:
        power_manager.start()

    window = MainWindow(system_monitor=system_monitor, settings=settings, power_manager=power_manager)
    tray = SystemTray(window, system_monitor, settings)
    # MainWindow içinden tepsi ikonunu canlı yenilemek için referans ver
    window._tray = tray

    if settings.startup.run_on_boot:
        try:
            from core.startup import ensure_startup_enabled
            ensure_startup_enabled(True)
        except Exception as e:
            print("Failed to set startup:", e)

    start_minimized = args.minimized or settings.startup.start_minimized
    if start_minimized:
        window.hide()
    else:
        window.show()

    ret = app.exec()

    try:
        power_manager.stop()
    except Exception:
        pass
    system_monitor.stop()
    sys.exit(ret)

if __name__ == "__main__":
    main()