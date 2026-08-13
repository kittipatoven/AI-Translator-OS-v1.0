#!/usr/bin/env python3
"""Audio test script for AI Translator OS.

Records a 5-second WAV, applies noise-reduction/VAD, then plays it back.
On Windows or systems without ALSA it uses sounddevice or falls back to a
dummy file so the test does not crash.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from managers.audio_manager import AudioManager


def load_config():
    config_path = PROJECT_ROOT / "config" / "config.json"
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def main():
    config = load_config()
    audio = AudioManager(config)

    print(f"[test_audio] Microphone present: {audio.is_microphone_present()}")
    print(f"[test_audio] Speaker present: {audio.is_speaker_present()}")
    print(f"[test_audio] Input device: {audio.device_input}")
    print(f"[test_audio] Output device: {audio.device_output}")

    output_path = PROJECT_ROOT / "data" / "test_record.wav"
    print("[test_audio] Recording 5 seconds...")
    recorded = audio.record(duration=5, output_path=output_path)
    print(f"[test_audio] Recorded: {recorded.name} (exists={recorded.exists()})")

    print("[test_audio] Playing back...")
    try:
        audio.play(recorded)
        print("[test_audio] Playback finished")
    except Exception as exc:
        print(f"[test_audio] Playback skipped: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
