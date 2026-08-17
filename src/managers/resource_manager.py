import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

from utils import system_helper

logger = logging.getLogger(__name__)


class ResourceManager:
    """Monitor and protect system resources on the Raspberry Pi.

    Tracks CPU, RAM, temperature and disk usage.  Provides disk cleanup and
    CPU throttling detection.  cleanup_if_needed() should be called regularly
    (e.g. from the main loop) to keep the system stable.
    """

    def __init__(self, config):
        self.storage_threshold = config.get("storage_threshold_percent", 85)
        self.critical_threshold = 95
        self.logs_dir = Path(config.get("logs_dir", "/app/logs"))
        self.cache_dirs = [
            Path(config.get("audio.record_dir", "/app/data/recordings")),
            Path(config.get("audio.play_dir", "/app/data/tts")),
        ]

    def snapshot(self):
        usage = system_helper.disk_usage("/")
        percent = (usage.used / usage.total * 100) if usage else 0
        return {
            "cpu": system_helper.cpu_percent(),
            "ram": system_helper.ram_usage(),
            "temperature": system_helper.temperature(),
            "throttled": self.is_throttled(),
            "disk_percent": percent,
        }

    def cleanup_if_needed(self):
        usage = system_helper.disk_usage("/")
        if not usage:
            return
        percent = usage.used / usage.total * 100
        if percent >= self.critical_threshold:
            logger.warning("Disk critical: %.1f%% used; running aggressive cleanup", percent)
            self._rotate_logs(keep=1)
            self._clean_cache(keep=2)
        elif percent >= self.storage_threshold:
            logger.warning("Disk high: %.1f%% used; running cleanup", percent)
            self._rotate_logs(keep=7)
            self._clean_cache(keep=5)

    def is_throttled(self):
        """Return True if the Raspberry Pi is currently under-voltage or thermally throttled."""
        if not shutil.which("vcgencmd"):
            return False
        try:
            rc = subprocess.run(
                ["vcgencmd", "get_throttled"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if rc.returncode != 0:
                return False
            # Output: throttled=0x40000 etc.
            value = rc.stdout.strip().split("=")[-1]
            flags = int(value, 16) if value.startswith("0x") else int(value, 0)
            # Bits 16..19 mean currently active
            now_throttled = (flags & 0x40000) or (flags & 0x20000) or (flags & 0x10000) or (flags & 0x80000)
            return bool(now_throttled)
        except Exception as exc:
            logger.warning("Failed to read throttled status: %s", exc)
            return False

    def is_disk_critical(self):
        usage = system_helper.disk_usage("/")
        if not usage:
            return False
        percent = usage.used / usage.total * 100
        return percent >= self.critical_threshold

    def _rotate_logs(self, keep=7):
        files = sorted(self.logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        for log_file in files[keep:]:
            try:
                log_file.unlink()
                logger.info("Rotated log: %s", log_file)
            except Exception:
                pass

    def _clean_cache(self, keep=5):
        for d in self.cache_dirs:
            if not d.exists():
                continue
            files = sorted(d.iterdir(), key=lambda p: p.stat().st_mtime)
            for f in files[:-keep] if keep > 0 else files:
                try:
                    f.unlink()
                    logger.info("Cleaned cache: %s", f)
                except Exception:
                    pass
