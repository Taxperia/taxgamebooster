import os
import subprocess
import threading
import time
from datetime import datetime
from core.settings import Settings

def _container_ext(container: str) -> str:
    c = (container or "mp4").lower()
    return c if c in ("mp4","mkv","mov") else "mp4"

def estimate_replay_size_mb(minutes: int, bitrate_mbps: float) -> int:
    # MB ≈ bitrate(Mb/s) * 60 * minutes / 8
    return int((bitrate_mbps * 60.0 * minutes) / 8.0)

class InstantReplay:
    """
    ffmpeg ddagrab/gdigrab ile segment mp4/mkv üretir (ör: 20sn).
    Kaydet denince son X dakikayı concat eder (copy).
    """
    def __init__(self, settings: Settings):
        self.settings = settings
        self._ffmpeg = None
        self._thread = None
        self._running = False
        self._segments_dir = os.path.join(self.settings.paths.video_dir, "segments")
        os.makedirs(self._segments_dir, exist_ok=True)

    def start(self):
        os.makedirs(self._segments_dir, exist_ok=True)
        fps = self.settings.recording.fps
        encoder = self.settings.recording.encoder
        seg_sec = self.settings.recording.segment_seconds
        bitrate = max(2.0, float(self.settings.recording.bitrate_mbps or 12.0))
        ext = _container_ext(self.settings.recording.container)
        out_pattern = os.path.join(self._segments_dir, f"seg_%03d.{ext}")
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "ddagrab",
            "-framerate", str(fps),
            "-i", "desktop",
            "-c:v", encoder,
            "-preset", "p6",
            "-b:v", f"{bitrate}M",
            "-maxrate", f"{bitrate*1.3:.1f}M",
            "-bufsize", f"{bitrate*2.0:.1f}M",
            "-f", "segment",
            "-segment_time", str(seg_sec),
            "-reset_timestamps", "1",
            out_pattern
        ]
        # Windows 10 altı için: ffmpeg ddagrab yoksa gdigrab fallback
        try:
            self._ffmpeg = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            cmd[2:4] = ["-f", "gdigrab"]
            self._ffmpeg = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        self._running = True

        def clean_loop():
            while self._running:
                try:
                    segs = sorted([os.path.join(self._segments_dir, f) for f in os.listdir(self._segments_dir) if f.endswith(f".{ext}")])
                    keep_min = max(1, min(self.settings.recording.replay_minutes, 10))
                    keep = max(1, (keep_min*60) // self.settings.recording.segment_seconds + 3)
                    for f in segs[:-keep]:
                        try:
                            os.remove(f)
                        except Exception:
                            pass
                except Exception:
                    pass
                time.sleep(self.settings.recording.segment_seconds)
        self._thread = threading.Thread(target=clean_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._ffmpeg:
            try:
                self._ffmpeg.terminate()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=2)

    def save_replay(self) -> str | None:
        # Son X dakikanın segmentlerini concat yap
        ext = _container_ext(self.settings.recording.container)
        seg_sec = self.settings.recording.segment_seconds
        replay_sec = max(60, min(600, self.settings.recording.replay_minutes * 60))
        segs = sorted([os.path.join(self._segments_dir, f) for f in os.listdir(self._segments_dir) if f.endswith(f".{ext}")])
        if not segs:
            return None
        need_count = max(1, replay_sec // seg_sec + 1)
        chosen = segs[-need_count:]
        concat_list_path = os.path.join(self._segments_dir, "concat.txt")
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for c in chosen:
                f.write(f"file '{c.replace('\\', '/')}'\n")
        out_dir = self.settings.paths.video_dir
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, datetime.now().strftime(f"replay_%Y%m%d_%H%M%S.{ext}"))
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path, "-c", "copy", out_path]
        subprocess.run(cmd)
        return out_path