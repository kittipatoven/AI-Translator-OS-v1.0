#!/bin/bash
# AI Translator OS v1.0 — Doctor / diagnostic tool
set -euo pipefail

APP_DIR="/opt/translator"
CONFIG_PATH="${APP_DIR}/config/config.json"

check() {
    local label="$1"
    local status="$2"
    local message="${3:-}"
    if [[ "${status}" == "OK" ]]; then
        printf "[OK]   %-24s %s\n" "${label}" "${message}"
    elif [[ "${status}" == "WARN" ]]; then
        printf "[WARN] %-24s %s\n" "${label}" "${message}" >&2
    else
        printf "[FAIL] %-24s %s\n" "${label}" "${message}" >&2
    fi
}

print_header() {
    echo ""
    echo "AI TRANSLATOR DOCTOR"
    echo "--------------------"
}

check_os() {
    local name=""
    if [[ -f /etc/os-release ]]; then
        name="$(source /etc/os-release; echo "${NAME:-} ${VERSION_ID:-}")"
    fi
    if [[ -f /etc/os-release ]] && (source /etc/os-release; [[ "${ID_LIKE:-}" == *"debian"* || "${ID:-}" == "raspbian" || "${ID:-}" == "debian" ]]); then
        check "OS" "OK" "${name}"
    else
        check "OS" "WARN" "Not Debian-based (${name})"
    fi
}

check_arch() {
    local arch="$(uname -m 2>/dev/null || echo unknown)"
    if [[ "${arch}" == "aarch64" ]]; then
        check "Arch" "OK" "${arch}"
    else
        check "Arch" "FAIL" "${arch} (need aarch64)"
    fi
}

check_pi_model() {
    local model=""
    if [[ -f /sys/firmware/devicetree/base/model ]]; then
        model="$(tr -d '\0' < /sys/firmware/devicetree/base/model)"
    elif [[ -f /proc/cpuinfo ]]; then
        model="$(grep -m1 "Model" /proc/cpuinfo 2>/dev/null | cut -d: -f2- | sed 's/^ *//')"
    fi
    if [[ -n "${model}" ]]; then
        check "Pi Model" "OK" "${model}"
    else
        check "Pi Model" "WARN" "Could not detect"
    fi
}

check_ram() {
    local total_kb mem_avail
    total_kb="$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)"
    mem_avail="$(awk '/MemAvailable/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)"
    local total_mb=$((total_kb / 1024))
    local avail_mb=$((mem_avail / 1024))
    if [[ ${total_mb} -lt 512 ]]; then
        check "RAM" "FAIL" "${total_mb} MB total"
    elif [[ ${total_mb} -lt 1024 ]]; then
        check "RAM" "WARN" "${total_mb} MB total, ${avail_mb} MB available"
    else
        check "RAM" "OK" "${total_mb} MB total, ${avail_mb} MB available"
    fi
}

check_swap() {
    local swap_total="$(free -m 2>/dev/null | awk '/^Swap:/ {print $2}' || echo 0)"
    if [[ "${swap_total}" == "0" ]]; then
        check "Swap" "WARN" "No swap"
    else
        check "Swap" "OK" "${swap_total} MB"
    fi
}

check_disk() {
    local avail_gb avail_pct
    if command -v df &>/dev/null; then
        avail_gb="$(df -BG "${APP_DIR}" 2>/dev/null | tail -1 | awk '{print $4}' | tr -d 'G' || echo 0)"
        avail_pct="$(df "${APP_DIR}" 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%' || echo 0)"
    else
        avail_gb=0; avail_pct=0
    fi
    if [[ ${avail_gb} -lt 5 ]]; then
        check "Disk" "WARN" "${avail_gb} GB available at ${APP_DIR}"
    else
        check "Disk" "OK" "${avail_gb} GB available (${avail_pct}% used)"
    fi
}

check_temp() {
    local temp=""
    if command -v vcgencmd &>/dev/null; then
        temp="$(vcgencmd measure_temp 2>/dev/null | cut -d= -f2 | cut -d"'" -f1)"
    fi
    if [[ -z "${temp}" ]]; then
        check "Temperature" "WARN" "vcgencmd not available"
        return
    fi
    local tnum="${temp%%.*}"
    if [[ -z "${tnum}" ]]; then tnum=0; fi
    if [[ ${tnum} -ge 85 ]]; then
        check "Temperature" "WARN" "${temp}°C (throttling likely)"
    elif [[ ${tnum} -ge 80 ]]; then
        check "Temperature" "WARN" "${temp}°C (hot)"
    else
        check "Temperature" "OK" "${temp}°C"
    fi
}

check_throttle() {
    local throttled=""
    if command -v vcgencmd &>/dev/null; then
        throttled="$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)"
    fi
    if [[ -z "${throttled}" ]]; then
        check "Throttling" "WARN" "vcgencmd not available"
        return
    fi
    local msg=""
    case "${throttled}" in
        0x0|0x0*) msg="OK (${throttled})" ;;
        0x50000) msg="Under-voltage now & previously (${throttled})" ;;
        0x20000) msg="Under-voltage now (${throttled})" ;;
        0x80000) msg="Throttled now (${throttled})" ;;
        0x40000) msg="Throttled previously (${throttled})" ;;
        *) msg="Check value: ${throttled}" ;;
    esac
    if [[ "${throttled}" == "0x0" || "${throttled}" == "0x0"* ]]; then
        check "Throttling" "OK" "${msg}"
    else
        check "Throttling" "WARN" "${msg}"
    fi
}

check_i2c() {
    if lsmod 2>/dev/null | grep -q "i2c_dev" || [[ -c /dev/i2c-1 ]]; then
        check "I2C" "OK" "Enabled"
    else
        check "I2C" "WARN" "Not enabled"
    fi
}

check_lcd() {
    local addr=""
    if command -v i2cdetect &>/dev/null && [[ -c /dev/i2c-1 ]]; then
        addr="$(i2cdetect -y 1 2>/dev/null | grep -E "(27|3F)" | awk '{print $NF}')" || true
    fi
    if [[ -n "${addr}" ]]; then
        check "LCD" "OK" "Detected at 0x${addr}"
    else
        check "LCD" "WARN" "Not detected (will use web fallback)"
    fi
}

check_audio() {
    local mic_out spk_out
    if command -v arecord &>/dev/null; then
        mic_out="$(arecord -l 2>/dev/null | grep -c "card" || echo 0)"
    else
        mic_out=0
    fi
    if command -v aplay &>/dev/null; then
        spk_out="$(aplay -l 2>/dev/null | grep -c "card" || echo 0)"
    else
        spk_out=0
    fi
    if [[ ${mic_out} -gt 0 && ${spk_out} -gt 0 ]]; then
        check "Audio" "OK" "Mic(s): ${mic_out}, Speaker(s): ${spk_out}"
    else
        check "Audio" "WARN" "Mic: ${mic_out}, Speaker: ${spk_out}"
    fi
}

check_buttons() {
    if [[ -c /dev/gpiomem || -c /dev/gpiochip0 ]]; then
        check "Buttons" "OK" "GPIO device present"
    else
        check "Buttons" "WARN" "No GPIO device (use web buttons)"
    fi
}

check_docker() {
    if command -v docker &>/dev/null && systemctl is-active --quiet docker 2>/dev/null; then
        check "Docker" "OK" "Running"
    elif command -v docker &>/dev/null; then
        check "Docker" "WARN" "Installed but not running"
    else
        check "Docker" "FAIL" "Not installed"
    fi
}

check_container() {
    if command -v docker &>/dev/null; then
        if docker compose -f "${APP_DIR}/docker-compose.yml" ps 2>/dev/null | grep -q "translator"; then
            check "Container" "OK" "translator running"
        else
            check "Container" "WARN" "translator not running"
        fi
    else
        check "Container" "WARN" "Docker not available"
    fi
}

check_models() {
    local missing=0
    for d in whisper nllb piper; do
        if [[ -z "$(ls -A "${APP_DIR}/models/${d}" 2>/dev/null)" ]]; then
            missing=$((missing + 1))
        fi
    done
    if [[ ${missing} -eq 0 ]]; then
        check "Models" "OK" "Whisper, NLLB, Piper present"
    else
        check "Models" "WARN" "${missing} model directories empty"
    fi
}

check_api() {
    local code
    if command -v curl &>/dev/null; then
        code="$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/health 2>/dev/null || echo 000)"
    else
        code="000"
    fi
    if [[ "${code}" == "200" ]]; then
        check "API" "OK" "http://localhost:8080/api/health -> 200"
    else
        check "API" "WARN" "HTTP ${code}"
    fi
}

check_logs() {
    if [[ -d "${APP_DIR}/logs" ]]; then
        local newest=""
        newest="$(ls -1t "${APP_DIR}/logs" 2>/dev/null | head -1 || echo "")"
        if [[ -n "${newest}" ]]; then
            check "Logs" "OK" "${newest}"
        else
            check "Logs" "WARN" "No log files"
        fi
    else
        check "Logs" "WARN" "Missing logs directory"
    fi
}

main() {
    print_header
    check_os
    check_arch
    check_pi_model
    check_ram
    check_swap
    check_disk
    check_temp
    check_throttle
    check_i2c
    check_lcd
    check_audio
    check_buttons
    check_docker
    check_container
    check_models
    check_api
    check_logs
    echo ""
}

main "$@"
