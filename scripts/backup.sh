#!/bin/bash
# AI Translator OS v1.0 — Backup config, data, dictionary, language packs
set -euo pipefail

APP_DIR="/opt/translator"
BACKUP_DIR="${APP_DIR}/backups"

usage() {
    cat <<'EOF'
Usage: sudo ./scripts/backup.sh [output_dir]

Default backup dir: /opt/translator/backups
EOF
}

do_backup() {
    local outdir="${1:-${BACKUP_DIR}}"
    local ts="$(date +%Y%m%d-%H%M%S)"
    local archive="${outdir}/translator-${ts}.tar.gz"

    mkdir -p "${outdir}"
    mkdir -p "${APP_DIR}/logs" "${APP_DIR}/data"

    local items=()
    [[ -d "${APP_DIR}/config" ]] && items+=("${APP_DIR}/config")
    [[ -f "${APP_DIR}/data/dictionary.json" ]] && items+=("${APP_DIR}/data/dictionary.json")
    [[ -d "${APP_DIR}/data/language_packs" ]] && items+=("${APP_DIR}/data/language_packs")
    [[ -f "${APP_DIR}/data/history.jsonl" ]] && items+=("${APP_DIR}/data/history.jsonl")
    [[ -d "${APP_DIR}/data/history" ]] && items+=("${APP_DIR}/data/history")

    if [[ ${#items[@]} -eq 0 ]]; then
        echo "[backup] Nothing to backup" >&2
        exit 1
    fi

    tar -czf "${archive}" -C / "${items[@]/#\//}"
    echo "[backup] Created: ${archive}"
    ls -lh "${archive}"
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

do_backup "${1:-${BACKUP_DIR}}"
