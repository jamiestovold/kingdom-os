# Kingdom Core

You are building Kingdom Core, not the full Kingdom OS.

## Core Principle
The task engine is the centre of the system. Everything flows through tasks.

## Rules
- Do not add future features.
- Do not build the GUI yet.
- Do not install Ollama, Whisper, Obsidian, Telegram, or extra tools yet.
- Do not create decorative agent/skill/personality files.
- Backend must bind only to 127.0.0.1.
- Never bind services to 0.0.0.0.
- Every write action must create an audit log entry.
- Every task state change must create a git checkpoint tag.
- API routes must require token auth.
- Verification commands must be run before reporting success.
- If a step fails, stop and report. Do not skip ahead.

## Phase 1 Goal
A working local-only task engine with:
- SQLite queue
- approvals
- audit log
- git checkpoint tags
- secured FastAPI API
- systemd service

## Valid Task States
queued → running → waiting_approval → approved → completed
running → failed
No other state transitions are permitted.
