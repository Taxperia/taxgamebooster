import json
import os
import sys
from typing import Dict, Optional, List

_LOCALE_DATA: Dict[str, str] = {}
_CURRENT_LANG: str = "en"

def _base_dir() -> str:
    if getattr(sys, "_MEIPASS", None):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _locales_dir() -> str:
    return os.path.join(_base_dir(), "locales")

def _load_locale(lang: str) -> Optional[Dict[str, str]]:
    path = os.path.join(_locales_dir(), f"{lang}.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception as e:
        print(f"Locale load error for {lang}: {e}")
    return None

def list_available_languages() -> List[str]:
    langs: List[str] = []
    d = _locales_dir()
    try:
        for fn in os.listdir(d):
            if fn.lower().endswith(".json"):
                langs.append(os.path.splitext(fn)[0])
    except Exception:
        pass
    # En azından en ve tr olsun
    if "en" not in langs:
        langs.append("en")
    if "tr" not in langs:
        langs.append("tr")
    return sorted(set(langs), key=lambda x: x.lower())

def install_translator(app, language: str):
    global _LOCALE_DATA, _CURRENT_LANG
    lang = (language or "en").lower()
    data = _load_locale(lang)
    if data is None and lang != "en":
        data = _load_locale("en")
        lang = "en"
    _LOCALE_DATA = data or {}
    _CURRENT_LANG = lang

def t(key: str, default: Optional[str] = None) -> str:
    if not key:
        return ""
    return _LOCALE_DATA.get(key, default if default is not None else key)

def current_language() -> str:
    return _CURRENT_LANG