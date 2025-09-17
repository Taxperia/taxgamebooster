import os
import json
from dataclasses import dataclass, asdict, field

CONFIG_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "PulseBoost")
CONFIG_PATH = os.path.join(CONFIG_DIR, "settings.json")

@dataclass
class UISettings:
    theme: str = "tokyonight"
    language: str = "tr"
    show_overlay: bool = True
    use_rtss: bool = False
    tray_icon: str = "tray1"  # assets/icons/tray/{tray_icon}.svg

@dataclass
class PowerSettings:
    auto_switch: bool = True
    cpu_util_threshold: int = 40
    gpu_util_threshold: int = 30

@dataclass
class PathsSettings:
    video_dir: str = os.path.join(os.path.expanduser("~"), "Videos", "PulseBoost")
    screenshot_dir: str = os.path.join(os.path.expanduser("~"), "Pictures", "PulseBoost")

@dataclass
class HotkeySettings:
    enable_global: bool = True
    start_stop_record: str = "Ctrl+Alt+R"
    screenshot: str = "Ctrl+Alt+S"
    save_replay: str = "Ctrl+Alt+P"

@dataclass
class RecordingSettings:
    encoder: str = "h264_nvenc"   # h264_nvenc, hevc_nvenc, h264_qsv, libx264
    fps: int = 60
    resolution: str = "desktop"   # "desktop" or "1920x1080"
    container: str = "mp4"        # mp4, mkv, mov
    quality_preset: str = "medium" # low, medium, high, custom
    bitrate_mbps: float = 12.0     # custom/override
    instant_replay: bool = True
    replay_minutes: int = 2        # 1..10
    segment_seconds: int = 20

@dataclass
class StartupSettings:
    run_on_boot: bool = False
    start_minimized: bool = False

@dataclass
class ToolsSettings:
    presentmon_path: str = ""
    rtss_hint_path: str = ""

@dataclass
class PerformanceSettings:
    enable_performance_mode: bool = False
    target_process_name: str = ""
    whitelist_processes: list[str] = field(default_factory=lambda: [
        "explorer.exe", "dwm.exe", "svchost.exe", "cmd.exe", "conhost.exe",
        "PulseBoost.exe", "PulseBoost", "python.exe", "powershell.exe", "SearchApp.exe"
    ])
    suspend_cpu_threshold: float = 1.0

@dataclass
class OverlaySettings:
    skin: str = "afterburner-like"
    position: str = "top-left"   # top-left, top-right, bottom-left, bottom-right
    grid_columns: int = 2
    font_size: int = 14
    bg_opacity: float = 0.35
    border_radius: int = 10
    margin: int = 16
    colors: dict = field(default_factory=lambda: {
        "cpu": "#76ff03",
        "ram": "#00e5ff",
        "gpu": "#ffb74d",
        "net": "#90caf9",
        "temp": "#ff5252",
        "fps": "#e0e0e0",
    })

@dataclass
class SpeedtestSettings:
    preferred_server_id: int | None = None
    gauge_theme: str = "car"

@dataclass
class BenchmarkSettings:
    cpu_seconds: int = 20
    gpu_seconds: int = 45
    leaderboard_path: str = os.path.join(CONFIG_DIR, "benchmarks.json")

@dataclass
class Settings:
    ui: UISettings = field(default_factory=UISettings)
    power: PowerSettings = field(default_factory=PowerSettings)
    paths: PathsSettings = field(default_factory=PathsSettings)
    recording: RecordingSettings = field(default_factory=RecordingSettings)
    startup: StartupSettings = field(default_factory=StartupSettings)
    tools: ToolsSettings = field(default_factory=ToolsSettings)
    performance: PerformanceSettings = field(default_factory=PerformanceSettings)
    overlay: OverlaySettings = field(default_factory=OverlaySettings)
    speedtest: SpeedtestSettings = field(default_factory=SpeedtestSettings)
    benchmark: BenchmarkSettings = field(default_factory=BenchmarkSettings)
    hotkeys: HotkeySettings = field(default_factory=HotkeySettings)

    @staticmethod
    def load() -> "Settings":
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                s = Settings()
                for key in ("ui","power","paths","recording","startup","tools","performance","overlay","speedtest","benchmark","hotkeys"):
                    if key in data:
                        getattr(s, key).__dict__.update(data[key])
                # overlay colors merge
                if "overlay" in data and "colors" in data["overlay"]:
                    s.overlay.colors.update(data["overlay"]["colors"])
                # leaderboard fallback
                if not s.benchmark.leaderboard_path:
                    s.benchmark.leaderboard_path = os.path.join(CONFIG_DIR, "benchmarks.json")
                return s
        except Exception as e:
            print("Failed to load settings:", e)
        return Settings()

    def save(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "ui": asdict(self.ui),
                "power": asdict(self.power),
                "paths": asdict(self.paths),
                "recording": asdict(self.recording),
                "startup": asdict(self.startup),
                "tools": asdict(self.tools),
                "performance": asdict(self.performance),
                "overlay": asdict(self.overlay),
                "speedtest": asdict(self.speedtest),
                "benchmark": asdict(self.benchmark),
                "hotkeys": asdict(self.hotkeys),
            }, f, ensure_ascii=False, indent=2)