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

# 1. OS check
if [[ "$(uname -s)" != "Linux" ]]; then
    error "This installer is for Linux/Raspberry Pi only."
fi

log "Installing AI Translator OS to ${APP_DIR}..."

# 2. Install required host packages
log "Updating package lists and installing host dependencies..."

# Stop package manager background services that may lock apt
for svc in packagekit packagekitd apt-daily apt-daily-upgrade; do
    if systemctl is-active --quiet "${svc}" 2>/dev/null; then
        log "Stopping ${svc} to free apt lock..."
        systemctl stop "${svc}" 2>/dev/null || true
    fi
done

# Force-kill any remaining package manager processes
for p in packagekitd apt-daily apt-daily-upgrade; do
    pids="$(pgrep -x "${p}" 2>/dev/null || true)"
    if [[ -n "${pids}" ]]; then
        log "Killing remaining ${p} processes..."
        kill -9 ${pids} 2>/dev/null || true
    fi
done

# Wait up to 60s for apt lists lock
for i in $(seq 1 60); do
    if [[ ! -e /var/lib/apt/lists/lock ]] || ! pgrep -x packagekitd >/dev/null 2>&1; then
        break
    fi
    log "Waiting for apt lock... ${i}s"
    sleep 1
done
sleep 2

export DEBIAN_FRONTEND=noninteractive
apt-get update -q
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
        python3 scripts/download_models.py --all --output models || \
            log "Model download script failed. Please copy models manually."
    else
        log "No network. Please copy pre-downloaded models to models/whisper, models/nllb, models/piper"
    fi
fi

# 9. Build the Docker image with platform-specific parallelism
log "Building Docker image (whisper.cpp will use -j${JOBS})..."
cd "${APP_DIR}"
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

log "======================================================"
log "AI Translator OS v1.0 setup complete."
log "System is set to auto-start on boot via systemd."
log "Reboot now, or run: sudo docker compose -f ${APP_DIR}/docker-compose.yml restart"
log "======================================================"
