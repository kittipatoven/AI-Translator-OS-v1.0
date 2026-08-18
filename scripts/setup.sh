#!/bin/bash
# AI Translator OS v1.0 — Installer v2
set -euo pipefail

APP_DIR="/opt/translator"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PI_USER="${SUDO_USER:-${USER:-pi}}"

log() { echo "[setup] $1"; }
warn() { echo "[setup] WARNING: $1" >&2; }
error() { echo "[setup] ERROR: $1" >&2; exit 1; }

# ---------------- helpers ----------------

__installed() {
    test -d "${APP_DIR}" && test -f "${APP_DIR}/docker-compose.yml"
}

__require_installed() {
    if ! __installed; then
        error "AI Translator OS is not installed. Run: sudo ${0} install"
    fi
}

fix_permissions() {
    log "Setting ownership for ${APP_DIR}..."
    chown -R "${PI_USER}:${PI_USER}" "${APP_DIR}" 2>/dev/null || true
    chmod +x "${APP_DIR}/scripts/"*.sh 2>/dev/null || true
}

check_root() {
    if [[ "${EUID:-0}" -ne 0 ]]; then
        error "Please run as root or with sudo"
    fi
}

get_arch() { uname -m; }

get_pi_model() {
    local model=""
    if [[ -f /sys/firmware/devicetree/base/model ]]; then
        model="$(tr -d '\0' < /sys/firmware/devicetree/base/model)"
    fi
    if [[ -z "${model}" ]] && grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
        model="$(grep -m1 "Model" /proc/cpuinfo 2>/dev/null | cut -d: -f2- | sed 's/^ *//')"
    fi
    echo "${model:-Unknown}"
}

get_total_ram_mb() {
    awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 0
}

get_available_disk_gb() {
    df -BG "${APP_DIR}" 2>/dev/null | tail -1 | awk '{print $4}' | tr -d 'G' || echo 0
}

wait_for_apt_locks() {
    _apt_locked() {
        for lock in /var/lib/apt/lists/lock /var/lib/dpkg/lock /var/lib/dpkg/lock-frontend /var/cache/apt/archives/lock; do
            [[ -e "${lock}" ]] && return 0
        done
        for p in apt apt-get dpkg unattended-upgrade packagekit packagekitd apt-daily apt-daily-upgrade; do
            pgrep -x "${p}" &>/dev/null && return 0
        done
        return 1
    }
    for i in $(seq 1 90); do
        if ! _apt_locked; then
            return 0
        fi
        log "Waiting for apt/dpkg lock... ${i}s"
        sleep 1
    done
    return 1
}

print_throttle_status() {
    local v="$1"
    case "${v}" in
        0x0|0x0*) echo "OK" ;;
        0x50000) echo "Under-voltage now & previously" ;;
        0x20000) echo "Under-voltage now" ;;
        0x80000) echo "Throttled now" ;;
        0x40000) echo "Throttled previously" ;;
        *) echo "Value ${v}" ;;
    esac
}

# ---------------- commands ----------------

cmd_help() {
    cat <<'EOF'
AI Translator OS v1.0 Setup v2

Usage: sudo ./scripts/setup.sh [MODE]

Modes:
  install            Full install
  update             Update project and rebuild image
  repair             Repair containers / service
  uninstall          Stop, disable and remove /opt/translator
  doctor             Run system diagnostics
  status             Show status
  logs               Show container logs
  restart            Restart translator container
  stop               Stop translator container
  test-audio         Test microphone & speaker
  test-lcd           Test LCD1602
  test-buttons       Test 5 push buttons
  test-ai            Run AI pipeline self-test
  download-models    Download models
  backup             Backup config/data
  restore            Restore from backup
  help               Show this help
EOF
}

cmd_status() {
    if ! __installed; then
        log "Not installed in ${APP_DIR}"
        log "Run: sudo ${0} install"
        exit 1
    fi
    python3 "${APP_DIR}/scripts/status.py" 2>/dev/null || true
    log "Container status:"
    docker compose -f "${APP_DIR}/docker-compose.yml" ps 2>/dev/null || true
}

cmd_logs() {
    __require_installed
    docker compose -f "${APP_DIR}/docker-compose.yml" logs --tail 200 "$@" 2>/dev/null || true
}

cmd_restart() {
    __require_installed
    docker compose -f "${APP_DIR}/docker-compose.yml" restart || error "docker compose restart failed"
    log "Restarted"
}

cmd_stop() {
    __require_installed
    docker compose -f "${APP_DIR}/docker-compose.yml" down || warn "docker compose down failed"
    log "Stopped"
}

cmd_test_audio() {
    __require_installed
    docker compose -f "${APP_DIR}/docker-compose.yml" run --rm translator python /app/scripts/test_audio.py
}

cmd_test_lcd() {
    __require_installed
    docker compose -f "${APP_DIR}/docker-compose.yml" run --rm translator python /app/scripts/test_lcd.py
}

cmd_test_buttons() {
    __require_installed
    docker compose -f "${APP_DIR}/docker-compose.yml" run --rm translator python /app/scripts/test_buttons.py
}

cmd_test_ai() {
    __require_installed
    docker compose -f "${APP_DIR}/docker-compose.yml" run --rm translator python /app/scripts/test_ai_pipeline.py
}

cmd_doctor() {
    if __installed; then
        bash "${APP_DIR}/scripts/doctor.sh"
    else
        bash "${PROJECT_ROOT}/scripts/doctor.sh"
    fi
}

cmd_download_models() {
    if __installed; then
        bash "${APP_DIR}/scripts/download_models.sh" "$@"
    else
        error "Not installed. Run install first."
    fi
}

cmd_backup() {
    __require_installed
    bash "${APP_DIR}/scripts/backup.sh" "${1:-}"
}

cmd_restore() {
    __require_installed
    bash "${APP_DIR}/scripts/restore.sh" "${1:-}"
}

cmd_update() {
    __require_installed
    log "Updating AI Translator OS..."
    if [[ -d "${PROJECT_ROOT}/.git" ]]; then
        git -C "${PROJECT_ROOT}" pull || warn "git pull failed"
    fi
    rsync -a --delete \
        --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
        --exclude='.cache' --exclude='models' --exclude='logs' \
        --exclude='cache' --exclude='data/history.jsonl' --exclude='data/history' \
        --exclude='backups' \
        "${PROJECT_ROOT}/" "${APP_DIR}/" || error "rsync failed"
    fix_permissions
    cd "${APP_DIR}"
    export DOCKER_BUILDKIT=0
    docker compose build || error "Docker build failed"
    docker compose up -d || error "docker compose up failed"
    log "Update complete"
}

cmd_repair() {
    log "Smart repair..."
    if ! command -v docker &>/dev/null; then
        error "Docker not installed. Run: sudo ${0} install"
    fi
    if ! systemctl is-active --quiet docker 2>/dev/null; then
        systemctl start docker 2>/dev/null || error "Cannot start Docker"
    fi
    if [[ ! -d "${APP_DIR}" ]]; then
        error "${APP_DIR} not found. Run: sudo ${0} install"
    fi
    fix_permissions
    cd "${APP_DIR}"
    docker compose build 2>/dev/null || true
    docker compose up -d --force-recreate 2>/dev/null || true
    cp "${APP_DIR}/scripts/translator-os.service" /etc/systemd/system/translator-os.service
    sed -i "s|WorkingDirectory=.*|WorkingDirectory=${APP_DIR}|" /etc/systemd/system/translator-os.service
    sed -i "s|ExecStart=.*|ExecStart=/usr/bin/docker compose -f ${APP_DIR}/docker-compose.yml up -d|" /etc/systemd/system/translator-os.service
    sed -i "s|ExecStop=.*|ExecStop=/usr/bin/docker compose -f ${APP_DIR}/docker-compose.yml down|" /etc/systemd/system/translator-os.service
    systemctl daemon-reload
    systemctl enable translator-os 2>/dev/null || true
    systemctl restart translator-os 2>/dev/null || warn "Could not restart systemd service"
    log "Repair complete"
}

cmd_uninstall() {
    log "Uninstalling..."
    systemctl disable translator-os 2>/dev/null || true
    systemctl stop translator-os 2>/dev/null || true
    if __installed; then
        cd "${APP_DIR}"
        docker compose down 2>/dev/null || true
    fi
    rm -rf "${APP_DIR}"
    log "Uninstalled"
    log "Run 'docker system prune' to free images"
}

# ---------------- install flow ----------------

cmd_install() {
    check_root

    ARCH="$(get_arch)"
    PI_MODEL="$(get_pi_model)"
    TOTAL_RAM_MB="$(get_total_ram_mb)"

    # OS / arch
    if [[ "$(uname -s)" != "Linux" ]]; then
        error "This installer is for Linux only."
    fi
    if [[ "${ARCH}" != "aarch64" ]]; then
        error "Requires aarch64. Detected ${ARCH}. Please flash Raspberry Pi OS Lite 64-bit."
    fi
    if [[ -f /etc/os-release ]]; then
        ID="$(source /etc/os-release; echo "${ID:-}")"
        ID_LIKE="$(source /etc/os-release; echo "${ID_LIKE:-}")"
        if [[ "${ID_LIKE}" != *"debian"* && "${ID}" != "raspbian" && "${ID}" != "debian" ]]; then
            warn "OS is not Debian-based. Continuing anyway."
        fi
    fi

    log "OS: $(cat /etc/os-release 2>/dev/null | grep -E '^PRETTY_NAME' | cut -d= -f2- | tr -d '"')"
    log "Arch: ${ARCH}"
    log "Pi Model: ${PI_MODEL}"
    log "RAM: ${TOTAL_RAM_MB} MB"

    # Throttling / temp
    if command -v vcgencmd &>/dev/null; then
        TEMP="$(vcgencmd measure_temp 2>/dev/null | cut -d= -f2 | cut -d"'" -f1)"
        THROTTLED="$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)"
        log "Temperature: ${TEMP}"
        log "Throttled: ${THROTTLED} = $(print_throttle_status "${THROTTLED}")"
        if [[ "${THROTTLED}" != "0x0" && "${THROTTLED}" != "0x0"* ]]; then
            warn "Power/thermal issue detected. Consider a better PSU/cooling."
        fi
    fi

    # Prevent accidental overwrite
    if [[ -d "${APP_DIR}" ]]; then
        warn "${APP_DIR} already exists."
        if [[ -t 0 ]]; then
            echo -n "[setup] Re-install, update, or abort? [u=update/r=reinstall/a=abort] (default u): "
            read -r choice
        else
            choice="u"
        fi
        case "${choice:-u}" in
            r|R|reinstall)
                rm -rf "${APP_DIR}"
                ;;
            a|A|abort)
                log "Aborted"
                exit 0
                ;;
            *)
                cmd_update
                return
                ;;
        esac
    fi

    # Build profile
    log "Hardware: CPU=$(nproc) RAM=${TOTAL_RAM_MB}MB"
    log "Build profiles:"
    log "  [1] Pi 3 Safe (recommended for Pi 3)"
    log "  [2] Pi 4/5"
    log "  [3] High Performance"
    if [[ -t 0 ]]; then
        echo -n "[setup] Choose profile [1/2/3] (default 1): "
        read -r profile
    else
        profile="1"
    fi
    profile="${profile:-1}"
    case "${profile}" in
        1) JOBS=1; BUILD_PROFILE="pi3-safe" ;;
        2) JOBS=2; BUILD_PROFILE="pi4" ;;
        3) JOBS=2; BUILD_PROFILE="highperf" ;;
        *) JOBS=1; BUILD_PROFILE="pi3-safe" ;;
    esac
    log "Selected: ${BUILD_PROFILE} (JOBS=${JOBS})"

    # APT
    for svc in packagekit packagekitd apt-daily apt-daily-upgrade; do
        systemctl stop "${svc}" 2>/dev/null || true
    done
    wait_for_apt_locks || warn "apt locks did not clear in time"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -q || error "apt-get update failed"
    apt-get install -y -q --no-install-recommends \
        curl rsync i2c-tools alsa-utils git build-essential cmake \
        libopenblas-dev libgomp1 libatomic1 python3-pip libgpiod2 \
        || error "apt-get install failed"

    # Docker
    if ! command -v docker &>/dev/null; then
        log "Installing Docker..."
        curl -fsSL https://get.docker.com | sh || error "Docker install failed"
        usermod -aG docker "${PI_USER}" || true
        systemctl enable docker
        systemctl start docker || error "Cannot start Docker"
    fi
    if ! docker compose version &>/dev/null; then
        apt-get install -y -q --no-install-recommends docker-compose-plugin || error "Docker compose install failed"
    fi

    # Interfaces
    log "Enabling I2C / audio / GPIO..."
    if command -v raspi-config &>/dev/null; then
        raspi-config nonint do_i2c 0 2>/dev/null || true
        raspi-config nonint do_spi 0 2>/dev/null || true
    fi
    modprobe i2c-dev 2>/dev/null || true
    usermod -aG audio,i2c,gpio "${PI_USER}" 2>/dev/null || true

    # Copy project
    log "Copying project to ${APP_DIR}..."
    mkdir -p "${APP_DIR}"
    rsync -a --delete \
        --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
        --exclude='.cache' --exclude='models' --exclude='logs' \
        --exclude='cache' --exclude='data/history.jsonl' --exclude='data/history' \
        --exclude='backups' \
        "${PROJECT_ROOT}/" "${APP_DIR}/"

    mkdir -p "${APP_DIR}/data" "${APP_DIR}/logs" "${APP_DIR}/cache" \
        "${APP_DIR}/models/whisper" "${APP_DIR}/models/nllb" "${APP_DIR}/models/piper"

    # Save build profile to config
    if [[ -f "${APP_DIR}/config/config.json" ]]; then
        python3 - <<EOF || true
import json, os
path = "${APP_DIR}/config/config.json"
with open(path) as f:
    cfg = json.load(f)
cfg["build_profile"] = "${BUILD_PROFILE}"
cfg["build_jobs"] = ${JOBS}
with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
EOF
    fi

    # Swap
    if [[ ${TOTAL_RAM_MB} -lt 2048 ]]; then
        log "Low RAM (${TOTAL_RAM_MB}MB). Configuring 2GB swap..."
        if [[ ! -f /swapfile ]]; then
            fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
            chmod 600 /swapfile
            mkswap /swapfile
            swapon /swapfile
            grep -q "^/swapfile" /etc/fstab || echo "/swapfile none swap sw 0 0" >> /etc/fstab
        fi
        if [[ -f /etc/sysctl.conf ]]; then
            if ! grep -q "^vm.swappiness" /etc/sysctl.conf; then
                echo "vm.swappiness=10" >> /etc/sysctl.conf
            fi
        fi
        sysctl -w vm.swappiness=10 2>/dev/null || true
    fi

    # Disk
    DISK_AVAIL="$(get_available_disk_gb)"
    log "Available disk: ${DISK_AVAIL} GB"
    if [[ ${DISK_AVAIL} -lt 5 ]]; then
        error "Need at least 5GB free. Only ${DISK_AVAIL}GB available."
    elif [[ ${DISK_AVAIL} -lt 10 ]]; then
        warn "Low disk space: ${DISK_AVAIL}GB remaining."
    fi

    # I2C / LCD check
    if command -v i2cdetect &>/dev/null && [[ -c /dev/i2c-1 ]]; then
        LCD_ADDR="$(i2cdetect -y 1 2>/dev/null | grep -E "(27|3F)" | awk '{print $NF}' | head -1 || true)"
        if [[ -n "${LCD_ADDR}" ]]; then
            log "LCD1602 detected at 0x${LCD_ADDR}"
        else
            warn "LCD1602 not detected. Web UI can still control the system."
        fi
    else
        warn "I2C not available. LCD will use console fallback."
    fi

    # Audio check
    if command -v arecord &>/dev/null; then
        if arecord -l 2>/dev/null | grep -q "card"; then
            log "USB Microphone detected"
        else
            warn "No microphone detected. Check USB and volume."
        fi
    else
        warn "arecord not found"
    fi
    if command -v aplay &>/dev/null; then
        if aplay -l 2>/dev/null | grep -q "card"; then
            log "USB Speaker detected"
        else
            warn "No speaker detected. Check USB and volume."
        fi
    else
        warn "aplay not found"
    fi

    # GPIO check
    if [[ -c /dev/gpiomem || -c /dev/gpiochip0 ]]; then
        log "GPIO device present"
    else
        warn "No GPIO device. Buttons unavailable; use web UI."
    fi

    # Models check/download
    log "Checking models..."
    missing=0
    for d in whisper nllb piper; do
        if [[ -z "$(ls -A "${APP_DIR}/models/${d}" 2>/dev/null)" ]]; then
            missing=$((missing + 1))
        fi
    done
    if [[ ${missing} -eq 0 ]]; then
        log "Models are present"
    else
        warn "Some model directories are empty"
        if ping -q -c 1 -W 3 1.1.1.1 &>/dev/null; then
            if [[ -t 0 ]]; then
                echo -n "[setup] Download default models now? [y/N] (default y): "
                read -r dld
            else
                dld="y"
            fi
            if [[ "${dld:-y}" == [yY]* ]]; then
                bash "${APP_DIR}/scripts/download_models.sh" || warn "Model download failed"
            fi
        else
            warn "No internet. Please copy models manually before using translation."
        fi
    fi

    # Build Docker
    log "Building Docker image (JOBS=${JOBS})..."
    cd "${APP_DIR}"
    export DOCKER_BUILDKIT=0
    BUILD_OK=0
    if docker compose build --build-arg "JOBS=${JOBS}"; then
        BUILD_OK=1
    elif docker compose build --build-arg "JOBS=1" --no-cache; then
        BUILD_OK=1
    fi
    if [[ ${BUILD_OK} -ne 1 ]]; then
        error "Docker build failed"
    fi

    # Unit tests
    log "Running unit tests..."
    docker compose run --rm translator python -m unittest discover -s /app/tests -v 2>/dev/null || warn "Unit tests had issues"

    # Start
    log "Starting AI Translator OS..."
    docker compose up -d || error "docker compose up failed"

    # systemd
    log "Installing systemd service..."
    cp "${APP_DIR}/scripts/translator-os.service" /etc/systemd/system/translator-os.service
    sed -i "s|WorkingDirectory=.*|WorkingDirectory=${APP_DIR}|" /etc/systemd/system/translator-os.service
    sed -i "s|ExecStart=.*|ExecStart=/usr/bin/docker compose -f ${APP_DIR}/docker-compose.yml up -d|" /etc/systemd/system/translator-os.service
    sed -i "s|ExecStop=.*|ExecStop=/usr/bin/docker compose -f ${APP_DIR}/docker-compose.yml down|" /etc/systemd/system/translator-os.service
    sed -i "s|ExecReload=.*|ExecReload=/usr/bin/docker compose -f ${APP_DIR}/docker-compose.yml restart|" /etc/systemd/system/translator-os.service
    systemctl daemon-reload
    systemctl enable translator-os
    systemctl start translator-os || warn "systemd start failed"

    # Container test
    log "Checking container..."
    sleep 5
    if docker ps | grep -q "translator"; then
        log "Container is running"
    else
        warn "Container not running. Check logs."
    fi
    sleep 5
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/health 2>/dev/null | grep -q "200"; then
        log "Health check passed (http://localhost:8080/api/health)"
    else
        warn "Health check not yet passing. The web UI may still be starting."
    fi

    fix_permissions

    # Diagnostic report
    log "Running doctor..."
    bash "${APP_DIR}/scripts/doctor.sh" || true

    log "Installation complete. Access the dashboard at http://$(hostname -I | awk '{print $1}' | head -1):8080"
}

# ---------------- main dispatch ----------------

MODE="${1:-install}"
shift || true

case "${MODE}" in
    install)                 cmd_install ;;
    update)                  cmd_update ;;
    repair)                  cmd_repair ;;
    uninstall)               cmd_uninstall ;;
    doctor)                  cmd_doctor ;;
    status)                  cmd_status ;;
    logs)                    cmd_logs "$@" ;;
    restart)                 cmd_restart ;;
    stop)                    cmd_stop ;;
    test-audio)              cmd_test_audio ;;
    test-lcd)                cmd_test_lcd ;;
    test-buttons)            cmd_test_buttons ;;
    test-ai)                 cmd_test_ai ;;
    download-models)         cmd_download_models "$@" ;;
    backup)                  cmd_backup "${1:-}"; shift || true ;;
    restore)                 cmd_restore "${1:-}"; shift || true ;;
    help|--help|-h)          cmd_help ;;
    *)                       error "Unknown mode: ${MODE}. Use help" ;;
esac
