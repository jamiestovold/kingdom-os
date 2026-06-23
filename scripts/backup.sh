#!/bin/bash
# Kingdom Backup Script
# Hourly: WAL-safe SQLite backup
# Daily:  Full encrypted archive (once per day via marker file)
# Weekly: Full encrypted snapshot (Sundays only)
# Local:  Unencrypted fast access
# B2:     Encrypted archives only

set -euo pipefail

KINGDOM_HOME="/home/kingdom-os"
BACKUP_DIR="${KINGDOM_HOME}/backups"
TIMESTAMP=$(date +%Y-%m-%d-%H%M%S)
DATE=$(date +%Y-%m-%d)
DOW=$(date +%u)  # 1=Monday 7=Sunday

mkdir -p "${BACKUP_DIR}/daily" "${BACKUP_DIR}/hourly" "${BACKUP_DIR}/weekly"

LOG_FILE="${BACKUP_DIR}/backup.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"; }

# Load env
set -a
source "${KINGDOM_HOME}/.env" 2>/dev/null || true
set +a

if [ -z "${BACKUP_PASSPHRASE:-}" ]; then
  log "ERROR: BACKUP_PASSPHRASE not set in .env -- aborting"
  exit 1
fi

log "=== Kingdom Backup Started ==="

# ── Hourly: WAL-safe SQLite backup ───────────────────────────────────────────
HOURLY_DB="${BACKUP_DIR}/hourly/kingdom-${TIMESTAMP}.db"
sqlite3 "${KINGDOM_HOME}/kingdom.db" ".backup '${HOURLY_DB}'"
log "Hourly DB saved: ${HOURLY_DB}"

# Retain last 24 hourly backups
ls -t "${BACKUP_DIR}/hourly/kingdom-"*.db 2>/dev/null | tail -n +25 | xargs rm -f 2>/dev/null || true

# ── Daily: full encrypted archive (once per day only) ────────────────────────
DAILY_MARKER="${BACKUP_DIR}/daily/${DATE}/.complete"
DAILY_ENC="${BACKUP_DIR}/daily/kingdom-daily-${DATE}.tar.gz.enc"

if [ ! -f "${DAILY_MARKER}" ]; then
  log "Daily backup starting..."
  mkdir -p "${BACKUP_DIR}/daily/${DATE}"

  # WAL-safe DB copy
  DAILY_DB_TMP="/tmp/kingdom-daily-${DATE}.db"
  sqlite3 "${KINGDOM_HOME}/kingdom.db" ".backup '${DAILY_DB_TMP}'"

  # Build staging directory -- only copy files that exist
  STAGE="/tmp/kingdom-stage-${DATE}"
  rm -rf "${STAGE}"
  mkdir -p "${STAGE}"

  # Copy DB
  cp "${DAILY_DB_TMP}" "${STAGE}/"

  # Copy config files only if they exist
  for f in CLAUDE.md SOUL.md USER.md AGENTS.md MEMORY.md kingdom-philosophy.md; do
    [ -f "${KINGDOM_HOME}/${f}" ] && cp "${KINGDOM_HOME}/${f}" "${STAGE}/" || true
  done

  # Copy scripts directory
  [ -d "${KINGDOM_HOME}/scripts" ] && cp -r "${KINGDOM_HOME}/scripts" "${STAGE}/" || true

  # Copy gui (exclude node_modules and dist)
  if [ -d "${KINGDOM_HOME}/gui" ]; then
    mkdir -p "${STAGE}/gui"
    rsync -a --exclude="node_modules" --exclude="dist" "${KINGDOM_HOME}/gui/" "${STAGE}/gui/" 2>/dev/null || \
    cp -r "${KINGDOM_HOME}/gui" "${STAGE}/" || true
  fi

  # Copy chroma_data
  [ -d "${KINGDOM_HOME}/chroma_data" ] && cp -r "${KINGDOM_HOME}/chroma_data" "${STAGE}/" || true

  # Build encrypted archive from staging directory
  tar -czf - -C "${STAGE}" . \
  | openssl enc -aes-256-cbc -pbkdf2 -salt \
    -out "${DAILY_ENC}" \
    -pass "pass:${BACKUP_PASSPHRASE}"

  rm -rf "${STAGE}" "${DAILY_DB_TMP}"
  touch "${DAILY_MARKER}"
  log "Daily encrypted archive: ${DAILY_ENC}"

  # Upload to B2 (encrypted archive only)
  if command -v rclone &>/dev/null && rclone listremotes 2>/dev/null | grep -q "b2kingdom:"; then
    rclone copy "${DAILY_ENC}" b2kingdom:kingdom-backup/daily/ \
      --log-level ERROR 2>>"${LOG_FILE}" && log "B2 daily upload: OK" || log "B2 daily upload: FAILED"
  else
    log "B2 not configured -- local backup only"
  fi

  # Retain last 7 daily archives
  ls -t "${BACKUP_DIR}/daily/kingdom-daily-"*.tar.gz.enc 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null || true
  log "Daily retention: kept last 7"
else
  log "Daily backup already done today -- skipping"
fi

# Upload hourly DB to B2 encrypted only
if command -v rclone &>/dev/null && rclone listremotes 2>/dev/null | grep -q "b2kingdom:"; then
  HOURLY_ENC="/tmp/kingdom-hourly-${TIMESTAMP}.db.enc"
  openssl enc -aes-256-cbc -pbkdf2 -salt \
    -in "${HOURLY_DB}" \
    -out "${HOURLY_ENC}" \
    -pass "pass:${BACKUP_PASSPHRASE}"
  rclone copy "${HOURLY_ENC}" b2kingdom:kingdom-backup/hourly/ \
    --log-level ERROR 2>>"${LOG_FILE}" && log "B2 hourly upload: OK" || log "B2 hourly upload: FAILED"
  rm -f "${HOURLY_ENC}"
fi

# ── Weekly: full snapshot (Sundays only) ─────────────────────────────────────
if [ "${DOW}" = "7" ]; then
  WEEKLY_ENC="${BACKUP_DIR}/weekly/kingdom-week-$(date +%Y-W%V).tar.gz.enc"
  if [ ! -f "${WEEKLY_ENC}" ]; then
    log "Weekly snapshot starting..."
    tar -czf - -C "/home" \
      --exclude="kingdom-os/.venv" \
      --exclude="kingdom-os/gui/node_modules" \
      --exclude="kingdom-os/gui/dist" \
      --exclude="kingdom-os/backups" \
      kingdom-os/ \
    | openssl enc -aes-256-cbc -pbkdf2 -salt \
      -out "${WEEKLY_ENC}" \
      -pass "pass:${BACKUP_PASSPHRASE}"
    log "Weekly snapshot: ${WEEKLY_ENC}"
    if command -v rclone &>/dev/null && rclone listremotes 2>/dev/null | grep -q "b2kingdom:"; then
      rclone copy "${WEEKLY_ENC}" b2kingdom:kingdom-backup/weekly/ \
        --log-level ERROR 2>>"${LOG_FILE}" && log "B2 weekly upload: OK" || log "B2 weekly upload: FAILED"
    fi
    # Retain last 4 weekly snapshots
    ls -t "${BACKUP_DIR}/weekly/kingdom-week-"*.tar.gz.enc 2>/dev/null | tail -n +5 | xargs rm -f 2>/dev/null || true
    log "Weekly retention: kept last 4"
  fi
fi

log "=== Kingdom Backup Complete ==="
