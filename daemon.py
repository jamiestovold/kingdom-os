"""
Kingdom Core -- Queue Daemon (Phase 5)

Design:
- Single worker
- 10 second poll interval
- 15 minute stuck task timeout
- 12 tasks per hour maximum
- No auto-approval, no auto-completion
- No parallel execution
- No automatic Claude/Codex API calls
- All significant events written to audit_log with daemon_ prefix
- execute_task() handles queued->running transition -- daemon does not
- Recovery uses timeout logic on restart, not blanket failure
- No audit log spam while paused
"""
import asyncio
import aiosqlite
import signal
import sys
from datetime import datetime, timezone, timedelta
from db import DB_PATH
from engine import audit, transition_task
from executor import execute_task

# -- Configuration ------------------------------------------------------------
POLL_INTERVAL_SECONDS = 10
RUNNING_TIMEOUT_SECONDS = 900   # 15 minutes
MAX_TASKS_PER_HOUR = 12
WORKER_COUNT = 1                # single worker only

# -- Utilities ----------------------------------------------------------------
def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def now_dt() -> datetime:
    return datetime.now(timezone.utc)

# -- Daemon State -------------------------------------------------------------
async def get_daemon_state() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM daemon_state WHERE id = 1") as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else {}

async def update_daemon_state(**kwargs):
    kwargs["updated_at"] = now()
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE daemon_state SET {fields} WHERE id = 1",
            values
        )
        await db.commit()

async def is_paused() -> bool:
    state = await get_daemon_state()
    return bool(state.get("paused", 0))

async def check_hourly_limit() -> bool:
    """Returns True if hourly limit has been reached."""
    state = await get_daemon_state()
    tasks_run = state.get("tasks_run_this_hour", 0)
    window_start_str = state.get("hour_window_start")
    if not window_start_str:
        await update_daemon_state(
            tasks_run_this_hour=0,
            hour_window_start=now()
        )
        return False
    window_start = datetime.fromisoformat(window_start_str)
    if now_dt() - window_start > timedelta(hours=1):
        await update_daemon_state(
            tasks_run_this_hour=0,
            hour_window_start=now()
        )
        return False
    return tasks_run >= MAX_TASKS_PER_HOUR

async def increment_hourly_count():
    state = await get_daemon_state()
    current = state.get("tasks_run_this_hour", 0)
    await update_daemon_state(tasks_run_this_hour=current + 1)

# -- Recovery -----------------------------------------------------------------
async def recover_stuck_tasks():
    """
    Find running tasks older than timeout and move to failed.
    Uses timeout logic only -- does NOT fail all running tasks on startup.
    Graceful recovery after reboots: tasks running for less than timeout are left alone.
    """
    cutoff = (now_dt() - timedelta(seconds=RUNNING_TIMEOUT_SECONDS)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT t.id, t.title, r.id as run_id, r.started_at
               FROM tasks t
               LEFT JOIN runs r ON r.task_id = t.id
               WHERE t.status = 'running'
               AND r.started_at < ?
               ORDER BY r.started_at ASC""",
            (cutoff,)
        ) as cursor:
            stuck = await cursor.fetchall()
        stuck = [dict(r) for r in stuck]

    for row in stuck:
        task_id = row["id"]
        run_id = row.get("run_id")
        reason = f"Daemon timeout: task exceeded {RUNNING_TIMEOUT_SECONDS} seconds"
        await audit("daemon_timeout", f"task/{task_id}", reason)
        if run_id:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT INTO run_logs (run_id, timestamp, level, message) VALUES (?, ?, ?, ?)",
                    (run_id, now(), "error", reason)
                )
                await db.execute(
                    "UPDATE runs SET status = 'failed', error = ?, completed_at = ? WHERE id = ?",
                    (reason, now(), run_id)
                )
                await db.commit()
        try:
            await transition_task(task_id, "failed", actor="daemon_timeout")
        except ValueError:
            pass  # Already moved, ignore
        await audit("daemon_recovery", f"task/{task_id}", "stuck task moved to failed after timeout")

# -- Task Fetching ------------------------------------------------------------
async def get_next_queued_task() -> dict | None:
    """
    Fetch the oldest queued task without transitioning it.
    execute_task() handles the queued -> running transition.
    Do not add transition logic here.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tasks WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None

# -- Main Loop ----------------------------------------------------------------
async def daemon_loop():
    await audit("daemon_started", "daemon",
        f"poll={POLL_INTERVAL_SECONDS}s timeout={RUNNING_TIMEOUT_SECONDS}s limit={MAX_TASKS_PER_HOUR}/hr workers={WORKER_COUNT}")
    await update_daemon_state(started_at=now())

    _was_paused = False
    while True:
        try:
            await update_daemon_state(last_poll=now())

            # Check paused flag -- no audit spam while paused
            if await is_paused():
                if not _was_paused:
                    # Only log the transition into paused state, not every poll
                    await audit("daemon_paused_poll", "daemon", "daemon is paused, skipping processing")
                    _was_paused = True
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
                continue

            # If we just resumed, log it
            if _was_paused:
                await audit("daemon_resumed_poll", "daemon", "daemon resumed processing")
                _was_paused = False

            # Recover stuck tasks (timeout-based, not blanket)
            await recover_stuck_tasks()

            # Check hourly rate limit
            if await check_hourly_limit():
                await audit("daemon_rate_limit", "daemon",
                    f"hourly limit of {MAX_TASKS_PER_HOUR} reached -- waiting")
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
                continue

            # Fetch next queued task
            # execute_task() handles the queued -> running transition
            task = await get_next_queued_task()
            if not task:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
                continue

            # Execute via existing Phase 3 executor
            # execute_task() transitions queued -> running internally
            await audit("daemon_executing", f"task/{task['id']}",
                f"agent={task['agent']} type={task['task_type']}")
            result = await execute_task(task)
            await audit("daemon_execution_complete", f"task/{task['id']}",
                f"run={result.get('run_id')} status={result.get('status')} task_status={result.get('task_status')}")

            # Increment hourly counter
            await increment_hourly_count()

            # Single task per loop
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

        except asyncio.CancelledError:
            await audit("daemon_shutdown", "daemon", "received cancellation signal")
            break
        except Exception as e:
            await audit("daemon_error", "daemon", f"unhandled error: {str(e)}")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

# -- Entry Point --------------------------------------------------------------
def handle_signal(sig, frame):
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    asyncio.run(daemon_loop())
