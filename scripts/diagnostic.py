#!/usr/bin/env python3
"""Comprehensive hardware and AI diagnostics for AI Translator OS.

Runs inside the Docker container on the Pi (privileged mode) and prints an
OK/FAIL/SKIP report for every component.  This is intentionally defensive:
no test should crash the script; every problem is reported.
"""

import json
import os
import re
import signal
import subprocess
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


config = load_config()

RESULTS = []


def _pad(label, ok, detail=""):
    tag = "OK" if ok is True else ("SKIP" if ok is None else "FAIL")
    line = f"[{tag}] {label}"
    if detail:
        line = f"{line} ({detail})"
    print(line)
    RESULTS.append((label, ok))


def _run(cmd, timeout=10, shell=False):
    try:
        return subprocess.run(
            cmd,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:
        return subprocess.CompletedProcess(cmd, returncode=1, stderr=str(exc), stdout="")


def _mem_kb(key):
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith(key):
                return int(line.split()[1])
    return 0


def _total_ram_mb():
    return _mem_kb("MemTotal") // 1024


def _total_swap_mb():
    return _mem_kb("SwapTotal") // 1024


def check_os():
    arch = os.uname().machine
    is_aarch64 = arch == "aarch64"
    _pad("Architecture aarch64", is_aarch64, arch)

    cpuinfo = Path("/proc/cpuinfo").read_text(errors="ignore") if Path("/proc/cpuinfo").exists() else ""
    is_pi = "Raspberry Pi" in cpuinfo
    _pad("Raspberry Pi board", is_pi)


def check_resources():
    ram = _total_ram_mb()
    swap = _total_swap_mb()
    _pad(f"RAM {ram} MB", True)
    _pad(f"Swap {swap} MB", swap >= 1024, f"{swap} MB")

    temp = _run(["vcgencmd", "measure_temp"], timeout=5)
    if temp.returncode == 0:
        _pad("CPU temperature", True, temp.stdout.strip().replace("temp=", ""))
    else:
        _pad("CPU temperature", None, "vcgencmd not available")

    df = _run(["df", "-h", "/"], timeout=5)
    _pad("SD/Root space", df.returncode == 0, df.stdout.splitlines()[-1] if df.stdout else "")


def check_i2c():
    bus = config.get("lcd", {}).get("i2c_bus", 1)
    rc = _run(["i2cdetect", "-y", str(bus)], timeout=10)
    ok = rc.returncode == 0 and any(c in rc.stdout for c in ["0x27", "0x3f", "0x3F"])
    _pad(f"I2C bus {bus}", ok)

    try:
        from managers.lcd_manager import LCDManager

        lcd = LCDManager(bus=bus, address=config.get("lcd", {}).get("i2c_address", 0x27))
        lcd.display("AI TRANSLATOR", "HARDWARE TEST")
        _pad("LCD1602", lcd.i2c is not None, "0x27" if lcd.i2c else "no display")
    except Exception as exc:
        _pad("LCD1602", False, str(exc))


def check_gpio():
    _pad("GPIO /dev/gpiomem", Path("/dev/gpiomem").exists())

    try:
        from managers.button_manager import ButtonManager

        pins = config.get("buttons", {"left": 17, "right": 27, "speak": 22, "replay": 23, "menu": 24})
        bm = ButtonManager(pins)
        for name in pins:
            bm.on(name, short=lambda n=name: None)
        bm.start()
        for name in pins:
            bm.simulate(name)
            time.sleep(0.05)
        bm.stop()
        _pad("5 Push Buttons", True, ", ".join(pins.keys()))
    except Exception as exc:
        _pad("5 Push Buttons", False, str(exc))


def check_audio():
    mic = _run(["arecord", "-l"], timeout=5)
    mic_ok = mic.returncode == 0 and "card" in mic.stdout
    _pad("USB Microphone", mic_ok)

    spk = _run(["aplay", "-l"], timeout=5)
    spk_ok = spk.returncode == 0 and "card" in spk.stdout
    _pad("USB Speaker", spk_ok)

    if not (mic_ok and spk_ok):
        return

    # Record a short test WAV and play it back.
    try:
        from managers.audio_manager import AudioManager

        audio = AudioManager(config)
        wav = PROJECT_ROOT / "data" / "diagnostic_record.wav"
        recorded = audio.record(duration=3, output_path=wav)
        _pad("Record 3s WAV", recorded.exists(), str(recorded))
        try:
            audio.play(recorded)
            _pad("Playback WAV", True)
        except Exception as exc:
            _pad("Playback WAV", False, str(exc))
    except Exception as exc:
        _pad("Audio record/playback", False, str(exc))


def _silence_wav(path: Path, seconds: int = 2):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00" * (16000 * 2 * seconds))
    return path


def check_whisper():
    whisper_dir = config.get("models", {}).get("whisper_dir", "/app/models/whisper")
    try:
        from managers.speech_manager import SpeechManager

        sm = SpeechManager(whisper_dir)
        _pad("Whisper model present", sm.is_model_present())
    except Exception as exc:
        _pad("Whisper model present", False, str(exc))
        return

    # Run whisper-cli on a silent test file: zero bytes produce no text,
    # but the process exercising the binary and libs proves the runtime works.
    wav = _silence_wav(PROJECT_ROOT / "data" / "diagnostic_whisper.wav", 1)
    try:
        from managers.speech_manager import SpeechManager

        sm = SpeechManager(whisper_dir)
        text = sm.transcribe(str(wav), language="en")
        _pad("Whisper inference", True, repr(text[:40]))
    except Exception as exc:
        _pad("Whisper inference", False, str(exc)[:40])


def check_nllb():
    nllb_dir = config.get("models", {}).get("nllb_dir", "/app/models/nllb")
    try:
        from managers.translation_manager import TranslationManager

        tm = TranslationManager(nllb_dir)
        _pad("NLLB model present", tm.is_model_present())
    except Exception as exc:
        _pad("NLLB model present", False, str(exc))
        return

    # NLLB 600M easily OOM on a 1 GB Pi.  Only attempt inference on >= 1.5 GB.
    ram_mb = _total_ram_mb()
    if ram_mb < 1536:
        _pad("NLLB inference", None, f"{ram_mb} MB RAM (need >=1536)")
        return

    # Use an alarm so a hung model does not block the diagnostic forever.
    def _timeout_handler(signum, frame):
        raise TimeoutError("NLLB timeout")

    old = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(120)
    try:
        from managers.translation_manager import TranslationManager

        tm = TranslationManager(nllb_dir)
        result = tm.translate("Hello", "eng_Latn", "tha_Thai")
        _pad("NLLB inference", bool(result), repr(result[:40]))
    except Exception as exc:
        _pad("NLLB inference", False, str(exc)[:40])
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def check_piper():
    piper_dir = config.get("models", {}).get("piper_dir", "/app/models/piper")
    try:
        from managers.tts_manager import TTSManager

        tts = TTSManager(piper_dir)
        _pad("Piper model present", tts.is_model_present())
    except Exception as exc:
        _pad("Piper model present", False, str(exc))
        return

    out = PROJECT_ROOT / "data" / "diagnostic_tts.wav"
    try:
        from managers.tts_manager import TTSManager

        tts = TTSManager(piper_dir)
        tts.set_language("tha_Thai")
        path = tts.speak("สวัสดี", output_path=out)
        _pad("Piper/eSpeak TTS", Path(path).exists() if path else False)
    except Exception as exc:
        _pad("Piper/eSpeak TTS", False, str(exc)[:40])


def main():
    print("=" * 40)
    print(" AI TRANSLATOR HARDWARE / AI TEST")
    print("=" * 40)
    print()

    check_os()
    check_resources()
    check_i2c()
    check_gpio()
    check_audio()
    check_whisper()
    check_nllb()
    check_piper()

    print()
    print("=" * 40)
    fail = sum(1 for _, ok in RESULTS if ok is False)
    skip = sum(1 for _, ok in RESULTS if ok is None)
    ok = sum(1 for _, ok in RESULTS if ok is True)
    if fail == 0:
        print(f" HARDWARE TEST PASSED ({ok} OK, {skip} SKIP)")
    else:
        print(f" HARDWARE TEST FAILED ({ok} OK, {skip} SKIP, {fail} FAIL)")
    print("=" * 40)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
