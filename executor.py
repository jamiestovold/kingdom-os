"""
Kingdom Core — Controlled Execution Layer

Rules:
- Nothing executes automatically. Must be triggered via API.
- All runs default to requires_approval = True.
- Output is captured and logged. Never applied automatically.
- Local LLM: mechanical tasks only, output captured, not applied.
- Script: whitelisted scripts only, no arbitrary bash.
- Claude/Codex: manual handoff only — returns prompt package for human to run.
- Task moves to waiting_approval on success.
- Task moves to failed on error or timeout.
- Never auto-transition to completed.
"""
import asyncio
import subprocess
import uuid
import time
import aiosqlite
from datetime import datetime, timezone
from db import DB_PATH, SCRIPT_WHITELIST
from engine import audit, checkpoint, transition_task


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def log_run(run_id: str, message: str, level: str = "info"):
    """Append-only run log. Never updates or deletes."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO run_logs (run_id, timestamp, level, message) VALUES (?, ?, ?, ?)",
            (run_id, now(), level, message)
        )
        await db.commit()


async def create_run(task_id: str, agent: str) -> str:
    """Create a run record. requires_approval always True."""
    run_id = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO runs (id, task_id, agent, status, requires_approval, started_at)
               VALUES (?, ?, ?, 'running', 1, ?)""",
            (run_id, task_id, agent, now())
        )
        await db.commit()
    return run_id


async def complete_run(run_id: str, output: str, error: str = None,
                       status: str = "completed", duration_ms: int = None):
    """Mark run complete with output and duration. Never applies output."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE runs
               SET status = ?, output = ?, error = ?, completed_at = ?, duration_ms = ?
               WHERE id = ?""",
            (status, output, error, now(), duration_ms, run_id)
        )
        await db.commit()


async def execute_local_llm(task: dict, run_id: str) -> str:
    """
    Execute task via local LLM (Ollama).
    Captures output only. Never writes files or applies code.
    Only handles mechanical task types: build, document.
    Raises on timeout or error — caller handles failure path.
    """
    task_type = task.get("task_type", "general")
    if task_type not in ["build", "document"]:
        raise ValueError(
            f"local_llm agent only handles build/document tasks. Got: {task_type}"
        )

    prompt = f"""You are a code generation assistant.
Task: {task['title']}
Description: {task.get('description', 'No description provided')}
Generate the requested code or documentation.
Return only the output, no explanations.
Do not include file paths or commands to apply the output."""

    await log_run(run_id, "Sending prompt to Ollama (qwen2.5-coder:1.5b)...")
    result = subprocess.run(
        ["ollama", "run", "qwen2.5-coder:1.5b", prompt, "--nowordwrap"],
        capture_output=True,
        text=True,
        timeout=120
    )
    if result.returncode != 0:
        raise RuntimeError(f"Ollama exited with code {result.returncode}: {result.stderr}")

    output = result.stdout.strip()
    await log_run(run_id, f"Local LLM responded ({len(output)} chars)")
    return output


async def execute_script(task: dict, run_id: str) -> str:
    """
    Execute a whitelisted script only.
    No arbitrary bash. No commands outside whitelist.
    Raises on timeout, error, or non-whitelisted script.
    """
    description = task.get("description", "")
    script_to_run = None
    for whitelisted in SCRIPT_WHITELIST:
        if whitelisted in description:
            script_to_run = whitelisted
            break

    if not script_to_run:
        raise ValueError(
            f"No whitelisted script found in task description. "
            f"Whitelist: {SCRIPT_WHITELIST}"
        )

    await log_run(run_id, f"Running whitelisted script: {script_to_run}")
    result = subprocess.run(
        ["bash", f"/home/kingdom-os/{script_to_run}"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd="/home/kingdom-os"
    )
    output = result.stdout + result.stderr
    await log_run(run_id, f"Script completed (exit code {result.returncode})")
    if result.returncode != 0:
        raise RuntimeError(f"Script exited with code {result.returncode}: {result.stderr}")
    return output


async def execute_claude_handoff(task: dict, run_id: str) -> str:
    """
    Claude/Codex manual handoff.
    Does not call Claude or Codex API automatically.
    Returns a structured prompt package for the human to run manually.
    """
    agent = task.get("agent", "claude")
    await log_run(run_id, f"Preparing {agent} handoff package...")

    handoff = f"""# {agent.upper()} HANDOFF PACKAGE
Generated: {now()}
Task ID: {task['id']}
Task Type: {task['task_type']}

## Task
{task['title']}

## Description
{task.get('description', 'No description provided')}

## Instructions
This task requires {agent} to handle it.
Copy the prompt below and run it manually in your {agent} session.

## Prompt for {agent.upper()}
---
Task: {task['title']}
Type: {task['task_type']}
Description: {task.get('description', 'No description')}

Please complete this task. Return your output clearly formatted.

After reviewing the output, update the task status via:
POST /tasks/{task['id']}/transition
{{"to_status": "approved", "actor": "kingdom"}}
---

## Status
This run is waiting for your manual review and approval.
Task will remain in waiting_approval until you act on it."""

    await log_run(run_id, f"Handoff package prepared for {agent}")
    return handoff


async def execute_task(task: dict) -> dict:
    """
    Main execution entry point.
    Routes to correct executor based on agent.
    On success: moves task to waiting_approval.
    On error or timeout: moves task to failed.
    requires_approval is always True.
    Never auto-transitions to completed.
    """
    task_id = task["id"]
    agent = task["agent"]
    start_time = time.monotonic()

    # Create run record
    run_id = await create_run(task_id, agent)
    await log_run(run_id, f"Run started for task: {task['title']}")
    await log_run(run_id, f"Agent: {agent}, Type: {task['task_type']}")

    # Audit
    await audit("execute_task", f"task/{task_id}", f"run={run_id} agent={agent}")

    # Transition to running
    try:
        await transition_task(task_id, "running", actor="executor")
    except ValueError as e:
        await log_run(run_id, f"Cannot transition to running: {e}", "error")
        duration_ms = int((time.monotonic() - start_time) * 1000)
        await complete_run(run_id, "", str(e), "failed", duration_ms)
        return {"run_id": run_id, "status": "failed", "error": str(e)}

    # Execute based on agent — errors go to failed path
    try:
        if agent == "local_llm":
            output = await execute_local_llm(task, run_id)
        elif agent == "script":
            output = await execute_script(task, run_id)
        elif agent in ["claude", "codex"]:
            output = await execute_claude_handoff(task, run_id)
        else:
            raise ValueError(f"Unknown agent: {agent}")

        duration_ms = int((time.monotonic() - start_time) * 1000)
        await complete_run(run_id, output, status="completed", duration_ms=duration_ms)
        await log_run(run_id, f"Run complete in {duration_ms}ms. Output captured. Awaiting approval.")

        # Success: move to waiting_approval
        # transition_task already creates a checkpoint — no manual checkpoint needed here
        await transition_task(task_id, "waiting_approval", actor="executor")

        return {
            "run_id": run_id,
            "status": "completed",
            "requires_approval": True,
            "duration_ms": duration_ms,
            "output": output,
            "task_status": "waiting_approval"
        }

    except subprocess.TimeoutExpired as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        error_msg = f"Timeout after {duration_ms}ms"
        await log_run(run_id, error_msg, "error")
        await complete_run(run_id, "", error_msg, "failed", duration_ms)
        try:
            await transition_task(task_id, "failed", actor="executor")
        except Exception:
            pass
        return {"run_id": run_id, "status": "failed", "error": error_msg, "duration_ms": duration_ms}

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        error_msg = str(e)
        await log_run(run_id, f"Execution error: {error_msg}", "error")
        await complete_run(run_id, "", error_msg, "failed", duration_ms)
        try:
            await transition_task(task_id, "failed", actor="executor")
        except Exception:
            pass
        return {"run_id": run_id, "status": "failed", "error": error_msg, "duration_ms": duration_ms}


async def get_run(run_id: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise ValueError(f"Run {run_id} not found")
            return dict(row)


async def get_run_logs(run_id: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM run_logs WHERE run_id = ? ORDER BY timestamp ASC",
            (run_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def list_runs(task_id: str = None) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if task_id:
            async with db.execute(
                "SELECT * FROM runs WHERE task_id = ? ORDER BY started_at DESC",
                (task_id,)
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT 50"
            ) as cursor:
                rows = await cursor.fetchall()
        return [dict(r) for r in rows]
