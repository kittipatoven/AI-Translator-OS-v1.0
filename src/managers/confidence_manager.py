import unicodedata


class ConfidenceManager:
    def __init__(self, threshold=0.7):
        self.threshold = threshold

    @staticmethod
    def _tokenize(text, lang=None):
        text = text.strip()
        if not text:
            return []
        if lang and ("_Thai" in lang or "_Hans" in lang or "_Hant" in lang or
                     "_Hang" in lang or "_Mymr" in lang or "zho" in lang or
                     "kor" in lang or "mya" in lang or "tha" in lang):
            return list(unicodedata.normalize("NFC", text))
        return text.lower().split()

    def score(self, source, translated, back_similarity, source_lang=None, target_lang=None):
        if not translated:
            return 0.0
        if not source:
            return 0.0
        source_tokens = self._tokenize(source, source_lang)
        target_tokens = self._tokenize(translated, target_lang)
        length_ratio = min(len(target_tokens), len(source_tokens)) / max(len(target_tokens), len(source_tokens))
        confidence = 0.5 * back_similarity + 0.5 * length_ratio
        return round(min(max(confidence, 0.0), 1.0), 3)

    def is_confident(self, confidence):
        return confidence >= self.threshold
