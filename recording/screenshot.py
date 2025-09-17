import os
from datetime import datetime
from mss import mss
from core.settings import Settings

def take_screenshot(settings: Settings) -> str:
    outdir = settings.paths.screenshot_dir
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, datetime.now().strftime("screenshot_%Y%m%d_%H%M%S.png"))
    with mss() as sct:
        sct.shot(mon=-1, output=path)
    return path