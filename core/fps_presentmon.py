import os
import subprocess
import threading
import time
import csv
from dataclasses import dataclass
from typing import Optional

@dataclass
class FPSSample:
    fps: float = 0.0
    process_name: str = ""
    pid: Optional[int] = None

class PresentMonMonitor:
    """
    PresentMon CSV çıktısını dosyaya alır ve tail ederek FPS hesaplar.
    Kullanım: start(process_name="game.exe") veya start(pid=1234)
    """
    def __init__(self, presentmon_path: str):
        self.presentmon_path = presentmon_path
        self._proc: Optional[subprocess.Popen] = None
        self._tail_thread: Optional[threading.Thread] = None
        self._running = False
        self._output_csv = None
        self.sample = FPSSample()

    def available(self) -> bool:
        return bool(self.presentmon_path and os.path.isfile(self.presentmon_path))

    def start(self, process_name: str | None = None, pid: int | None = None):
        if not self.available():
            raise RuntimeError("PresentMon yolu ayarlı değil veya bulunamadı.")
        ts = int(time.time())
        out_dir = os.path.join(os.getenv("TEMP", "."), "PulseBoost")
        os.makedirs(out_dir, exist_ok=True)
        self._output_csv = os.path.join(out_dir, f"presentmon_{ts}.csv")
        args = [self.presentmon_path, "-output_file", self._output_csv, "-no_summary", "-append", "-terminate_on_proc_exit"]
        if process_name:
            args += ["-process_name", process_name]
            self.sample.process_name = process_name
        if pid:
            args += ["-process_id", str(pid)]
            self.sample.pid = pid
        # per-present CSV
        args += ["-csv"]
        self._proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._running = True
        self._tail_thread = threading.Thread(target=self._tail_loop, daemon=True)
        self._tail_thread.start()

    def stop(self):
        self._running = False
        try:
            if self._proc:
                self._proc.terminate()
        except Exception:
            pass

    def _tail_loop(self):
        # CSV header ör: "Application,ProcessID,SwapChainAddress,Runtime,...,msBetweenPresents,..."
        last_size = 0
        while self._running:
            try:
                if self._output_csv and os.path.exists(self._output_csv):
                    size = os.path.getsize(self._output_csv)
                    if size > last_size:
                        with open(self._output_csv, "r", encoding="utf-8", newline="") as f:
                            f.seek(last_size)
                            reader = csv.reader(f)
                            for row in reader:
                                if not row or "msBetweenPresents" in row[0]:
                                    # header satırı
                                    continue
                                try:
                                    # kolonları bul
                                    # basit yaklaşım: msBetweenPresents'ı sondan ara
                                    ms = None
                                    for col in row[::-1]:
                                        if col.replace(".", "", 1).isdigit():
                                            # aday
                                            ms = float(col)
                                            break
                                    if ms is not None and ms > 0:
                                        self.sample.fps = 1000.0 / ms
                                except Exception:
                                    continue
                        last_size = size
            except Exception:
                pass
            time.sleep(0.5)