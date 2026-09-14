import os
import sys
import time
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("EngageMindDaemon")

from config.settings import settings
from main import run_discovery_cycle

CHECK_INTERVAL_SECONDS = int(os.getenv("ENGAGEMIND_SCAN_INTERVAL_SECONDS", "3600"))  # 1 hour

def run_daemon_loop():
    """24/7 Background daemon loop for EngageMind AI."""
    logger.info(f"🚀 EngageMind AI 24/7 Daemon Started (Scanning interval: {CHECK_INTERVAL_SECONDS // 60}m)...")
    logger.info(f"🛡️ Safety Settings: Max {settings.max_comments_per_day} comments/day | Active hours: {settings.active_hours_start}:00 - {settings.active_hours_end}:00 ({settings.timezone}).")

    while True:
        try:
            tz = ZoneInfo(settings.timezone)
            now = datetime.now(tz)

            if settings.active_hours_start <= now.hour < settings.active_hours_end:
                logger.info(f"⏰ Active business window reached ({now.strftime('%H:%M')}). Running discovery cycle...")
                run_discovery_cycle(limit=2, force=False)
            else:
                logger.debug(f"Sleeping outside active hours ({now.strftime('%H:%M')}).")

        except Exception as ex:
            logger.error(f"Error in EngageMind daemon loop: {ex}")

        time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    run_daemon_loop()
