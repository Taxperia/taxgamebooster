import time
import threading
import psutil
import shutil
import subprocess

# NVML (NVIDIA)
try:
    import pynvml
    pynvml.nvmlInit()
    NVML_AVAILABLE = True
except Exception:
    NVML_AVAILABLE = False

GiB = 1024 ** 3

class SystemSnapshot:
    def __init__(self):
        self.cpu_percent = 0.0
        self.cpu_freq = 0.0
        self.cpu_temp = None
        self.cpu_power_w = None

        self.ram_used = 0
        self.ram_total = 0
        self.ram_percent = 0.0

        self.gpu_util = None
        self.gpu_mem_used = None
        self.gpu_mem_total = None
        self.gpu_temp = None
        self.gpu_power_w = None

        self.net_up = 0
        self.net_down = 0

class SystemMonitor:
    def __init__(self, interval=1.0):
        self.interval = interval
        self.snapshot = SystemSnapshot()
        self._running = False
        self._thread = None
        self._last_net = psutil.net_io_counters()
        self._have_nvidia_smi = shutil.which("nvidia-smi") is not None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self):
        while self._running:
            try:
                self._collect()
            except Exception as e:
                print("SystemMonitor error:", e)
            time.sleep(self.interval)

    def _collect(self):
        s = self.snapshot
        # CPU
        s.cpu_percent = psutil.cpu_percent(interval=None)
        try:
            cf = psutil.cpu_freq()
            s.cpu_freq = cf.current if cf else 0.0
        except Exception:
            s.cpu_freq = 0.0

        # RAM (Windows'ta used ~ total - available)
        vm = psutil.virtual_memory()
        s.ram_total = vm.total
        s.ram_used = vm.total - vm.available
        s.ram_percent = vm.percent

        # GPU
        if NVML_AVAILABLE:
            try:
                h = pynvml.nvmlDeviceGetHandleByIndex(0)
                util = pynvml.nvmlDeviceGetUtilizationRates(h)
                mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                s.gpu_util = util.gpu
                s.gpu_mem_used = mem.used
                s.gpu_mem_total = mem.total
                try:
                    s.gpu_temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
                except Exception:
                    s.gpu_temp = None
                try:
                    s.gpu_power_w = pynvml.nvmlDeviceGetPowerUsage(h) / 1000.0
                except Exception:
                    s.gpu_power_w = None
            except Exception:
                s.gpu_util = None
        elif self._have_nvidia_smi:
            try:
                out = subprocess.check_output([
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                    "--format=csv,noheader,nounits"
                ], text=True, stderr=subprocess.DEVNULL, timeout=1.5)
                line = out.strip().splitlines()[0]
                u, mu, mt, t, p = [x.strip() for x in line.split(",")]
                s.gpu_util = float(u)
                s.gpu_mem_used = float(mu) * 1024 * 1024
                s.gpu_mem_total = float(mt) * 1024 * 1024
                s.gpu_temp = float(t)
                s.gpu_power_w = float(p)
            except Exception:
                s.gpu_util = None
        else:
            s.gpu_util = None

        # Network throughput
        now_net = psutil.net_io_counters()
        dt = max(self.interval, 1e-6)
        s.net_up = (now_net.bytes_sent - self._last_net.bytes_sent) / dt
        s.net_down = (now_net.bytes_recv - self._last_net.bytes_recv) / dt
        self._last_net = now_net

    def get(self) -> SystemSnapshot:
        return self.snapshot