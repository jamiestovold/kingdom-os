# Kingdom Core

You are building Kingdom Core, not the full Kingdom OS.

## Core Principle
The task engine is the centre of the system. Everything flows through tasks.

## Agent Hierarchy
- Claude — architect. Deep reasoning, planning, research, analysis, general tasks.
- Codex — reviewer and tester. Independent code challenge, test writing.
- Local LLM (Qwen2.5-Coder:1.5b) — builder. Code generation, boilerplate, documentation.
- Script — infra tasks. Pure bash, whitelisted scripts only.

## Routing Rules
- architecture → claude
- review → codex
- research → claude
- analysis → claude
- build → local_llm
- test → codex
- document → local_llm
- infra → script
- general → claude

## Execution Rules — Phase 3
- Nothing executes automatically. User or API must trigger every run.
- All runs default to requires_approval = True.
- Output is captured and logged. Never applied to files automatically.
- Local LLM: build and document tasks only. Output captured, not applied.
- Script: whitelisted scripts only. No arbitrary bash.
- Claude/Codex: manual handoff package only. Never called automatically.
- Task moves to waiting_approval on success. Never to completed automatically.
- Task moves to failed on error or timeout. Not waiting_approval.

## Rules
- Do not replace existing schema — only add to it.
- Do not use execute_fetchone — use async with db.execute() as cursor pattern.
- Do not add duplicate checkpoints — transition_task already creates them.
- Do not add a background daemon yet — Phase 4.
- Do not add RAG yet — Phase 5.
- Do not build the GUI yet — Phase 6.
- Backend must bind only to 127.0.0.1. Never 0.0.0.0.
- Every write action must create an audit log entry.
- Every task state change must create a git checkpoint tag.
- API routes must require token auth except /health, /version, /agents.
- If a step fails, stop and report. Do not skip ahead.
- Never commit or push before final verification passes.

## Current Phase
Phase 3 — Controlled Execution Layer.

## Phase 3 Success Condition
POST /tasks/{id}/run triggers correct agent.
Output captured in runs table with duration_ms.
Logs written to run_logs table.
Task moves to waiting_approval on success.
Task moves to failed on error/timeout.
requires_approval = True on all runs.
