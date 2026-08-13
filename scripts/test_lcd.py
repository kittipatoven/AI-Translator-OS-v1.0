#!/usr/bin/env python3
"""LCD1602 I2C test script for AI Translator OS.

Displays two demo messages on the LCD. Falls back to console output on
Windows, macOS, or any system without I2C hardware.
"""

import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from managers.lcd_manager import LCDManager


def load_config():
    config_path = PROJECT_ROOT / "config" / "config.json"
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def main():
    config = load_config()
    bus = config.get("lcd", {}).get("i2c_bus", 1)
    address = config.get("lcd", {}).get("i2c_address", 0x27)

    print(f"[test_lcd] Opening LCD at I2C bus={bus} address=0x{address:02X}")
    lcd = LCDManager(bus=bus, address=address)

    print("[test_lcd] Displaying 'AI Translator' / 'Ready'")
    lcd.display("AI Translator", "Ready")
    time.sleep(2)

    print("[test_lcd] Displaying 'LCD Test' / 'OK'")
    lcd.display("LCD Test", "OK")
    time.sleep(2)

    print("[test_lcd] Clearing LCD")
    lcd.clear()
    print("[test_lcd] Done")


if __name__ == "__main__":
    main()
