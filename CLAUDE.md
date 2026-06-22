# Kingdom Core

You are building Kingdom Core, not the full Kingdom OS.

## Core Principle
The task engine is the centre of the system. Everything flows through tasks.

## Agent Hierarchy
- Claude — architect. Deep reasoning, planning, research, analysis, general tasks.
- Codex — reviewer and tester. Independent code challenge, test writing.
- Local LLM (Qwen2.5-Coder:1.5b) — builder. Code generation, boilerplate, documentation. Not yet active.
- Script — infra tasks. Pure bash, no AI needed.

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

## Rules
- Do not add future features.
- Do not build the GUI yet.
- Do not activate automatic local LLM execution yet — Phase 3.
- Do not spawn sub-agents yet — Phase 3.
- Do not add RAG yet — Phase 4.
- Backend must bind only to 127.0.0.1. Never 0.0.0.0.
- Every write action must create an audit log entry.
- Every task state change must create a git checkpoint tag.
- API routes must require token auth except /health, /version, /agents.
- If a step fails, stop and report. Do not skip ahead.

## Current Phase
Phase 2 — Agent Routing Foundation.
Tasks can be created with task_type.
Kingdom assigns the correct agent automatically.
Agents are not yet executed automatically.

## Phase 2 Success Condition
A task created with task_type gets auto-assigned to the correct agent.
/agents shows Claude, Codex, local_llm, and script with health status.
