# AI Translator OS v1.0

Complete offline AI translator for Raspberry Pi 3.

## Hardware

- Raspberry Pi 3 (Raspberry Pi OS Lite 64-bit)
- LCD1602 I2C (SDA GPIO2, SCL GPIO3)
- USB microphone and USB speaker
- Buttons with internal pull-up on GPIO17/27/22/23/24

## Project Layout

- `src/main.py` – application entry point
- `src/managers/` – modular managers (LCD, audio, speech, TTS, ...)
- `src/utils/` – I2C and system helpers
- `config/config.json` – runtime configuration
- `scripts/translator-os.service` – systemd auto-start unit
- `Dockerfile` + `docker-compose.yml` – Docker runtime

## Quick Start

1. Install Raspberry Pi OS Lite 64-bit.
2. Copy this project to `/opt/translator` on the Pi.
3. Download the offline models on a PC with internet using `python scripts/download_models.py` and copy them to `models/whisper/`, `models/nllb/`, and `models/piper/`.
4. Run the automated setup:

   ```bash
   sudo chmod +x /opt/translator/scripts/setup.sh
   sudo /opt/translator/scripts/setup.sh
   ```

   This installs Docker, enables I2C, builds the container, and enables auto-start on boot.

5. Reboot — the translator starts automatically.

## Documentation

- `docs/PROJECT_SPEC.md` — full system specification
- `docs/ARCHITECTURE.md` — project structure and data flow
- `docs/HARDWARE.md` — wiring and GPIO setup
- `docs/DOCKER.md` — container deployment guide
- `docs/TEST_PLAN.md` — testing plan
- `docs/TASKS.md` — remaining development tasks

## Notes

- All translation runs offline using local models.
- Place language packs in `data/language_packs/`
- Place the custom dictionary in `data/dictionary.json`
- USB and microSD update packages are detected by `UpdateManager`.
- `WatchdogManager` restarts individual modules without rebooting the Pi.
