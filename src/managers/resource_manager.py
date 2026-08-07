import os
import shutil
import time
from pathlib import Path

from utils import system_helper


class ResourceManager:
    def __init__(self, config):
        self.storage_threshold = config.get("storage_threshold_percent", 85)
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
            "disk_percent": percent,
        }

    def cleanup_if_needed(self):
        usage = system_helper.disk_usage("/")
        if not usage:
            return
        percent = usage.used / usage.total * 100
        if percent >= self.storage_threshold:
            self._rotate_logs()
            self._clean_cache()

    def _rotate_logs(self):
        # Keep only last 7 log files
        for log_file in sorted(self.logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[7:]:
            log_file.unlink()

    def _clean_cache(self):
        for d in self.cache_dirs:
            if not d.exists():
                continue
            for f in sorted(d.iterdir(), key=lambda p: p.stat().st_mtime)[:-5]:
                try:
                    f.unlink()
                except Exception:
                    pass
