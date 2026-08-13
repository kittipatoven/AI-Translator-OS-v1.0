#!/bin/bash
# Run all hardware/AI smoke tests on the Raspberry Pi or inside the Docker container.
set -e

cd "$(dirname "$0")/.."

echo "=== AI Translator OS — Pi Smoke Test ==="

echo "[1/5] LCD1602 I2C test"
python3 scripts/test_lcd.py

echo "[2/5] GPIO buttons test"
python3 scripts/test_buttons.py

echo "[3/5] USB microphone/speaker test"
python3 scripts/test_audio.py

echo "[4/5] NLLB translation test"
python3 scripts/test_translation.py

echo "[5/5] Web UI/API (Flask will be started by main.py)"
echo "      Please open http://$(hostname -I | awk '{print $1}'):8080 in a browser"

echo "=== Smoke test complete ==="
