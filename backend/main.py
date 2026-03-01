"""
MedLedger Main Backend — FastAPI on port 8000
WebSocket hub for real-time dashboard + REST audit API
"""

import asyncio
import json
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import aiosqlite

from backend.database import DB_PATH, init_db
from backend.audit_chain import init_chain, verify_chain, get_full_log, sign_action
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


@app.post("/agent/run")
async def agent_run(task: AgentTask):
    """Run the browser-use agent with a given task. Non-blocking — streams results via WebSocket."""
    # Import here to avoid circular imports and allow running without browser-use installed
    asyncio.create_task(_run_agent(task.task))
    return {"status": "started", "task": task.task}


async def _run_agent(task_str: str):
    """Execute agent task and broadcast each action over WebSocket."""
    try:
        from backend.agent import run_agent_task
        await run_agent_task(task_str, broadcast_fn=broadcast)
    except ImportError as e:
        await broadcast({"type": "error", "message": f"Agent dependencies not installed: {e}"})
    except Exception as e:
        await broadcast({"type": "error", "message": f"Agent error: {str(e)}"})


# ──────────────────────────── Startup ────────────────────────────

@app.on_event("startup")
async def startup():
    await init_db()
    await init_chain()


# ──────────────────────────── Serve Frontend ────────────────────────────

import os
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "build")

if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
