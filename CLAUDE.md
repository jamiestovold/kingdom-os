# Kingdom Core

You are building Kingdom Core, not the full Kingdom OS.

## Core Principle
The task engine is the centre of the system. Everything flows through tasks.

## Agent Hierarchy
- Claude -- architect. Deep reasoning, planning, research, analysis, general tasks.
- Codex -- reviewer and tester. Independent code challenge, test writing.
- Local LLM (Qwen2.5-Coder:1.5b) -- builder. Code generation, boilerplate, documentation.
- Script -- infra tasks. Pure bash, whitelisted scripts only.

## Routing Rules
- architecture -> claude
- review -> codex
- research -> claude
- analysis -> claude
- build -> local_llm
- test -> codex
- document -> local_llm
- infra -> script
- general -> claude

## Task Lifecycle
queued -> running -> waiting_approval -> approved -> completed
waiting_approval -> failed (rejection)
running -> failed (error, timeout, or daemon timeout)

## Approval Rules
- approve: waiting_approval -> approved. Actor and timestamp required.
- complete: approved -> completed. Explicit human action only. Never automatic.
- reject: waiting_approval -> failed. Reason required.
- Retry: create a new task. Do not reset task state.

## Daemon Rules -- Phase 5
- Single worker only. worker_count = 1.
- Poll interval: 10 seconds.
- Stuck task timeout: 900 seconds (15 minutes).
- Max tasks per hour: 12.
- No auto-approval. No auto-completion.
- No parallel execution.
- No automatic Claude or Codex API calls.
- No retries.
- execute_task() handles queued->running transition. Daemon does not.
- Recovery uses timeout logic on restart, not blanket failure.
- Daemon events written to audit_log with daemon_ prefix for significant events only.
- No audit log spam while paused.
- API controls paused flag only. systemd controls process lifecycle.

## Rules
- Do not add RAG yet -- Phase 6.
- Do not build the GUI yet -- Phase 7.
- Do not replace existing schema -- only add to it.
- Do not use execute_fetchone -- use async with db.execute() as cursor pattern.
- Backend must bind only to 127.0.0.1. Never 0.0.0.0.
- Every write action must create an audit log entry.
- Every task state change must create a git checkpoint tag.
- Never commit or push before final verification passes.

## Current Phase
Phase 5 -- Controlled Queue Daemon.

## Phase 5 Success Condition
Daemon picks up queued tasks automatically.
Tasks processed one at a time via execute_task().
Tasks stop at waiting_approval -- no auto-approval.
Pause/resume works via API.
Daemon events visible in audit_log.
No task auto-completed by daemon.

## Knowledge Layer Rules -- Phase 6
- RAG is read-only context. Never changes task state.
- Never auto-indexes. Ingestion is always a deliberate action.
- Excluded from indexing: .git, .venv, __pycache__, *.db, *.db-wal, *.db-shm, .env, *.log, *.pyc
- Retrieval limit: top 5 chunks max.
- Max context added to handoff: 5,000 characters hard cap.
- Chroma data directory excluded from git.
- Rebuild endpoint intentionally omitted in Phase 6. Rebuild requires locking and will be added later.
- No daemon auto-indexing yet -- Phase 7 or later.

## Backup Rules -- Phase 6.5
- Hourly: WAL-safe SQLite backup via sqlite3 .backup command.
- Daily: Full encrypted archive -- runs once per day via marker file.
- Weekly: Full encrypted snapshot -- Sundays only.
- Local backups: unencrypted, fast access.
- B2 uploads: encrypted with AES-256 before leaving VPS.
- BACKUP_PASSPHRASE is in .env and in password manager -- never log or expose it.
- Recovery target: under 30 minutes on a fresh VPS.
- Run backup: bash scripts/backup.sh
- Run restore: bash scripts/restore.sh <date> <passphrase>
- backups/, *.enc, rclone.conf are in .gitignore -- never commit them.
