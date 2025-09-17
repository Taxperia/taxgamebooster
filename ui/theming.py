import os
import sys
from typing import List
from PySide6.QtWidgets import QApplication

def _base_dir() -> str:
    if getattr(sys, "_MEIPASS", None):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _themes_dir() -> str:
    return os.path.join(_base_dir(), "themes")

def list_available_themes() -> List[str]:
    names: List[str] = []
    d = _themes_dir()
    try:
        for fn in os.listdir(d):
            if fn.lower().endswith(".qss"):
                names.append(os.path.splitext(fn)[0])
    except Exception:
        pass
    # Fallback themes
    fallbacks = ["modern-dark", "cyberpunk", "glass-morphism", "minimal-light", "pulse", "dark", "light"]
    for theme in fallbacks:
        if theme not in names:
            names.append(theme)
    return sorted(set(names), key=lambda x: x.lower())

def _read_qss(theme_name: str) -> str:
    fname = f"{theme_name.lower()}.qss"
    path = os.path.join(_themes_dir(), fname)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Theme read error for {theme_name}: {e}")
    # fallback
    fallback = os.path.join(_themes_dir(), "dark.qss")
    if os.path.isfile(fallback):
        try:
            with open(fallback, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return ""

def apply_theme(app: QApplication, theme: str) -> bool:
    qss = _read_qss(theme or "dark")
    app.setStyleSheet(qss)
    return bool(qss)