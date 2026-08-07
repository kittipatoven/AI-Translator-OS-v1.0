import json
from pathlib import Path


class DictionaryManager:
    def __init__(self, path):
        self.path = Path(path)
        self.dictionary = {}
        self.load()

    def load(self):
        if not self.path.exists():
            self.dictionary = {}
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.dictionary = json.load(f)
        except Exception:
            self.dictionary = {}

    def apply(self, text, target_lang=None):
        """Apply dictionary to source text.

        - If a term has `do_not_translate=True`, keep it as-is.
        - If a target language is provided and a translation is known,
          replace the term with the target-language translation.
        """
        if not text:
            return text
        for term, data in self.dictionary.items():
            if term not in text:
                continue
            if not isinstance(data, dict):
                continue
            if data.get("do_not_translate"):
                continue
            if target_lang:
                translation = data.get("translations", {}).get(target_lang)
                if translation:
                    text = text.replace(term, translation)
        return text
