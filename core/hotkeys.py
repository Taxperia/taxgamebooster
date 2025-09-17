from __future__ import annotations
import threading

try:
    import keyboard  # system-wide hotkeys
except Exception:
    keyboard = None

class HotkeyManager:
    def __init__(self):
        self._hooks: list[str] = []
        self._lock = threading.Lock()

    def active(self) -> bool:
        return keyboard is not None

    def register(self, combo: str, callback):
        if keyboard is None:
            return False
        with self._lock:
            keyboard.add_hotkey(combo, callback)
            self._hooks.append(combo)
        return True

    def clear(self):
        if keyboard is None:
            return
        with self._lock:
            for c in self._hooks:
                try:
                    keyboard.remove_hotkey(c)
                except Exception:
                    pass
            self._hooks.clear()