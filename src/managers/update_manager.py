import json
import shutil
import subprocess
import time
from pathlib import Path


class UpdateManager:
    def __init__(self, config, backup_manager):
        self.config = config
        self.backup = backup_manager
        self.paths = config.get("update.paths", ["/media/usb", "/media/sdcard"])

    def check(self):
        for p in self.paths:
            update_dir = Path(p)
            if not update_dir.exists():
                continue
            manifest = update_dir / "update.json"
            if manifest.exists():
                return update_dir
        return None

    def apply(self, update_dir):
        if self.backup:
            self.backup.create()
        manifest = Path(update_dir) / "update.json"
        try:
            plan = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(f"Invalid update manifest: {exc}") from exc
        try:
            for item in plan.get("files", []):
                src = Path(update_dir) / item["source"]
                dst = Path(item["destination"])
                if src.is_dir():
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
            return True
        except Exception as exc:
            if self.backup:
                self.backup.restore()
            raise RuntimeError(f"Update failed and rolled back: {exc}") from exc
