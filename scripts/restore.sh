#!/bin/bash
# AI Translator OS v1.0 — Restore from a backup archive
set -euo pipefail

APP_DIR="/opt/translator"
BACKUP_DIR="${APP_DIR}/backups"

usage() {
    cat <<'EOF'
Usage: sudo ./scripts/restore.sh [archive_path]

If no archive is given, the latest backup in /opt/translator/backups is used.
EOF
}

list_backups() {
    find "${BACKUP_DIR}" -maxdepth 1 -name "translator-*.tar.gz" -type f -printf '%T@ %p\n' 2>/dev/null | sort -rn | cut -d' ' -f2-
}

select_archive() {
    local backups
    backups="$(list_backups)"
    if [[ -z "${backups}" ]]; then
        echo "[restore] No backup archives found in ${BACKUP_DIR}" >&2
        exit 1
    fi
    local count=1
    echo "[restore] Available backups:"
    while IFS= read -r b; do
        echo "  [${count}] $(basename "${b}")"
        count=$((count + 1))
    done <<< "${backups}"
    echo -n "[restore] Select backup number: "
    read -r choice
    local selected="$(sed -n "${choice}p" <<< "${backups}")"
    if [[ -z "${selected}" ]]; then
        echo "[restore] Invalid selection" >&2
        exit 1
    fi
    echo "${selected}"
}

do_restore() {
    local archive="$1"
    if [[ ! -f "${archive}" ]]; then
        echo "[restore] Archive not found: ${archive}" >&2
        exit 1
    fi

    echo "[restore] Restoring from: ${archive}"
    tar -xzf "${archive}" -C / || {
        echo "[restore] Extraction failed" >&2
        exit 1
    }

    chown -R "${SUDO_USER:-${USER}}:${SUDO_USER:-${USER}}" "${APP_DIR}/config" "${APP_DIR}/data" 2>/dev/null || true
    echo "[restore] Done"
    echo "[restore] Run: sudo ./scripts/setup.sh restart"
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

ARCHIVE="${1:-}"
if [[ -z "${ARCHIVE}" ]]; then
    ARCHIVE="$(select_archive)"
fi
do_restore "${ARCHIVE}"
