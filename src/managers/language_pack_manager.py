import json
from pathlib import Path


class LanguagePackManager:
    def __init__(self, packs_dir="/app/data/language_packs"):
        self.packs_dir = Path(packs_dir)
        self.packs_dir.mkdir(parents=True, exist_ok=True)
        self._packs = self._load_packs()

    def _load_packs(self):
        packs = {}
        for f in self.packs_dir.glob("*.json"):
            try:
                packs[f.stem] = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
        if not packs:
            # Default built-in packs
            packs = {
                "en-th": {"name": "English -> Thai", "source": "eng_Latn", "target": "tha_Thai"},
                "th-en": {"name": "Thai -> English", "source": "tha_Thai", "target": "eng_Latn"},
            }
        return packs

    def list(self):
        return list(self._packs.keys())

    def get(self, key):
        return self._packs.get(key)

    def add(self, key, pack):
        path = self.packs_dir / f"{key}.json"
        path.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")
        self._packs[key] = pack
