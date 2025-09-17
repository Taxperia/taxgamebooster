import os
import winreg

APP_NAME = "PulseBoost"
# Path to current executable or script
def _get_exec_path():
    import sys
    if getattr(sys, 'frozen', False):
        return sys.executable
    return sys.executable + " " + os.path.abspath(sys.argv[0])

def ensure_startup_enabled(enabled: bool):
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _get_exec_path())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass