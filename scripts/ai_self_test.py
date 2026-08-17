#!/usr/bin/env python3
"""End-to-end AI pipeline self-test for AI Translator OS.

Runs inside the Docker container.  It exercises Whisper -> NLLB -> Piper
with a synthetic test WAV and a small English phrase, then reports OK/FAIL
for every stage.  On 1 GB Raspberry Pi 3 the NLLB inference is skipped
automatically to avoid OOM kills.
"""

import json
import os
import signal
import subprocess
import sys
import wave
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))


def load_config():
    path = PROJECT_ROOT / "config" / "config.json"
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _mem_kb(key):
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith(key):
                return int(line.split()[1])
    return 0


def _total_ram_mb():
    return _mem_kb("MemTotal") // 1024


def _silence_wav(path: Path, seconds: int = 2):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00" * (16000 * 2 * seconds))
    return path


def _run_with_timeout(func, args, timeout=120):
    """Run *func* with a SIGALRM timeout to avoid hung models."""
    def _timeout_handler(signum, frame):
        raise TimeoutError("inference timeout")

    old = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout)
    try:
        return func(*args)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def main():
    config = load_config()
    results = []
    ram = _total_ram_mb()

    print("=" * 40)
    print(" AI PIPELINE SELF-TEST")
    print("=" * 40)
    print(f"RAM: {ram} MB")
    print()

    # Stage 1: Whisper
    whisper_dir = config.get("models", {}).get("whisper_dir", "/app/models/whisper")
    try:
        from managers.speech_manager import SpeechManager

        sm = SpeechManager(whisper_dir)
        if not sm.is_model_present():
            raise RuntimeError("Whisper model not found")
        wav = _silence_wav(PROJECT_ROOT / "data" / "ai_self_test.wav", 2)
        text = _run_with_timeout(sm.transcribe, (str(wav), "en"), 120)
        print(f"[OK] Whisper: {text!r}")
        results.append(True)
    except Exception as exc:
        print(f"[FAIL] Whisper: {exc}")
        results.append(False)

    # Stage 2: NLLB (skip on low RAM to prevent OOM)
    nllb_dir = config.get("models", {}).get("nllb_dir", "/app/models/nllb")
    if ram < 1536:
        print(f"[SKIP] NLLB: {ram} MB RAM (need >=1536)")
    else:
        try:
            from managers.translation_manager import TranslationManager

            tm = _run_with_timeout(TranslationManager, (nllb_dir,), 120)
            if not tm.is_model_present():
                raise RuntimeError("NLLB model not found")
            translated = _run_with_timeout(tm.translate, ("Hello", "eng_Latn", "tha_Thai"), 120)
            print(f"[OK] NLLB: {translated!r}")
            results.append(True)
        except Exception as exc:
            print(f"[FAIL] NLLB: {exc}")
            results.append(False)

    # Stage 3: Piper / TTS
    piper_dir = config.get("models", {}).get("piper_dir", "/app/models/piper")
    try:
        from managers.tts_manager import TTSManager

        tts = TTSManager(piper_dir)
        out = PROJECT_ROOT / "data" / "ai_self_test_tts.wav"
        path = _run_with_timeout(tts.speak, ("Hello", out), 120)
        ok = Path(path).exists() if path else False
        if ok:
            print(f"[OK] TTS: {path}")
            results.append(True)
        else:
            raise RuntimeError("TTS did not create output")
    except Exception as exc:
        print(f"[FAIL] TTS: {exc}")
        results.append(False)

    # Stage 4: Audio playback of TTS result (if available)
    try:
        from managers.audio_manager import AudioManager

        audio = AudioManager(config)
        if Path(PROJECT_ROOT / "data" / "ai_self_test_tts.wav").exists():
            audio.play(PROJECT_ROOT / "data" / "ai_self_test_tts.wav")
            print("[OK] Speaker playback")
            results.append(True)
    except Exception as exc:
        print(f"[WARN] Speaker playback: {exc}")
        # Playback is not critical for the AI pipeline itself.

    print()
    print("=" * 40)
    if all(results):
        print(" AI PIPELINE SELF-TEST PASSED")
    else:
        print(" AI PIPELINE SELF-TEST FAILED")
    print("=" * 40)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
