#!/bin/bash
# Kingdom Restore Script
# Restores from an encrypted daily archive
# Usage: bash restore.sh <backup_date> <passphrase>
# Example: bash restore.sh 2025-06-23 mypassphrase

set -euo pipefail

BACKUP_DATE="${1:-}"
PASSPHRASE="${2:-}"
KINGDOM_HOME="/home/kingdom-os"
BACKUP_DIR="${KINGDOM_HOME}/backups"

if [ -z "${BACKUP_DATE}" ] || [ -z "${PASSPHRASE}" ]; then
  echo "Usage: bash restore.sh <backup_date> <passphrase>"
  echo ""
  echo "Available daily archives:"
  ls "${BACKUP_DIR}/daily/"*.tar.gz.enc 2>/dev/null || echo "No archives found"
  echo ""
  echo "Available hourly DB backups:"
  ls "${BACKUP_DIR}/hourly/"*.db 2>/dev/null | tail -5 || echo "No hourly backups found"
  exit 1
fi

ARCHIVE="${BACKUP_DIR}/daily/kingdom-daily-${BACKUP_DATE}.tar.gz.enc"
if [ ! -f "${ARCHIVE}" ]; then
  echo "Archive not found: ${ARCHIVE}"
  echo "Available:"
  ls "${BACKUP_DIR}/daily/"*.tar.gz.enc 2>/dev/null || echo "None"
  exit 1
fi

echo "=== Kingdom Restore from ${BACKUP_DATE} ==="
echo "Archive: ${ARCHIVE}"
echo ""
read -p "This will overwrite current data. Continue? (yes/no): " CONFIRM
[ "${CONFIRM}" = "yes" ] || { echo "Aborted."; exit 1; }

# Stop services
echo "Stopping services..."
sudo systemctl stop kingdom-daemon 2>/dev/null || true
sudo systemctl stop kingdom-gui 2>/dev/null || true
sudo systemctl stop kingdom-core 2>/dev/null || true
sleep 2

# Decrypt and extract
echo "Decrypting and extracting..."
RESTORE_TMP="/tmp/kingdom-restore-${BACKUP_DATE}"
mkdir -p "${RESTORE_TMP}"
openssl enc -aes-256-cbc -pbkdf2 -d \
  -in "${ARCHIVE}" \
  -pass "pass:${PASSPHRASE}" \
| tar -xzf - -C "${RESTORE_TMP}"

# Restore DB
DB_TMP="${RESTORE_TMP}/kingdom-daily-${BACKUP_DATE}.db"
if [ -f "${DB_TMP}" ]; then
  cp "${DB_TMP}" "${KINGDOM_HOME}/kingdom.db"
  echo "kingdom.db restored"
elif [ -f "${RESTORE_TMP}/kingdom.db" ]; then
  cp "${RESTORE_TMP}/kingdom.db" "${KINGDOM_HOME}/kingdom.db"
  echo "kingdom.db restored"
fi

# Restore chroma_data
if [ -d "${RESTORE_TMP}/chroma_data" ]; then
  rm -rf "${KINGDOM_HOME}/chroma_data"
  cp -r "${RESTORE_TMP}/chroma_data" "${KINGDOM_HOME}/"
  echo "chroma_data restored"
fi

# Restore config files
for f in CLAUDE.md SOUL.md USER.md AGENTS.md MEMORY.md; do
  [ -f "${RESTORE_TMP}/${f}" ] && cp "${RESTORE_TMP}/${f}" "${KINGDOM_HOME}/${f}" && echo "${f} restored"
done

# Restore scripts
if [ -d "${RESTORE_TMP}/scripts" ]; then
  cp -r "${RESTORE_TMP}/scripts" "${KINGDOM_HOME}/"
  chmod +x "${KINGDOM_HOME}/scripts/"*.sh 2>/dev/null || true
  echo "scripts restored"
fi

# Restore gui (run npm install after)
if [ -d "${RESTORE_TMP}/gui" ]; then
  cp -r "${RESTORE_TMP}/gui" "${KINGDOM_HOME}/"
  echo "gui restored (run: cd /home/kingdom-os/gui && npm install)"
fi

# Cleanup
rm -rf "${RESTORE_TMP}"

# Restart services
echo ""
echo "Restarting services..."
sudo systemctl start kingdom-core
sleep 3
sudo systemctl start kingdom-daemon
sudo systemctl start kingdom-gui 2>/dev/null || true

echo ""
echo "=== Restore Complete ==="
echo "Verify: curl http://127.0.0.1:8000/health"
sudo systemctl status kingdom-core --no-pager | head -5
