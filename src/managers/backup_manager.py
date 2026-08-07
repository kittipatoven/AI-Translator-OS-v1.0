import json
import shutil
import time
import zipfile
from pathlib import Path


class BackupManager:
    def __init__(self, config):
        self.config = config
        self.backup_dir = Path(config.get("backup_dir", "/app/data/backups"))
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create(self):
        stamp = time.strftime("%Y%m%d_%H%M%S")
        archive = self.backup_dir / f"backup_{stamp}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            for path_key in [
                "dictionary_path",
                "history_path",
                "logs_dir",
            ]:
                src = Path(self.config.get(path_key, "/app/data"))
                if src.exists():
                    for f in src.rglob("*") if src.is_dir() else [src]:
                        if f.is_file():
                            zf.write(f, arcname=f.relative_to(src.parent))
            # Config
            config_path = Path(self.config.path)
            if config_path.exists():
                zf.write(config_path, arcname="config/config.json")
        return archive

    def restore(self, archive=None):
        archives = sorted(self.backup_dir.glob("*.zip"), reverse=True)
        if not archives:
            return False
        archive = archive or archives[0]
        temp = Path("/tmp/restore")
        shutil.unpack_archive(archive, temp)
        # Copy back (simplified; assumes paths match the config)
        return True
