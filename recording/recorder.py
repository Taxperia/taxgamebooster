import os
import subprocess
import threading
from datetime import datetime
from core.settings import Settings

try:
    import dxcam
except Exception:
    dxcam = None

def _container_ext(container: str) -> str:
    c = (container or "mp4").lower()
    return c if c in ("mp4","mkv","mov") else "mp4"

class ScreenRecorder:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._ffmpeg = None
        self._camera = None
        self._running = False
        self._thread = None

    def start(self, filename: str | None = None):
        if dxcam is None:
            raise RuntimeError("dxcam not installed")
        video_dir = self.settings.paths.video_dir
        os.makedirs(video_dir, exist_ok=True)
        ext = _container_ext(self.settings.recording.container)
        if not filename:
            filename = datetime.now().strftime(f"record_%Y%m%d_%H%M%S.{ext}")
        out_path = os.path.join(video_dir, filename)

        self._camera = dxcam.create(output_idx=0)
        if self.settings.recording.resolution != "desktop":
            try:
                w, h = self.settings.recording.resolution.split("x")
                w, h = int(w), int(h)
            except Exception:
                disp = self._camera.output_res()
                w, h = disp[0], disp[1]
        else:
            disp = self._camera.output_res()
            w, h = disp[0], disp[1]

        pix_fmt = "bgr0"
        bitrate = max(2.0, float(self.settings.recording.bitrate_mbps or 12.0))
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-f", "rawvideo",
            "-pix_fmt", pix_fmt,
            "-s", f"{w}x{h}",
            "-r", str(self.settings.recording.fps),
            "-i", "-",
            "-c:v", self.settings.recording.encoder,
            "-preset", "p6",
            "-b:v", f"{bitrate}M",
            "-maxrate", f"{bitrate*1.3:.1f}M",
            "-bufsize", f"{bitrate*2.0:.1f}M",
            out_path
        ]
        self._ffmpeg = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
        self._running = True

        def loop():
            for frame in self._camera.frames():
                if not self._running:
                    break
                try:
                    self._ffmpeg.stdin.write(frame.tobytes())
                except Exception:
                    break

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()
        return out_path

    def stop(self):
        self._running = False
        try:
            if self._camera:
                self._camera.stop()
        except Exception:
            pass
        try:
            if self._ffmpeg and self._ffmpeg.stdin:
                self._ffmpeg.stdin.close()
        except Exception:
            pass
        if self._thread:
            self._thread.join(timeout=2)
        try:
            if self._ffmpeg:
                self._ffmpeg.wait(timeout=3)
        except Exception:
            pass