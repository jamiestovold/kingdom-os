# Kingdom Core — Deferred Items

Items deliberately deferred until Kingdom Core is complete and verified.
These are not abandoned — they are scheduled for after the core build is stable.

---

## Offsite Backup (Deferred)

**Status:** Deferred — local backup and git checkpoints are active.
**Reason:** Deferred to avoid blocking the Phase build sequence.
**Architecture is ready:** `scripts/backup.sh` already supports B2 upload.
**When to implement:** After Phase 7 (GUI) is complete and verified.

### Deferred items

- **Backblaze B2 bucket** — create `kingdom-backup` bucket at backblaze.com
- **rclone configuration** — `rclone config` → new remote → `b2kingdom` → Backblaze B2
- **Automated offsite backup** — `backup.sh` already uploads to B2 when `b2kingdom:` remote is present; just needs rclone configured
- **Offsite restore testing** — decrypt daily archive from B2 on a fresh VPS and verify DB integrity

### How to activate when ready

```bash
# 1. Install rclone (already installed)
rclone --version

# 2. Configure B2 remote
rclone config
# n -> new remote -> name: b2kingdom -> Backblaze B2 -> enter keyID + applicationKey

# 3. Test write
echo "test-$(date +%s)" > /tmp/b2test.txt
rclone copy /tmp/b2test.txt b2kingdom:kingdom-backup/
rclone ls b2kingdom:kingdom-backup/ | grep test && echo "B2 write PASS"
rclone deletefile b2kingdom:kingdom-backup/b2test.txt
rm /tmp/b2test.txt

# 4. Run first full backup (will auto-upload to B2)
bash /home/kingdom-os/scripts/backup.sh

# 5. Verify B2 contents
rclone ls b2kingdom:kingdom-backup/
```

### What is already in place

- `scripts/backup.sh` — hourly WAL-safe DB, daily encrypted archive, weekly snapshot, B2 upload when configured
- `scripts/restore.sh` — decrypt and restore from daily archive
- `BACKUP_PASSPHRASE` — set in `.env` and stored externally
- Hourly cron job installed (`crontab -l | grep backup`)
- Local backups running (`backups/hourly/`, `backups/daily/`)
- AES-256-CBC + pbkdf2 encryption on all archives

---

## Other Deferred Items

None currently. This file will be updated as items are identified.

---

*Last updated: Phase 6.5*
