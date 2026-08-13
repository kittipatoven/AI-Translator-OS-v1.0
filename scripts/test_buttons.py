#!/usr/bin/env python3
"""Button test script for AI Translator OS.

On the Raspberry Pi this will use real GPIO. On Windows/macOS/Linux it
falls back to simulating each button press and verifying the handler fires.
"""

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from managers.button_manager import ButtonManager


def load_config():
    config_path = PROJECT_ROOT / "config" / "config.json"
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def make_handler(name):
    def handler():
        print(f"[button] {name} triggered")
    return handler


def main():
    config = load_config()
    pins = config.get("buttons", {
        "left": 17,
        "right": 27,
        "speak": 22,
        "replay": 23,
        "menu": 24,
    })

    print("[test_buttons] Registering handlers for:", list(pins.keys()))
    bm = ButtonManager(pins)
    for name in pins:
        bm.on(name, short=make_handler(name))

    try:
        bm.start()
    except Exception as exc:
        print(f"[test_buttons] Button start error: {exc}")
        return 1

    print("[test_buttons] Simulating each button press...")
    for name in pins:
        print(f"[test_buttons] Simulating {name}")
        bm.simulate(name)
        time.sleep(0.3)

    bm.stop()
    print("[test_buttons] Done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
