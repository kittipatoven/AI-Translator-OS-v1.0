import unicodedata
from difflib import SequenceMatcher


class BackTranslationManager:
    def __init__(self, translator=None):
        self.translator = translator

    @staticmethod
    def _tokenize(text, lang=None):
        """Tokenize at the most stable unit for the language."""
        text = text.strip()
        if not text:
            return []
        # Use characters for non-Latin/CJK scripts; words for Latin-like scripts.
        if lang and ("Thai" in lang or "_Thai" in lang or "_Hani" in lang or
                     "_Hans" in lang or "_Hant" in lang or "_Hang" in lang or
                     "_Mymr" in lang or "zho" in lang or "kor" in lang or
                     "mya" in lang or "tha" in lang):
            return list(unicodedata.normalize("NFC", text))
        return text.lower().split()

    def verify(self, source, translated, source_lang, target_lang):
        if self.translator is None:
            return 0.0, "no back-translator"
        back = self.translator.translate(translated, target_lang, source_lang)
        source_tokens = self._tokenize(source, source_lang)
        back_tokens = self._tokenize(back, source_lang)
        ratio = SequenceMatcher(None, source_tokens, back_tokens).ratio()
        return ratio, back

    def is_acceptable(self, similarity, threshold=0.7):
        return similarity >= threshold
