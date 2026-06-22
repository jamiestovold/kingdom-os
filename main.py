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


class TransitionRequest(BaseModel):
    to_status: str
    actor: Optional[str] = "api"


@app.post("/tasks", dependencies=[Depends(verify_token)])
async def api_create_task(req: CreateTaskRequest):
    task = await create_task(req.title, req.description, req.owner)
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
