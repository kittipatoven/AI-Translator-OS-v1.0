#!/usr/bin/env python3
"""Offline translation test for TH -> EN/ZH/KO/MY and back.

This is intended to run on the Raspberry Pi or any machine that has the
NLLB, Whisper and Piper/eSpeak assets available. On Windows it will fall
back gracefully and report any missing runtimes.
"""

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from managers.translation_manager import TranslationManager
from managers.tts_manager import TTSManager
from managers.language_pack_manager import LanguagePackManager


def main():
    packs_dir = PROJECT_ROOT / "data" / "language_packs"
    packs = LanguagePackManager(str(packs_dir))

    forward = ["th-en", "th-zh", "th-ko", "th-my"]
    pairs = [k for k in forward if k in packs.list()]
    if not pairs:
        print("[test_translation] No target language packs found")
        return 1

    nllb_dir = PROJECT_ROOT / "models" / "nllb"
    piper_dir = PROJECT_ROOT / "models" / "piper"

    print("[test_translation] Loading NLLB model...")
    translation = TranslationManager(str(nllb_dir))
    if not translation.is_model_present():
        print("[test_translation] NLLB model not loaded")
        return 1

    tts = TTSManager(str(piper_dir))

    test_texts = {
        "tha_Thai": "สวัสดีครับ คุณชื่ออะไร",
        "eng_Latn": "Hello, what is your name?",
        "zho_Hans": "你好，你叫什么名字？",
        "kor_Hang": "안녕하세요, 이름이 뭐예요?",
        "mya_Mymr": "မင်္ဂလာပါ၊ သင့်နာမည်က ဘာလဲ?",
    }

    for key in pairs:
        pack = packs.get(key)
        source = pack["source"]
        target = pack["target"]
        text = test_texts.get(source, "Hello")

        print(f"\n[test_translation] {key}: {source} -> {target}")
        print(f"  input: {text}")
        t0 = time.time()
        try:
            translated = translation.translate(text, source, target)
            print(f"  output ({time.time()-t0:.2f}s): {translated}")
        except Exception as exc:
            print(f"  ERROR ({time.time()-t0:.2f}s): {exc}")
            continue

        # Voice availability check
        voice = pack.get("piper_voice")
        tts.set_language(target)
        tts.set_voice(voice)
        has_voice = tts.has_voice(voice) if voice else False
        print(f"  piper_voice={voice} has_voice={has_voice}")
        if not has_voice:
            espeak_lang = tts._espeak_lang()
            print(f"  espeak fallback language: {espeak_lang}")

    print("\n[test_translation] Done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
