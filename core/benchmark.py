import time
import threading
import subprocess
import os
import numpy as np
from typing import Optional
try:
    import pynvml
    pynvml.nvmlInit()
    NVML_AVAILABLE = True
except Exception:
    NVML_AVAILABLE = False

def cpu_stress(seconds: int = 15, threads: int = 0) -> dict:
    """
    NumPy dot ile GIL dışı yoğun iş: GFLOPS tahmini.
    """
    if threads <= 0:
        threads = os.cpu_count() or 4
    stop = False
    gflops_acc = [0.0] * threads

    def worker(idx: int):
        nonlocal stop
        # küçük matris ile hızlı tekrar
        a = np.random.rand(512, 512).astype(np.float32)
        b = np.random.rand(512, 512).astype(np.float32)
        local_ops = 0
        t0 = time.time()
        while not stop:
            c = a @ b  # (512^3)*2 FLOPs ~ 2 * 134,217,728 ~ 268 MFLOPs
            local_ops += 2 * (512**3)
        dt = time.time() - t0
        gflops_acc[idx] = (local_ops / dt) / 1e9 if dt > 0 else 0.0

    ths = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(threads)]
    for t in ths: t.start()
    time.sleep(seconds)
    stop = True
    for t in ths: t.join(timeout=2)
    total_gflops = sum(gflops_acc)
    return {"seconds": seconds, "threads": threads, "gflops": round(total_gflops, 2)}

def gpu_nvenc_stress(seconds: int = 15, encoder: str = "h264_nvenc") -> dict:
    """
    ffmpeg testsrc ile NVENC encode yükü; GPU video engine kullanımı artar.
    """
    out_null = "NUL" if os.name == "nt" else "/dev/null"
    cmd = [
        "ffmpeg", "-v", "quiet",
        "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=60",
        "-t", str(seconds),
        "-c:v", encoder,
        "-preset", "p5",
        "-b:v", "20M",
        "-maxrate", "25M",
        "-bufsize", "40M",
        "-f", "null", out_null
    ]
    t0 = time.time()
    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        return {"seconds": seconds, "ok": False, "error": str(e)}
    dt = time.time() - t0
    res = {"seconds": seconds, "ok": True, "elapsed": round(dt, 2)}
    if NVML_AVAILABLE:
        try:
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            util = pynvml.nvmlDeviceGetUtilizationRates(h)
            res["gpu_util_after"] = util.gpu
            res["vid_util_after"] = getattr(util, "video", None) if hasattr(util, "video") else None
        except Exception:
            pass
    return res