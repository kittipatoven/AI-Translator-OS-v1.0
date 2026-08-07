from difflib import SequenceMatcher


class BackTranslationManager:
    def __init__(self, translator=None):
        self.translator = translator

    def verify(self, source, translated, source_lang, target_lang):
        if self.translator is None:
            return 0.0, "no back-translator"
        back = self.translator.translate(translated, target_lang, source_lang)
        ratio = SequenceMatcher(None, source.lower(), back.lower()).ratio()
        return ratio, back

    def is_acceptable(self, similarity, threshold=0.7):
        return similarity >= threshold
