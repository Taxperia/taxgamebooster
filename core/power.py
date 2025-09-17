import threading
import time
import subprocess
import shutil

# GUIDs for typical Windows power plans (may vary):
GUID_HIGH_PERFORMANCE = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
GUID_BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"

def set_power_plan(guid: str):
    subprocess.run(["powercfg", "/S", guid], capture_output=True, text=True)

def get_active_power_plan_guid() -> str | None:
    out = subprocess.run(["powercfg", "/GETACTIVESCHEME"], capture_output=True, text=True)
    if out.returncode == 0 and out.stdout:
        # parse GUID like: "Power Scheme GUID: 381b...  (Balanced)"
        for token in out.stdout.split():
            if token.count("-") == 4 and len(token) >= 36:
                return token.strip()
    return None

class AutoPowerPlanManager:
    def __init__(self, system_monitor, cpu_th=40, gpu_th=30, poll_interval=3.0):
        self.system_monitor = system_monitor
        self.cpu_th = cpu_th
        self.gpu_th = gpu_th
        self.poll_interval = poll_interval
        self._running = False
        self._thread = None
        self._last_state_high = False

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self):
        while self._running:
            s = self.system_monitor.get()
            cpu = s.cpu_percent or 0
            gpu = s.gpu_util or 0
            try:
                if cpu >= self.cpu_th or gpu >= self.gpu_th:
                    if not self._last_state_high:
                        set_power_plan(GUID_HIGH_PERFORMANCE)
                        self._last_state_high = True
                else:
                    if self._last_state_high:
                        set_power_plan(GUID_BALANCED)
                        self._last_state_high = False
            except Exception as e:
                print("AutoPowerPlan error:", e)
            time.sleep(self.poll_interval)