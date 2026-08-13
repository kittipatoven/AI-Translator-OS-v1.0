#!/usr/bin/env python3
"""Web UI/API smoke test for AI Translator OS.

Runs the Flask app with a mock ConversationManager and verifies that the
dashboard, language list, status, translation, and TTS endpoints respond.
"""

import io
import sys
import wave
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from web_server import WebServer


class MockTTS:
    def __init__(self):
        self._voice = "en_US-lessac-low"

    def speak(self, text, voice=None, output_path=None):
        path = PROJECT_ROOT / "data" / "test_tts.wav"
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00" * 32000)
        return path


class MockConv:
    def __init__(self):
        self.packs_keys = ["th-en", "th-zh", "th-ko", "th-my"]
        self.source_lang = "tha_Thai"
        self.target_lang = "eng_Latn"
        self.source_name = "TH -> EN"
        self.tts = MockTTS()
        self.speech = type("obj", (object,), {"transcribe": lambda *a, **k: "hello"})()
        self.last_result = None

    def get_status(self):
        return {
            "status": "Ready",
            "language": self.source_name,
            "language_key": self.packs_keys[0],
            "last_result": self.last_result,
        }

    def set_language_by_key(self, key):
        if key in self.packs_keys:
            self.source_name = key.upper()

    def next_language(self):
        pass

    def previous_language(self):
        pass

    def start_listening(self, duration=None):
        pass

    def replay(self):
        pass

    def translate_text(self, text):
        return {
            "source_text": text,
            "translated": "mock translation",
            "confidence": 0.85,
            "confident": True,
            "tts_path": None,
        }

    def _whisper_lang(self, lang):
        return lang.split("_")[0].lower()[:2]


def make_wav_bytes():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00" * 32000)
    return buf.getvalue()


def main():
    conv = MockConv()
    ws = WebServer(conv, host="127.0.0.1", port=8080)
    client = ws.app.test_client()

    tests = [
        ("/", 200, "Dashboard"),
        ("/api/status", 200, "Status"),
        ("/api/languages", 200, "Languages"),
    ]
    for path, status, name in tests:
        r = client.get(path)
        ok = r.status_code == status
        print(f"[test_web] {name}: {'OK' if ok else 'FAIL'} ({r.status_code})")
        if not ok:
            return 1

    r = client.post(
        "/api/translate",
        data={"text": "hello"},
        content_type="multipart/form-data",
    )
    print(f"[test_web] Translate text: {'OK' if r.status_code == 200 else 'FAIL'} ({r.status_code})")

    r = client.post(
        "/api/translate",
        data={"audio": (io.BytesIO(make_wav_bytes()), "test.wav")},
        content_type="multipart/form-data",
    )
    print(f"[test_web] Translate audio: {'OK' if r.status_code == 200 else 'FAIL'} ({r.status_code})")

    r = client.post("/api/tts", json={"text": "hello"})
    print(f"[test_web] TTS: {'OK' if r.status_code == 200 else 'FAIL'} ({r.status_code})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
