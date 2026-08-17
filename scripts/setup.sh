#!/bin/bash
# AI Translator OS v1.0 — Fully automated installation script
# Run as root or with sudo on the target Raspberry Pi / Linux:
#   chmod +x scripts/setup.sh
#   sudo ./scripts/setup.sh
set -euo pipefail

APP_DIR="/opt/translator"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PI_USER="${SUDO_USER:-${USER:-pi}}"

log() { echo "[setup] $1"; }
error() { echo "[setup] ERROR: $1" >&2; exit 1; }
warn() { echo "[setup] WARNING: $1" >&2; }

MODE="${1:-install}"

# Helper: are the Docker image and /opt/translator present?
__installed() {
    test -d "${APP_DIR}" && test -f "${APP_DIR}/docker-compose.yml"
}

__require_installed() {
    if ! __installed; then
        error "AI Translator OS is not installed. Run: sudo ${0} install"
    fi
}

fix_permissions() {
    log "Setting ownership for ${APP_DIR} to ${PI_USER}..."
    chown -R "${PI_USER}:${PI_USER}" "${APP_DIR}" 2>/dev/null || true
    chmod +x "${APP_DIR}/scripts/setup.sh" 2>/dev/null || true
}

run_diagnostic() {
    __require_installed
    log "Running hardware & AI diagnostics..."
    docker compose -f "${APP_DIR}/docker-compose.yml" run --rm translator python /app/scripts/diagnostic.py
}

run_test_audio() {
    __require_installed
    log "Running audio test..."
    docker compose -f "${APP_DIR}/docker-compose.yml" run --rm translator python /app/scripts/test_audio.py
}

run_test_lcd() {
    __require_installed
    log "Running LCD test..."
    docker compose -f "${APP_DIR}/docker-compose.yml" run --rm translator python /app/scripts/test_lcd.py
}

run_test_buttons() {
    __require_installed
    log "Running button test..."
    docker compose -f "${APP_DIR}/docker-compose.yml" run --rm translator python /app/scripts/test_buttons.py
}

run_test_ai() {
    __require_installed
    log "Running AI pipeline self-test..."
    docker compose -f "${APP_DIR}/docker-compose.yml" run --rm translator python /app/scripts/test_ai_pipeline.py
}

run_status() {
    if ! __installed; then
        log "AI Translator OS is not installed in ${APP_DIR}."
        log "Run: sudo ${0} install"
        exit 1
    fi
    python3 "${APP_DIR}/scripts/status.py"
}

do_update() {
    __require_installed
    log "Updating AI Translator OS..."
    if [[ -d "${PROJECT_ROOT}/.git" ]]; then
        git -C "${PROJECT_ROOT}" pull || warn "git pull failed"
    else
        warn "No .git directory; cannot auto-update from git"
    fi
    log "Syncing to ${APP_DIR}..."
    rsync -a --delete \
        --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
        --exclude='.cache' --exclude='models' --exclude='logs' \
        --exclude='cache' --exclude='data/history.jsonl' \
        "${PROJECT_ROOT}/" "${APP_DIR}/" || error "rsync failed"
    fix_permissions
    log "Rebuilding Docker image..."
    cd "${APP_DIR}"
    export DOCKER_BUILDKIT=0
    docker compose build || error "Docker build failed"
    log "Restarting..."
    docker compose up -d || error "docker compose up failed"
    log "Update complete"
}

do_repair() {
    log "Starting smart repair..."

    if ! command -v docker &>/dev/null; then
        error "Docker not installed. Run: sudo ${0} install"
    fi

    # 1. Ensure Docker is running
    if ! systemctl is-active --quiet docker 2>/dev/null; then
        log "Docker not running. Starting..."
        systemctl start docker 2>/dev/null || error "Cannot start Docker"
    fi

    # 2. Ensure install directory exists
    if [[ ! -d "${APP_DIR}" ]]; then
        error "${APP_DIR} not found. Run: sudo ${0} install"
    fi

    # 3. Fix permissions
    fix_permissions

    # 4. Restore missing models from bundled archive if present
    missing=0
    for d in whisper nllb piper; do
        if [[ -z "$(ls -A "${APP_DIR}/models/${d}" 2>/dev/null)" ]]; then
            missing=1
        fi
    done
    if [[ ${missing} -eq 1 ]]; then
        log "Some models are missing. Looking for models.tar.gz..."
        for tar_path in "${PROJECT_ROOT}/models.tar.gz" "/home/${PI_USER}/models.tar.gz" "${APP_DIR}/models.tar.gz"; do
            if [[ -f "${tar_path}" ]]; then
                log "Restoring models from ${tar_path}..."
                rm -rf "${APP_DIR}/models"
                mkdir -p "${APP_DIR}/models"
                tar -xzf "${tar_path}" -C "${APP_DIR}/models/" || log "WARNING: failed to extract models"
                break
            fi
        done
    fi

    # 5. Build / restart container
    cd "${APP_DIR}"
    if ! docker compose ps 2>/dev/null | grep -q "translator"; then
        log "Container not running. Starting..."
        docker compose up -d || error "docker compose up failed"
    else
        cid="$(docker compose ps -q 2>/dev/null | head -1)"
        if [[ -n "${cid}" ]]; then
            health="$(docker inspect --format='{{.State.Health.Status}}' "${cid}" 2>/dev/null)"
            if [[ "${health}" == "unhealthy" ]]; then
                log "Container is unhealthy. Restarting..."
                docker compose restart
            else
                log "Container is running (health: ${health:-unknown})"
            fi
        fi
    fi

    # 6. Ensure systemd auto-start is installed
    if [[ ! -f /etc/systemd/system/translator-os.service ]]; then
        log "systemd service missing. Reinstalling..."
        cp "${APP_DIR}/scripts/translator-os.service" /etc/systemd/system/translator-os.service
        sed -i "s|WorkingDirectory=.*|WorkingDirectory=${APP_DIR}|" /etc/systemd/system/translator-os.service
        sed -i "s|ExecStart=.*|ExecStart=/usr/bin/docker compose -f ${APP_DIR}/docker-compose.yml up|" /etc/systemd/system/translator-os.service
        sed -i "s|ExecStop=.*|ExecStop=/usr/bin/docker compose -f ${APP_DIR}/docker-compose.yml down|" /etc/systemd/system/translator-os.service
        systemctl daemon-reload
        systemctl enable translator-os.service
    fi
    systemctl restart translator-os.service 2>/dev/null || log "WARNING: could not restart systemd service"

    log "Smart repair complete. Check status with: ${0} --status"
}

do_uninstall() {
    log "Uninstalling AI Translator OS..."
    systemctl disable translator-os.service 2>/dev/null || true
    systemctl stop translator-os.service 2>/dev/null || true
    if __installed; then
        cd "${APP_DIR}"
        docker compose down 2>/dev/null || true
    fi
    rm -rf "${APP_DIR}"
    log "Uninstalled. Run 'docker system prune' to free images"
}

show_help() {
    cat <<'EOF'
AI Translator OS v1.0 Setup

Usage: sudo ./scripts/setup.sh [MODE]

Modes:
  install            Full install (default)
  --diagnostic       Run hardware/AI diagnostics
  --test-audio       Test microphone & speaker
  --test-lcd         Test LCD1602
  --test-buttons     Test 5 push buttons
  --test-ai          Run AI pipeline self-test
  --status           Show system and container status
  --repair           Smart repair: Docker, container, models, service
  --update           Update repo and rebuild image
  --uninstall        Stop, disable and remove /opt/translator
  --help             Show this help
EOF
}

case "$MODE" in
    install|--install)
        ;;
    --diagnostic|diagnostic) run_diagnostic; exit 0 ;;
    --test-audio) run_test_audio; exit 0 ;;
    --test-lcd) run_test_lcd; exit 0 ;;
    --test-buttons) run_test_buttons; exit 0 ;;
    --test-ai|test-ai) run_test_ai; exit 0 ;;
    --status) run_status; exit 0 ;;
    --repair|repair) do_repair; exit 0 ;;
    --update) do_update; exit 0 ;;
    --uninstall) do_uninstall; exit 0 ;;
    --help|-h) show_help; exit 0 ;;
    *) error "Unknown mode: ${MODE}. Use --help for usage." ;;
esac

# Detect architecture and choose safe build parallelism
ARCH="$(uname -m)"
IS_PI=0
if grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    IS_PI=1
fi

if [[ "$ARCH" == "aarch64" ]] || [[ "$ARCH" == "arm64" ]] || [[ "$IS_PI" -eq 1 ]]; then
    JOBS=1
    log "Detected ARM/SBC host: using -j1 for whisper.cpp to avoid OOM."
else
    JOBS=$(nproc)
    log "Detected x86_64 host: using -j${JOBS} for whisper.cpp."
fi

# 0. Architecture check: ctranslate2 and piper only provide wheels/binaries for AArch64
if [[ "$ARCH" != "aarch64" ]]; then
    error "AI Translator OS requires a 64-bit (aarch64) Raspberry Pi OS. Detected: ${ARCH}. ctranslate2 and Piper do not support 32-bit ARM. Please re-flash the SD card with Raspberry Pi OS Lite 64-bit."
fi

# 1. OS check
if [[ "$(uname -s)" != "Linux" ]]; then
    error "This installer is for Linux/Raspberry Pi only."
fi

if [[ "${FORCE_REPAIR:-0}" -eq 1 ]]; then
    log "Repairing AI Translator OS in ${APP_DIR}..."
else
    log "Installing AI Translator OS to ${APP_DIR}..."
fi

# 2. Install required host packages
log "Updating package lists and installing host dependencies..."

# Stop package manager background services that may lock apt
for svc in packagekit packagekitd apt-daily apt-daily-upgrade; do
    if systemctl is-active --quiet "${svc}" 2>/dev/null; then
        log "Stopping ${svc} to free apt lock..."
        systemctl stop "${svc}" 2>/dev/null || true
    fi
done

# Helper: wait for apt/dpkg/package manager locks to clear
_apt_locked() {
    for lock in /var/lib/apt/lists/lock /var/lib/dpkg/lock /var/lib/dpkg/lock-frontend /var/cache/apt/archives/lock; do
        if [[ -e "${lock}" ]]; then
            if command -v fuser &>/dev/null; then
                fuser -s "${lock}" 2>/dev/null && return 0
            else
                return 0
            fi
        fi
    done
    for p in apt apt-get dpkg unattended-upgrade packagekit packagekitd apt-daily apt-daily-upgrade; do
        pgrep -x "${p}" &>/dev/null && return 0
    done
    return 1
}

# Wait up to 90s for package manager locks to clear
for i in $(seq 1 90); do
    if ! _apt_locked; then
        break
    fi
    log "Waiting for apt/dpkg lock to clear... ${i}s"
    sleep 1
done

export DEBIAN_FRONTEND=noninteractive

# Tolerate slow / flaky Raspberry Pi mirrors during first-time setup
APT_CONF_DIR="/etc/apt/apt.conf.d"
mkdir -p "${APT_CONF_DIR}"
cat > "${APT_CONF_DIR}/99-translator-network" <<'EOF'
Acquire::http::Timeout "120";
Acquire::https::Timeout "120";
Acquire::ftp::Timeout "120";
Acquire::Retries "3";
Acquire::http::Pipeline-Depth "0";
EOF

APT_UPDATE_OK=0
for attempt in 1 2 3; do
    if apt-get update -q; then
        APT_UPDATE_OK=1
        break
    fi
    log "apt-get update attempt ${attempt} failed, retrying..."
    sleep 3
done
if [[ ${APT_UPDATE_OK} -ne 1 ]]; then
    error "apt-get update failed after 3 attempts. Check network and /etc/apt/sources.list"
fi

apt-get install -y -q --no-install-recommends \
    curl rsync i2c-tools alsa-utils git \
    build-essential cmake libopenblas-dev libgomp1 libatomic1 \
    python3-pip \
    || error "apt-get install failed"

# 3. Install Docker if not present
if ! command -v docker &> /dev/null; then
    log "Docker not found. Installing Docker..."
    curl -fsSL https://get.docker.com | sh || error "Docker install failed"
    usermod -aG docker "${PI_USER}" || true
    systemctl enable docker
    systemctl start docker
    log "Docker installed. You may need to re-login for group changes to take effect."
else
    log "Docker already installed."
fi

# 4. Install Docker Compose plugin if not present
if ! docker compose version &> /dev/null; then
    log "Docker Compose plugin not found. Installing..."
    apt-get install -y -q --no-install-recommends docker-compose-plugin \
        || error "Docker Compose install failed"
else
    log "Docker Compose plugin already installed."
fi

# 5. Enable I2C, SPI, and audio interfaces
log "Enabling I2C and audio..."
raspi-config nonint do_i2c 0 2>/dev/null || true
modprobe i2c-dev 2>/dev/null || true
usermod -aG audio "${PI_USER}" 2>/dev/null || true
usermod -aG i2c "${PI_USER}" 2>/dev/null || true

# 6. Copy project to ${APP_DIR}
log "Copying project files to ${APP_DIR}..."
mkdir -p "${APP_DIR}"
if command -v rsync &> /dev/null; then
    rsync -a --delete \
        --exclude='.git' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.cache' \
        --exclude='models' \
        --exclude='logs' \
        --exclude='cache' \
        --exclude='data/history.jsonl' \
        "${PROJECT_ROOT}/" "${APP_DIR}/"
else
    cp -r "${PROJECT_ROOT}/"* "${APP_DIR}/"
fi

# 7. Ensure runtime directories and model paths exist
log "Preparing runtime directories..."
mkdir -p "${APP_DIR}/data" \
         "${APP_DIR}/logs" \
         "${APP_DIR}/cache" \
         "${APP_DIR}/models/whisper" \
         "${APP_DIR}/models/nllb" \
         "${APP_DIR}/models/piper"

# 7a. Add swap on low-RAM devices (Pi 3 / 1GB)
TOTAL_RAM_KB=$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
TOTAL_RAM_GB=$((TOTAL_RAM_KB / 1024 / 1024))
if [[ ${TOTAL_RAM_GB} -lt 2 ]]; then
    if [[ ! -f /swapfile ]]; then
        log "Low RAM detected (${TOTAL_RAM_GB}GB). Adding 2GB swap..."
        fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
        chmod 600 /swapfile
        mkswap /swapfile
        swapon /swapfile
        if ! grep -q "^/swapfile" /etc/fstab; then
            echo "/swapfile none swap sw 0 0" >> /etc/fstab
        fi
    else
        log "Swap file already exists."
    fi
else
    log "RAM >= 2GB, skipping swap creation."
fi

# 7b. Extract bundled models.tar.gz if present (offline install)
for tar_path in "${PROJECT_ROOT}/models.tar.gz" "${APP_DIR}/models.tar.gz" "/home/${PI_USER}/models.tar.gz"; do
    if [[ -f "${tar_path}" ]]; then
        log "Found bundled models at ${tar_path}. Extracting..."
        rm -rf "${APP_DIR}/models"
        mkdir -p "${APP_DIR}/models"
        tar -xzf "${tar_path}" -C "${APP_DIR}/models/" || \
            log "WARNING: failed to extract models from ${tar_path}"
        break
    fi
done

# 8. Check / download models
log "Checking AI models..."
missing=0
for d in whisper nllb piper; do
    if [[ -z "$(ls -A "${APP_DIR}/models/${d}" 2>/dev/null)" ]]; then
        log "WARNING: models/${d}/ is empty."
        missing=1
    fi
done

if [[ ${missing} -eq 1 ]]; then
    if ping -q -c 1 1.1.1.1 &> /dev/null; then
        log "Network available. Attempting to download models..."
        cd "${APP_DIR}"
        if ! python3 -c "import huggingface_hub" 2>/dev/null; then
            log "Installing huggingface_hub..."
            pip3 install --break-system-packages huggingface_hub 2>/dev/null || \
                pip3 install huggingface_hub || \
                log "WARNING: failed to install huggingface_hub"
        fi
        python3 scripts/download_models_offline.py --output models || \
            log "Model download script failed. Please copy models manually."
    else
        log "No network. Please copy pre-downloaded models to models/whisper, models/nllb, models/piper"
    fi
fi

fix_permissions

# 9. Build the Docker image with platform-specific parallelism
log "Building Docker image (whisper.cpp will use -j${JOBS})..."
cd "${APP_DIR}"
export DOCKER_BUILDKIT=0
BUILD_SUCCESS=0
if docker compose build --build-arg "JOBS=${JOBS}"; then
    BUILD_SUCCESS=1
else
    log "Build with -j${JOBS} failed; retrying with -j1..."
    if docker compose build --build-arg "JOBS=1" --no-cache; then
        BUILD_SUCCESS=1
    fi
fi

if [[ ${BUILD_SUCCESS} -ne 1 ]]; then
    error "Docker build failed. Check 'docker compose logs' and /opt/translator/logs."
fi

# 10. Run unit tests inside the container
log "Running unit tests inside container..."
if docker compose run --rm translator python -m unittest discover -s /app/tests -v; then
    log "Unit tests passed."
else
    log "WARNING: Unit tests failed. Check the output above."
fi

# 11. Start the container
log "Starting AI Translator OS..."
docker compose up -d

# 12. Install systemd auto-start service
log "Installing systemd auto-start service..."
cp "${APP_DIR}/scripts/translator-os.service" /etc/systemd/system/translator-os.service
sed -i "s|WorkingDirectory=.*|WorkingDirectory=${APP_DIR}|" /etc/systemd/system/translator-os.service
sed -i "s|ExecStart=.*|ExecStart=/usr/bin/docker compose -f ${APP_DIR}/docker-compose.yml up -d|" /etc/systemd/system/translator-os.service
sed -i "s|ExecStop=.*|ExecStop=/usr/bin/docker compose -f ${APP_DIR}/docker-compose.yml down|" /etc/systemd/system/translator-os.service

systemctl daemon-reload
systemctl enable translator-os.service

# 13. Health check
log "Waiting for container to start..."
sleep 5
if docker compose ps | grep -q "translator"; then
    log "Translator container is running."
    docker compose logs --tail 30 translator || true
else
    log "WARNING: Container may not be running. Check 'docker compose logs'."
fi

# 14. Verify model presence again inside container
log "Verifying model files inside container..."
for d in whisper nllb piper; do
    if ! docker compose exec -T translator test -d "/app/models/${d}"; then
        log "WARNING: /app/models/${d} not found inside container."
    fi
done

# 15. Power supply sanity check
if dmesg | grep -qi "Undervoltage detected" 2>/dev/null; then
    log "======================================================"
    log "WARNING: Undervoltage detected in dmesg."
    log "Please use a 5V/2.5A+ power supply to avoid crashes."
    log "======================================================"
fi

log "======================================================"
log "AI Translator OS v1.0 setup complete."
log "System is set to auto-start on boot via systemd."
log "Reboot now, or run: sudo docker compose -f ${APP_DIR}/docker-compose.yml restart"
log "======================================================"
