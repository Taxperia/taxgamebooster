import psutil
import time
from dataclasses import dataclass
from typing import Optional

HIGH = psutil.HIGH_PRIORITY_CLASS if hasattr(psutil, "HIGH_PRIORITY_CLASS") else None
ABOVE = psutil.ABOVE_NORMAL_PRIORITY_CLASS if hasattr(psutil, "ABOVE_NORMAL_PRIORITY_CLASS") else None
NORMAL = psutil.NORMAL_PRIORITY_CLASS if hasattr(psutil, "NORMAL_PRIORITY_CLASS") else None

@dataclass
class PerfSession:
    target_pid: Optional[int] = None
    suspended_pids: set[int] = None

    def __post_init__(self):
        if self.suspended_pids is None:
            self.suspended_pids = set()

class PerformanceMode:
    """
    Hedef oyun sürecinin önceliğini yükseltir; beyaz liste dışı ve boşta süreçleri askıya alır, çıkışta geri yükler.
    """
    def __init__(self, whitelist: list[str], suspend_cpu_threshold: float = 1.0):
        self.whitelist = set(x.lower() for x in whitelist)
        self.suspend_cpu_threshold = suspend_cpu_threshold
        self.session = PerfSession()

    def start_for_process(self, pid: int):
        self.session = PerfSession(target_pid=pid, suspended_pids=set())
        # hedef önceliği
        try:
            p = psutil.Process(pid)
            if HIGH:
                p.nice(HIGH)
            elif ABOVE:
                p.nice(ABOVE)
        except Exception:
            pass

    def maintain(self):
        """
        Periyodik çağır: askıya alınacak süreçleri seç.
        """
        if not self.session.target_pid:
            return
        try:
            target = psutil.Process(self.session.target_pid)
            target_name = target.name().lower()
        except Exception:
            return
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "status"]):
            try:
                if p.info["pid"] in (0, 4, self.session.target_pid):
                    continue
                name = (p.info["name"] or "").lower()
                if name in self.whitelist:
                    continue
                if "system" in name or "svchost.exe" in name:
                    continue
                # düşük cpu ve arka plan
                cpu = p.cpu_percent(interval=0.0)
                if cpu <= self.suspend_cpu_threshold and p.status() == psutil.STATUS_RUNNING:
                    # askıya al
                    p.suspend()
                    self.session.suspended_pids.add(p.pid)
            except Exception:
                continue

    def stop(self):
        # askıya alınanları geri devam ettir
        for pid in list(self.session.suspended_pids):
            try:
                p = psutil.Process(pid)
                p.resume()
            except Exception:
                pass
        self.session.suspended_pids.clear()