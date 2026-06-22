import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from db import init_db
from engine import (
    create_task, transition_task, get_task,
    list_tasks, get_task_events, get_audit_log,
    list_checkpoints, audit
)
from health import check_all_agents
from routing import assign_agent, ROUTING_TABLE
from executor import execute_task, get_run, get_run_logs, list_runs
from approvals import approve_run, reject_run, complete_task, get_approvals
from daemon import get_daemon_state, update_daemon_state, POLL_INTERVAL_SECONDS, RUNNING_TIMEOUT_SECONDS, MAX_TASKS_PER_HOUR

load_dotenv()

API_TOKEN = os.getenv("KINGDOM_API_TOKEN")
VERSION = os.getenv("KINGDOM_VERSION", "1.0.0")

if not API_TOKEN:
    raise RuntimeError("KINGDOM_API_TOKEN not set in .env")

security = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    if credentials.credentials != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials.credentials


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(
    title="Kingdom Core",
    version=VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)


# ── Public endpoints ──────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "kingdom-core"
    }


@app.get("/version")
async def version():
    return {
        "version": VERSION,
        "service": "kingdom-core"
    }


# ── Task endpoints ────────────────────────────────────────────────────────────

class CreateTaskRequest(BaseModel):
    title: str
    description: Optional[str] = None
    owner: Optional[str] = None
    task_type: Optional[str] = "general"


class TransitionRequest(BaseModel):
    to_status: str
    actor: Optional[str] = "api"


@app.post("/tasks", dependencies=[Depends(verify_token)])
async def api_create_task(req: CreateTaskRequest):
    task = await create_task(req.title, req.description, req.owner, req.task_type)
    return task


@app.get("/tasks", dependencies=[Depends(verify_token)])
async def api_list_tasks(status: Optional[str] = None):
    tasks = await list_tasks(status)
    return {"tasks": tasks, "count": len(tasks)}


@app.get("/tasks/{task_id}", dependencies=[Depends(verify_token)])
async def api_get_task(task_id: str):
    try:
        task = await get_task(task_id)
        return task
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/tasks/{task_id}/transition", dependencies=[Depends(verify_token)])
async def api_transition_task(task_id: str, req: TransitionRequest):
    try:
        result = await transition_task(task_id, req.to_status, req.actor)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/tasks/{task_id}/events", dependencies=[Depends(verify_token)])
async def api_task_events(task_id: str):
    events = await get_task_events(task_id)
    return {"task_id": task_id, "events": events}


# ── Run endpoints ─────────────────────────────────────────────────────────────

@app.post("/tasks/{task_id}/run", dependencies=[Depends(verify_token)])
async def api_run_task(task_id: str):
    """
    Manually trigger execution of a queued task.
    Nothing executes automatically — this endpoint must be called explicitly.
    All runs default to requires_approval = True.
    Output is captured and logged. Never applied automatically.
    Task moves to waiting_approval on success, failed on error.
    """
    try:
        task = await get_task(task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if task["status"] != "queued":
        raise HTTPException(
            status_code=400,
            detail=f"Task must be in 'queued' status to run. Current status: {task['status']}"
        )

    await audit("trigger_run", f"task/{task_id}", f"agent={task['agent']}")
    result = await execute_task(task)
    return result


@app.get("/tasks/{task_id}/runs", dependencies=[Depends(verify_token)])
async def api_task_runs(task_id: str):
    runs = await list_runs(task_id)
    return {"task_id": task_id, "runs": runs}


@app.get("/runs", dependencies=[Depends(verify_token)])
async def api_list_runs():
    runs = await list_runs()
    return {"runs": runs, "count": len(runs)}


@app.get("/runs/{run_id}", dependencies=[Depends(verify_token)])
async def api_get_run(run_id: str):
    try:
        run = await get_run(run_id)
        return run
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/runs/{run_id}/logs", dependencies=[Depends(verify_token)])
async def api_run_logs(run_id: str):
    logs = await get_run_logs(run_id)
    return {"run_id": run_id, "logs": logs}


# ── Approval endpoints ────────────────────────────────────────────────────────

class ApproveRequest(BaseModel):
    actor: str
    note: Optional[str] = None


class RejectRequest(BaseModel):
    actor: str
    reason: str


class CompleteRequest(BaseModel):
    actor: str


@app.post("/runs/{run_id}/approve", dependencies=[Depends(verify_token)])
async def api_approve_run(run_id: str, req: ApproveRequest):
    """
    Approve a run in waiting_approval state.
    Records actor and timestamp.
    Transitions task: waiting_approval -> approved.
    Does not apply output to files.
    Does not complete the task -- call POST /tasks/{id}/complete for that.
    """
    try:
        result = await approve_run(run_id, req.actor, req.note)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/runs/{run_id}/reject", dependencies=[Depends(verify_token)])
async def api_reject_run(run_id: str, req: RejectRequest):
    """
    Reject a run in waiting_approval state.
    Reason is required.
    Records actor, reason, and timestamp.
    Transitions task: waiting_approval -> failed.
    To retry: create a new task.
    """
    try:
        result = await reject_run(run_id, req.actor, req.reason)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tasks/{task_id}/complete", dependencies=[Depends(verify_token)])
async def api_complete_task(task_id: str, req: CompleteRequest):
    """
    Mark an approved task as completed.
    Explicit human action only. Never automatic.
    Task must be in approved state.
    """
    try:
        result = await complete_task(task_id, req.actor)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/approvals", dependencies=[Depends(verify_token)])
async def api_list_approvals():
    records = await get_approvals()
    return {"approvals": records, "count": len(records)}


@app.get("/tasks/{task_id}/approvals", dependencies=[Depends(verify_token)])
async def api_task_approvals(task_id: str):
    records = await get_approvals(task_id=task_id)
    return {"task_id": task_id, "approvals": records}


@app.get("/runs/{run_id}/approvals", dependencies=[Depends(verify_token)])
async def api_run_approvals(run_id: str):
    records = await get_approvals(run_id=run_id)
    return {"run_id": run_id, "approvals": records}


# ── Daemon endpoints ──────────────────────────────────────────────────────────

@app.get("/daemon/status")
async def api_daemon_status():
    """
    Returns current daemon state.
    Public endpoint -- no token required.
    """
    state = await get_daemon_state()
    return {
        "daemon": {
            "paused": bool(state.get("paused", 0)),
            "last_poll": state.get("last_poll"),
            "tasks_run_this_hour": state.get("tasks_run_this_hour", 0),
            "hour_window_start": state.get("hour_window_start"),
            "started_at": state.get("started_at"),
            "updated_at": state.get("updated_at"),
        },
        "config": {
            "poll_interval_seconds": POLL_INTERVAL_SECONDS,
            "running_timeout_seconds": RUNNING_TIMEOUT_SECONDS,
            "max_tasks_per_hour": MAX_TASKS_PER_HOUR,
            "worker_count": 1,
        }
    }


@app.post("/daemon/pause", dependencies=[Depends(verify_token)])
async def api_daemon_pause():
    """
    Pause the daemon. Continues running but skips task processing.
    Does not stop the systemd service.
    """
    await update_daemon_state(paused=1)
    await audit("daemon_paused", "daemon", "paused via API")
    return {"status": "paused", "message": "Daemon will skip processing on next poll"}


@app.post("/daemon/resume", dependencies=[Depends(verify_token)])
async def api_daemon_resume():
    """Resume the daemon after pausing."""
    await update_daemon_state(paused=0)
    await audit("daemon_resumed", "daemon", "resumed via API")
    return {"status": "running", "message": "Daemon will resume processing on next poll"}


# ── Agent endpoints ───────────────────────────────────────────────────────────

@app.get("/agents")
async def api_agents():
    """
    Returns availability and health status of all agents.
    Public endpoint — no token required for health visibility.
    """
    agents = await check_all_agents()
    return {
        "agents": agents,
        "routing_table": ROUTING_TABLE,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/agents/routing")
async def api_routing_table():
    """Returns the task_type to agent routing table."""
    return {"routing": ROUTING_TABLE}


# ── Audit log ─────────────────────────────────────────────────────────────────

@app.get("/audit", dependencies=[Depends(verify_token)])
async def api_audit_log(limit: int = 100):
    logs = await get_audit_log(limit)
    return {"logs": logs, "count": len(logs)}


# ── Checkpoints ───────────────────────────────────────────────────────────────

@app.get("/checkpoints", dependencies=[Depends(verify_token)])
async def api_checkpoints():
    tags = await list_checkpoints()
    return {"checkpoints": tags, "count": len(tags)}
