import os
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication, QStyle
from PySide6.QtGui import QAction, QIcon
from core.settings import Settings

def _tray_icon_path(settings: Settings) -> str | None:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cand = os.path.join(base, "assets", "icons", "tray", f"{settings.ui.tray_icon}.svg")
    return cand if os.path.isfile(cand) else None

class SystemTray(QSystemTrayIcon):
    def __init__(self, main_window, system_monitor, settings: Settings):
        self.settings = settings
        icon = self._make_icon()
        super().__init__(icon)
        self.main_window = main_window
        self.setToolTip("PulseBoost")

        menu = QMenu()
        act_show = QAction("Aç")
        act_show.triggered.connect(self.show_main)
        menu.addAction(act_show)

        act_toggle_overlay = QAction("Overlay Aç/Kapat")
        act_toggle_overlay.triggered.connect(self._toggle_overlay)
        menu.addAction(act_toggle_overlay)

        act_exit = QAction("Çıkış")
        act_exit.triggered.connect(self.exit_app)
        menu.addAction(act_exit)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)
        self.show()

    def _make_icon(self) -> QIcon:
        p = _tray_icon_path(self.settings)
        if p:
            return QIcon(p)
        return QApplication.style().standardIcon(QStyle.SP_ComputerIcon)

    def refresh_icon(self):
        self.setIcon(self._make_icon())

    def _on_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_main()

    def show_main(self):
        self.main_window.showNormal()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def exit_app(self):
        QApplication.quit()

    def _toggle_overlay(self):
        try:
            want = not self.settings.ui.show_overlay
            self.settings.ui.show_overlay = want
            self.settings.save()
            if want:
                if getattr(self.main_window, "_overlay", None) is None:
                    self.main_window._init_overlay()
            else:
                if getattr(self.main_window, "_overlay", None):
                    self.main_window._overlay.close()
                    self.main_window._overlay = None
        except Exception as e:
            print("Toggle overlay error:", e)