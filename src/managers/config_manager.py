import json
import os
from pathlib import Path


class ConfigManager:
    def __init__(self, path=None):
        self.path = Path(path or os.getenv("CONFIG_PATH", "/app/config/config.json"))
        self.data = {}
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except Exception as exc:
            self.data = {}
            raise RuntimeError(f"Failed to load config: {exc}") from exc

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get(self, key, default=None):
        keys = key.split(".")
        value = self.data
        for k in keys:
            if not isinstance(value, dict):
                return default
            value = value.get(k, default)
            if value is None:
                return default
        return value

    def set(self, key, value):
        keys = key.split(".")
        d = self.data
        for k in keys[:-1]:
            if k not in d:
                d[k] = {}
            d = d[k]
        d[keys[-1]] = value
