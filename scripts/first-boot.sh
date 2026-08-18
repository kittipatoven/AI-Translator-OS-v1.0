#!/bin/bash
# AI Translator OS v1.0 — First boot / initial setup helpers
set -euo pipefail

APP_DIR="/opt/translator"
PI_USER="${SUDO_USER:-${USER:-pi}}"

log() { echo "[first-boot] $1"; }

set_timezone() {
    if [[ -f /etc/localtime ]] && command -v timedatectl &>/dev/null; then
        timedatectl set-timezone Asia/Bangkok 2>/dev/null || true
    fi
}

create_dirs() {
    mkdir -p "${APP_DIR}/logs"
    mkdir -p "${APP_DIR}/cache"
    mkdir -p "${APP_DIR}/data"
    mkdir -p "${APP_DIR}/models/whisper"
    mkdir -p "${APP_DIR}/models/nllb"
    mkdir -p "${APP_DIR}/models/piper"
    chown -R "${PI_USER}:${PI_USER}" "${APP_DIR}/logs" "${APP_DIR}/cache" "${APP_DIR}/data" 2>/dev/null || true
}

enable_hardware() {
    if command -v raspi-config &>/dev/null; then
        raspi-config nonint do_i2c 0 2>/dev/null || true
        raspi-config nonint do_spi 0 2>/dev/null || true
        raspi-config nonint do_spi 0 2>/dev/null || true
    fi
    modprobe i2c-dev 2>/dev/null || true
    usermod -aG audio,i2c,gpio "${PI_USER}" 2>/dev/null || true
}

basic_health() {
    log "Running basic health check..."
    if [[ -f "${APP_DIR}/scripts/doctor.sh" ]]; then
        bash "${APP_DIR}/scripts/doctor.sh" || true
    fi
}

main() {
    log "AI Translator OS first-boot setup"
    set_timezone
    create_dirs
    enable_hardware
    basic_health
    log "First-boot setup complete"
}

main "$@"
