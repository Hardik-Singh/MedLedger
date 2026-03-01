"""
MedLedger Main Backend — FastAPI on port 8000
WebSocket hub for real-time dashboard + REST audit API
"""

import asyncio
import json
import os
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import aiosqlite

from backend.database import DB_PATH, init_db
from backend.audit_chain import init_chain, verify_chain, get_full_log, sign_action, tamper_record, restore_record
from backend.models import AgentTask

app = FastAPI(title="MedLedger API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────── WebSocket Hub ────────────────────────────

connected_clients: List[WebSocket] = []


async def broadcast(data: dict):
    message = json.dumps(data)
    disconnected = []
    for ws in connected_clients:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in connected_clients:
            connected_clients.remove(ws)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in connected_clients:
            connected_clients.remove(ws)


# ──────────────────────────── REST API ────────────────────────────

@app.get("/audit/log")
async def audit_log():
    return await get_full_log()


@app.get("/audit/verify")
async def audit_verify():
    return await verify_chain()


@app.get("/patients/current")
async def patients_current():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM patients ORDER BY id")
        return [dict(row) for row in await cursor.fetchall()]


# ──────────────────────────── Agent ────────────────────────────

@app.post("/agent/run")
async def agent_run(task: AgentTask):
    """Run the browser-use agent with a given task. Non-blocking."""
    agent_name = task.agent_name if hasattr(task, 'agent_name') and task.agent_name else "MedLedger Agent"
    api_key = task.api_key if hasattr(task, 'api_key') and task.api_key else None
    asyncio.create_task(_run_agent(task.task, agent_name, api_key))
    return {"status": "started", "task": task.task, "agent_name": agent_name}


async def _run_agent(task_str: str, agent_name: str = "MedLedger Agent", api_key: str = None):
    """Execute agent task and broadcast each action over WebSocket."""
    try:
        from backend.agent import run_agent_task
        await run_agent_task(task_str, broadcast_fn=broadcast, agent_name=agent_name, api_key=api_key)
    except ImportError as e:
        await broadcast({"type": "error", "message": f"Agent dependencies not installed: {e}"})
    except Exception as e:
        await broadcast({"type": "error", "message": f"Agent error: {str(e)}"})


# ──────────────────────────── API Key Status ────────────────────────────

@app.get("/api/key-status")
async def api_key_status():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    has_key = bool(key and key.startswith("sk-"))
    return {"has_key": has_key, "key_preview": f"{key[:12]}...{key[-4:]}" if has_key and len(key) > 16 else None}


@app.post("/api/set-key")
async def set_api_key(body: dict):
    key = body.get("key", "")
    if key:
        os.environ["ANTHROPIC_API_KEY"] = key
        return {"status": "ok", "has_key": True}
    return {"status": "error", "message": "No key provided"}


# ──────────────────────────── Tamper Simulation ────────────────────────────

@app.post("/audit/tamper")
async def audit_tamper():
    """Intentionally corrupt one audit record for demo purposes."""
    result = await tamper_record()
    if result:
        await broadcast({"type": "tamper", "message": "Record tampered! Chain integrity compromised.", "tampered_id": result})
    return {"status": "tampered", "tampered_id": result}


@app.post("/audit/restore")
async def audit_restore():
    """Restore the tampered record."""
    result = await restore_record()
    if result:
        await broadcast({"type": "restored", "message": "Record restored. Chain integrity restored."})
    return {"status": "restored"}


# ──────────────────────────── Export ────────────────────────────

@app.get("/audit/export")
async def audit_export():
    """Export full audit log + verification as JSON."""
    log = await get_full_log()
    verification = await verify_chain()
    return {
        "exported_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "verification": verification,
        "audit_log": log,
    }


# ──────────────────────────── Startup ────────────────────────────

@app.on_event("startup")
async def startup():
    await init_db()
    await init_chain()


# ──────────────────────────── Serve Frontend ────────────────────────────

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "build")

if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
