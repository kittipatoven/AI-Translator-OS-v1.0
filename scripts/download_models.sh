#!/bin/bash
# AI Translator OS v1.0 — Offline model download wrapper
set -euo pipefail

APP_DIR="/opt/translator"

usage() {
    cat <<'EOF'
Usage: sudo ./scripts/download_models.sh [options]

Wrapper around scripts/download_models.py for the installed environment.
If internet is available, downloads the recommended default model set.

Options (passed to Python script):
  --all              Download default set
  --whisper VARIANT  Whisper model variant
  --nllb VARIANT     NLLB variant
  --voice VOICE      Piper voice, e.g. en_US-lessac-low
  --output DIR       Output directory (default: /opt/translator/models)
  -h, --help         Show help
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

OUTPUT_DIR="${APP_DIR}/models"
python3 "${APP_DIR}/scripts/download_models.py" --output "${OUTPUT_DIR}" --all "$@" || {
    echo "[download_models] Failed. Copy models manually." >&2
    exit 1
}
