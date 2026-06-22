import aiosqlite
import uuid
from datetime import datetime, timezone
from db import DB_PATH, VALID_TRANSITIONS
from routing import assign_agent
import subprocess
import os


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def audit(action: str, resource: str, details: str = None):
    """Append-only audit log. Never updates or deletes."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO audit_log (timestamp, action, resource, details) VALUES (?, ?, ?, ?)",
            (now(), action, resource, details)
        )
        await db.commit()


def checkpoint(task_id: str, event: str):
    """Create a git tag checkpoint for every task state change."""
    tag = f"checkpoint/{task_id[:8]}/{event}/{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    try:
        subprocess.run(
            ["git", "-C", "/home/kingdom-os", "tag", tag],
            capture_output=True, check=True
        )
    except subprocess.CalledProcessError:
        pass  # Checkpoint failure is logged but never blocks execution


async def create_task(
    title: str,
    description: str = None,
    owner: str = None,
    task_type: str = "general"
) -> dict:
    task_id = str(uuid.uuid4())
    ts = now()
    agent = assign_agent(task_type)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO tasks
               (id, title, description, status, task_type, agent, created_at, updated_at, current_owner)
               VALUES (?, ?, ?, 'queued', ?, ?, ?, ?, ?)""",
            (task_id, title, description, task_type, agent, ts, ts, owner)
        )
        await db.execute(
            """INSERT INTO task_events (task_id, from_status, to_status, timestamp, actor)
               VALUES (?, null, 'queued', ?, ?)""",
            (task_id, ts, owner or "system")
        )
        await db.commit()

    await audit("create_task", f"task/{task_id}", f"title={title} type={task_type} agent={agent}")
    checkpoint(task_id, "created")
    return {"id": task_id, "title": title, "status": "queued", "task_type": task_type, "agent": agent}


async def transition_task(task_id: str, to_status: str, actor: str = "system") -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            raise ValueError(f"Task {task_id} not found")

        from_status = row["status"]
        allowed = VALID_TRANSITIONS.get(from_status, [])
        if to_status not in allowed:
            raise ValueError(
                f"Invalid transition: {from_status} → {to_status}. "
                f"Allowed from {from_status}: {allowed}"
            )

        ts = now()
        await db.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (to_status, ts, task_id)
        )
        await db.execute(
            """INSERT INTO task_events (task_id, from_status, to_status, timestamp, actor)
               VALUES (?, ?, ?, ?, ?)""",
            (task_id, from_status, to_status, ts, actor)
        )
        await db.commit()

    await audit(
        "transition_task",
        f"task/{task_id}",
        f"{from_status} → {to_status} by {actor}"
    )
    checkpoint(task_id, f"{from_status}-to-{to_status}")
    return {"id": task_id, "from_status": from_status, "to_status": to_status}


async def get_task(task_id: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            raise ValueError(f"Task {task_id} not found")
        return dict(row)


async def list_tasks(status: str = None) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if status:
            async with db.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC", (status,)
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_task_events(task_id: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM task_events WHERE task_id = ? ORDER BY timestamp ASC",
            (task_id,)
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_audit_log(limit: int = 100) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def list_checkpoints() -> list:
    result = subprocess.run(
        ["git", "-C", "/home/kingdom-os", "tag", "-l", "checkpoint/*"],
        capture_output=True, text=True
    )
    tags = [t for t in result.stdout.strip().split("\n") if t]
    return sorted(tags, reverse=True)
