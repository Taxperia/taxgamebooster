import os
import shutil
import ctypes
from pathlib import Path

def _try_delete(path: Path):
    try:
        if path.is_file() or path.is_symlink():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass

def clean_temp_and_prefetch():
    # Windows temp
    temp_dirs = [
        Path(os.environ.get("TEMP", "")),
        Path(os.environ.get("TMP", "")),
        Path(r"C:\Windows\Temp"),
        Path(r"C:\Windows\Prefetch"),
    ]
    for d in temp_dirs:
        if d and d.exists():
            for child in d.iterdir():
                _try_delete(child)