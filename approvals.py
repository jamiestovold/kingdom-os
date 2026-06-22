"""
Kingdom Core -- Approval Layer

Rules:
- approve: waiting_approval -> approved. Logs actor and timestamp.
- reject: waiting_approval -> failed. Requires reason. Logs everything.
- complete: approved -> completed. Explicit human action only. Never automatic.
- Output is never applied to files by any approval action.
- Every decision is in the audit log.
"""
import aiosqlite
from datetime import datetime, timezone
from db import DB_PATH
from engine import audit, transition_task


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def record_approval(run_id, task_id, decision, actor, reason=None):
    """Append-only approval record. Never updates or deletes."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO approvals (run_id, task_id, decision, actor, reason, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (run_id, task_id, decision, actor, reason, now())
        )
        await db.commit()


async def get_run_for_approval(run_id):
    """Fetch run and its task. Validates task is in waiting_approval state."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)) as cursor:
            run = await cursor.fetchone()
        if not run:
            raise ValueError(f"Run {run_id} not found")
        run = dict(run)
        async with db.execute("SELECT * FROM tasks WHERE id = ?", (run["task_id"],)) as cursor:
            task = await cursor.fetchone()
        if not task:
            raise ValueError(f"Task {run['task_id']} not found")
        task = dict(task)
        if task["status"] != "waiting_approval":
            raise ValueError(
                f"Task must be in waiting_approval to approve or reject. "
                f"Current status: {task['status']}"
            )
        return {"run": run, "task": task}


async def approve_run(run_id, actor, note=None):
    """
    Approve a run.
    Records approval with actor and timestamp.
    Transitions task: waiting_approval -> approved.
    Does not apply output to files.
    Does not transition to completed -- that requires explicit /tasks/{id}/complete call.
    """
    data = await get_run_for_approval(run_id)
    task = data["task"]
    task_id = task["id"]

    await record_approval(run_id, task_id, "approved", actor, note)
    await transition_task(task_id, "approved", actor=actor)
    await audit("approve_run", f"task/{task_id}", f"run={run_id} actor={actor} note={note}")

    return {
        "run_id": run_id,
        "task_id": task_id,
        "decision": "approved",
        "actor": actor,
        "task_status": "approved",
        "note": note,
        "message": "Run approved. Call POST /tasks/{id}/complete to mark task completed."
    }


async def reject_run(run_id, actor, reason):
    """
    Reject a run.
    Reason is required.
    Transitions task: waiting_approval -> failed.
    To retry: create a new task.
    """
    if not reason or not reason.strip():
        raise ValueError("Rejection reason is required. Provide a reason.")

    data = await get_run_for_approval(run_id)
    task = data["task"]
    task_id = task["id"]

    await record_approval(run_id, task_id, "rejected", actor, reason)
    await transition_task(task_id, "failed", actor=actor)
    await audit("reject_run", f"task/{task_id}", f"run={run_id} actor={actor} reason={reason}")

    return {
        "run_id": run_id,
        "task_id": task_id,
        "decision": "rejected",
        "actor": actor,
        "reason": reason,
        "task_status": "failed",
        "message": "Run rejected. Task moved to failed. Create a new task to retry."
    }


async def complete_task(task_id, actor):
    """
    Mark an approved task as completed.
    Explicit human action only -- never automatic.
    Task must be in approved state.
    Records completion in approvals table for full audit trail.
    Does not apply output to files.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as cursor:
            task = await cursor.fetchone()
        if not task:
            raise ValueError(f"Task {task_id} not found")
        task = dict(task)

    if task["status"] != "approved":
        raise ValueError(
            f"Task must be in approved state to complete. "
            f"Current status: {task['status']}"
        )

    # Get the run_id for this task to record in approvals
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id FROM runs WHERE task_id = ? ORDER BY started_at DESC LIMIT 1",
            (task_id,)
        ) as cursor:
            run_row = await cursor.fetchone()

    if not run_row:
        raise ValueError(
            f"No run found for task {task_id}. Cannot complete a task with no execution record."
        )
    run_id = dict(run_row)["id"]

    await transition_task(task_id, "completed", actor=actor)
    await record_approval(run_id, task_id, "completed", actor, "Task marked complete by human")
    await audit("complete_task", f"task/{task_id}", f"actor={actor}")

    return {
        "task_id": task_id,
        "task_status": "completed",
        "actor": actor,
        "message": "Task completed. Output was reviewed and approved by a human."
    }


async def get_approvals(task_id=None, run_id=None):
    """Get approval history for a task or run."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if task_id:
            async with db.execute(
                "SELECT * FROM approvals WHERE task_id = ? ORDER BY timestamp ASC",
                (task_id,)
            ) as cursor:
                rows = await cursor.fetchall()
        elif run_id:
            async with db.execute(
                "SELECT * FROM approvals WHERE run_id = ? ORDER BY timestamp ASC",
                (run_id,)
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute(
                "SELECT * FROM approvals ORDER BY timestamp DESC LIMIT 50"
            ) as cursor:
                rows = await cursor.fetchall()
        return [dict(r) for r in rows]
