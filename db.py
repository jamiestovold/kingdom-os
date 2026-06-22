import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "kingdom.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    task_type TEXT NOT NULL DEFAULT 'general',
    agent TEXT NOT NULL DEFAULT 'claude',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    current_owner TEXT
);

CREATE TABLE IF NOT EXISTS task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'system',
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    action TEXT NOT NULL,
    resource TEXT NOT NULL,
    details TEXT
);

CREATE TABLE IF NOT EXISTS agent_registry (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    description TEXT,
    available INTEGER NOT NULL DEFAULT 1,
    last_health_check TEXT,
    health_status TEXT DEFAULT 'unknown'
);
"""

VALID_TRANSITIONS = {
    "queued": ["running"],
    "running": ["waiting_approval", "failed"],
    "waiting_approval": ["approved", "running"],
    "approved": ["completed"],
    "failed": [],
    "completed": [],
}

VALID_AGENTS = ["claude", "codex", "local_llm", "script"]

VALID_TASK_TYPES = [
    "general",
    "architecture",
    "review",
    "research",
    "analysis",
    "build",
    "test",
    "document",
    "infra",
]

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()

async def get_db():
    return aiosqlite.connect(DB_PATH)

# Whitelisted scripts — only these can be executed by the script agent
SCRIPT_WHITELIST = [
    "scripts/kingdom-doctor.sh",
    "scripts/watchdog.sh",
    "scripts/backup.sh",
    "scripts/checkpoint.sh",
]
