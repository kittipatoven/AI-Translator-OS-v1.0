#!/usr/bin/env python3
"""End-to-end AI pipeline test for AI Translator OS.

Runs inside the Docker container and exercises the full chain:

    Microphone -> Whisper -> Text -> NLLB -> Translated -> Piper -> WAV -> Speaker

If no real speech is captured, the script falls back to a fixed test sentence
so that the rest of the pipeline (translation, TTS, playback) can still be
validated.  On 1 GB Raspberry Pi 3 the NLLB inference is skipped to avoid OOM.
"""

import json
import os
import signal
import sys
import time
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


def _status(label, ok, detail=""):
    tag = "OK" if ok is True else ("WARN" if ok is None else "FAIL")
    print(f"{label:18s} [{tag:5s}] {detail}")


def _run_with_timeout(func, args, timeout=120):
    def _timeout_handler(signum, frame):
        raise TimeoutError("inference timeout")

    old = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout)
    try:
        return func(*args)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def _silence_wav(path: Path, seconds: int = 1):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00" * (16000 * 2 * seconds))
    return path


def main():
    config = load_config()
    ram = _total_ram_mb()
    results = {}
    source_text = ""
    translated = ""
    tts_path = None

    print("=" * 40)
    print(" AI PIPELINE TEST")
    print("=" * 40)
    print(f"RAM: {ram} MB")
    print()

    # 1. Microphone
    wav_in = PROJECT_ROOT / "data" / "pipeline_input.wav"
    try:
        from managers.audio_manager import AudioManager

        audio = AudioManager(config)
        if audio.is_microphone_present():
            print("Please say 'Hello' within 3 seconds...")
            recorded = _run_with_timeout(audio.record, (3, wav_in), 10)
            _status("Microphone", True, f"{recorded.name}")
            results["microphone"] = True
        else:
            _status("Microphone", False, "not detected")
            _silence_wav(wav_in, 1)
            results["microphone"] = False
    except Exception as exc:
        _status("Microphone", False, str(exc)[:30])
        _silence_wav(wav_in, 1)
        results["microphone"] = False

    # 2. Whisper
    whisper_dir = config.get("models", {}).get("whisper_dir", "/app/models/whisper")
    try:
        from managers.speech_manager import SpeechManager

        sm = SpeechManager(whisper_dir)
        if not sm.is_model_present():
            raise RuntimeError("Whisper model not found")
        source_text = _run_with_timeout(sm.transcribe, (str(wav_in), "en"), 120).strip()
        if source_text:
            _status("Whisper", True, repr(source_text[:40]))
            results["whisper"] = True
        else:
            _status("Whisper", None, "empty (will use fallback)")
            source_text = "Hello"
            results["whisper"] = None
    except Exception as exc:
        _status("Whisper", False, str(exc)[:30])
        source_text = "Hello"
        results["whisper"] = False

    # 3. NLLB
    nllb_dir = config.get("models", {}).get("nllb_dir", "/app/models/nllb")
    tts_language = "tha_Thai"
    if ram < 1536:
        _status("Translation (NLLB)", None, f"{ram} MB RAM (skipped)")
        translated = "Hello"  # use English fallback for TTS
        tts_language = "eng_Latn"
        results["nllb"] = None
    else:
        try:
            from managers.translation_manager import TranslationManager

            tm = _run_with_timeout(TranslationManager, (nllb_dir,), 120)
            if not tm.is_model_present():
                raise RuntimeError("NLLB model not found")
            translated = _run_with_timeout(
                tm.translate, (source_text, "eng_Latn", "tha_Thai"), 120
            )
            _status("Translation (NLLB)", bool(translated), repr(translated[:40]))
            results["nllb"] = bool(translated)
            if not translated:
                translated = "Hello"
                tts_language = "eng_Latn"
        except Exception as exc:
            _status("Translation (NLLB)", False, str(exc)[:30])
            translated = "Hello"
            tts_language = "eng_Latn"
            results["nllb"] = False

    # 4. Piper TTS
    piper_dir = config.get("models", {}).get("piper_dir", "/app/models/piper")
    tts_out = PROJECT_ROOT / "data" / "pipeline_tts.wav"
    try:
        from managers.tts_manager import TTSManager

        tts = TTSManager(piper_dir)
        tts.set_language(tts_language)
        tts_path = _run_with_timeout(tts.speak, (translated, tts_out), 120)
        if tts_path and Path(tts_path).exists():
            _status("Piper TTS", True, f"{tts_path}")
            results["piper"] = True
        else:
            raise RuntimeError("TTS did not create output")
    except Exception as exc:
        _status("Piper TTS", False, str(exc)[:30])
        results["piper"] = False

    # 5. Audio output
    try:
        from managers.audio_manager import AudioManager

        audio = AudioManager(config)
        if tts_path and Path(tts_path).exists():
            _run_with_timeout(audio.play, (Path(tts_path),), 60)
            _status("Audio Output", True, "playback OK")
            results["audio_output"] = True
        else:
            _status("Audio Output", None, "no TTS file to play")
            results["audio_output"] = None
    except Exception as exc:
        _status("Audio Output", False, str(exc)[:30])
        results["audio_output"] = False

    # Summary
    print()
    print("=" * 40)
    fail = sum(1 for v in results.values() if v is False)
    warn = sum(1 for v in results.values() if v is None)
    ok = sum(1 for v in results.values() if v is True)
    if fail == 0:
        print(" AI PIPELINE      [PASS]")
    else:
        print(" AI PIPELINE      [FAIL]")
    print(f" OK: {ok}  WARN: {warn}  FAIL: {fail}")
    print("=" * 40)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
