import threading
import time
from pathlib import Path


class ConversationManager:
    def __init__(self, config, lcd, audio, speech, translation, tts,
                 language_packs, dictionary, rule, back, confidence, history, resource):
        self.config = config
        self.lcd = lcd
        self.audio = audio
        self.speech = speech
        self.translation = translation
        self.tts = tts
        self.packs = language_packs
        self.dictionary = dictionary
        self.rule = rule
        self.back = back
        self.confidence = confidence
        self.history = history
        self.resource = resource
        self.packs_keys = self.packs.list()
        self.current_pack_index = 0
        self._set_language_pair()
        self.listening = False
        self.record_timeout = config.get("audio.record_timeout", 10)

    def _set_language_pair(self):
        key = self.packs_keys[self.current_pack_index] if self.packs_keys else None
        pack = self.packs.get(key) if key else {}
        self.source_lang = pack.get("source", self.config.get("languages.source"))
        self.target_lang = pack.get("target", self.config.get("languages.target"))
        self.source_name = pack.get("name", f"{self.source_lang}")
        self.tts.set_voice(pack.get("piper_voice"))
        self.tts.set_language(self.target_lang)

    def idle(self):
        self.resource.cleanup_if_needed()

    def start_listening(self):
        if self.listening:
            return
        self.listening = True
        threading.Thread(target=self._listen, daemon=True).start()

    def _listen(self):
        try:
            self.lcd.display("Listening...", "")
            wav_path = self.audio.record(duration=self.record_timeout)
            self.lcd.display("Thinking...", "")
            source_text = self.speech.transcribe(
                wav_path, language=self._whisper_lang(self.source_lang)
            )
            prepared = self.dictionary.apply(source_text, self.target_lang)
            masked = self.rule.mask(prepared)
            translated = self.translation.translate(masked, self.source_lang, self.target_lang)
            translated = self.rule.unmask(translated)
            similarity, _ = self.back.verify(source_text, translated, self.source_lang, self.target_lang)
            score = self.confidence.score(source_text, translated, similarity, self.source_lang, self.target_lang)
            if not self.confidence.is_confident(score):
                self.lcd.display("Low Confidence", "Please speak again")
                self.history.add(source_text, translated, self.source_lang, self.target_lang, score)
                return
            self.lcd.display("Speaking...", translated[:16])
            try:
                tts_path = self.tts.speak(translated)
                self.audio.play(tts_path)
            except RuntimeError:
                self.lcd.display("No TTS voice", translated[:16])
            self.history.add(source_text, translated, self.source_lang, self.target_lang, score)
            self.lcd.display("Ready", self.source_name)
        except Exception as exc:
            self.lcd.display("Error", str(exc)[:16])
        finally:
            self.listening = False

    def replay(self):
        path = self.tts.replay()
        if path:
            self.audio.play(path)

    def next_language(self):
        if not self.packs_keys:
            return
        self.current_pack_index = (self.current_pack_index + 1) % len(self.packs_keys)
        self._set_language_pair()
        self.lcd.display("Language", self.source_name[:16])

    def previous_language(self):
        if not self.packs_keys:
            return
        self.current_pack_index = (self.current_pack_index - 1) % len(self.packs_keys)
        self._set_language_pair()
        self.lcd.display("Language", self.source_name[:16])

    def toggle_menu(self):
        self.lcd.display("Menu", "Not implemented")

    def _whisper_lang(self, lang_code):
        pack = self.packs.get(self.packs_keys[self.current_pack_index]) if self.packs_keys else {}
        if pack:
            return pack.get("whisper_source") or lang_code.split("_")[0].lower()[:2]
        return lang_code.split("_")[0].lower()[:2]
