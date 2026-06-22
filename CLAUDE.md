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
running -> failed (error or timeout)

## Approval Rules -- Phase 4
- approve: waiting_approval -> approved. Actor and timestamp required.
- complete: approved -> completed. Explicit human action only. Never automatic.
- reject: waiting_approval -> failed. Reason required.
- Retry: create a new task. Do not reset task state.
- Output is never applied to files by any approval action.
- Every decision is in the audit log.
- Rejection without reason is not permitted.

## Rules
- Do not add a daemon yet -- Phase 5.
- Do not add RAG yet -- Phase 6.
- Do not build the GUI yet -- Phase 7.
- Do not replace existing schema -- only add to it.
- Do not use execute_fetchone -- use async with db.execute() as cursor pattern.
- Backend must bind only to 127.0.0.1. Never 0.0.0.0.
- Every write action must create an audit log entry.
- Every task state change must create a git checkpoint tag.
- Never commit or push before final verification passes.

## Current Phase
Phase 4 -- Approval Layer.

## Phase 4 Success Condition
POST /runs/{id}/approve -> logs approval -> task moves to approved.
POST /tasks/{id}/complete -> logs completion -> task moves to completed.
POST /runs/{id}/reject -> logs rejection with reason -> task moves to failed.
All decisions recorded in approvals table with actor and timestamp.
Rejection without reason is blocked.
No output applied to files.
