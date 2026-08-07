import json
import time
from pathlib import Path


class HistoryManager:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, source, target, source_lang, target_lang, confidence):
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "source_lang": source_lang,
            "target_lang": target_lang,
            "source": source,
            "target": target,
            "confidence": confidence,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def last(self, n=1):
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines[-n:] if line.strip()]
