import os
from dataclasses import dataclass
import winreg
from pathlib import Path

RUN_KEYS = [
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
]

DISABLED_SUFFIX = "_PulseBoostDisabled"

@dataclass
class StartupItem:
    location: str
    name: str
    command: str
    enabled: bool

def list_startup_items() -> list[StartupItem]:
    items: list[StartupItem] = []
    for hive, path in RUN_KEYS:
        try:
            with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        items.append(StartupItem(location=f"{hive}-{path}", name=name, command=value, enabled=True))
                        i += 1
                    except OSError:
                        break
        except FileNotFoundError:
            pass
        # disabled bucket
        try:
            with winreg.OpenKey(hive, path + DISABLED_SUFFIX, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        items.append(StartupItem(location=f"{hive}-{path}{DISABLED_SUFFIX}", name=name, command=value, enabled=False))
                        i += 1
                    except OSError:
                        break
        except FileNotFoundError:
            pass
    return items

def set_startup_item_enabled(hive, path, name: str, enable: bool):
    src_key_path = path + (DISABLED_SUFFIX if enable is False else "")
    dst_key_path = path + ("" if enable is False else DISABLED_SUFFIX)
    # move value between keys
    try:
        with winreg.OpenKey(hive, src_key_path, 0, winreg.KEY_READ) as src:
            value, vtype = winreg.QueryValueEx(src, name)
    except FileNotFoundError:
        return
    # Ensure dest exists
    try:
        winreg.CreateKey(hive, dst_key_path)
    except Exception:
        pass
    with winreg.OpenKey(hive, dst_key_path, 0, winreg.KEY_SET_VALUE) as dst:
        winreg.SetValueEx(dst, name, 0, vtype, value)
    # delete from src
    with winreg.OpenKey(hive, src_key_path, 0, winreg.KEY_SET_VALUE) as src:
        try:
            winreg.DeleteValue(src, name)
        except FileNotFoundError:
            pass