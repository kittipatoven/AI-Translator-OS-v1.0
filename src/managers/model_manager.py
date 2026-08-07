import hashlib
import json
from pathlib import Path


class ModelManager:
    def __init__(self, model_dir):
        self.model_dir = Path(model_dir)

    def _manifest(self):
        manifest = self.model_dir / "manifest.json"
        if not manifest.exists():
            return {}
        try:
            return json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def list_models(self):
        return [f.name for f in self.model_dir.iterdir() if f.is_file()]

    def exists(self, name):
        return (self.model_dir / name).exists()

    def checksum(self, name, algorithm="sha256"):
        path = self.model_dir / name
        if not path.exists():
            return None
        h = hashlib.new(algorithm)
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def verify(self, name):
        manifest = self._manifest()
        expected = manifest.get("sha256", {}).get(name)
        if not expected:
            return True  # no manifest means no verification
        return self.checksum(name) == expected
