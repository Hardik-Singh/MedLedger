"""
MedLedger Main Backend — FastAPI on port 8000
WebSocket hub, REST audit API, multi-agent orchestration, alerts, exports,
Supermemory integration, auditing agent.
"""

import asyncio
import csv
import io
import json
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
import aiosqlite

from backend.database import DB_PATH, init_db
from backend.audit_chain import init_chain, verify_chain, get_full_log, sign_action, tamper_record, restore_record
from backend.models import AgentTask, MultiAgentTask
from backend.memory import memory_status, reset_client
from backend.risk_engine import calculate_patient_risk, get_all_patient_risks
from backend.interactions import check_current_allergy_conflicts


@asynccontextmanager
async def lifespan(app):
    await init_db()
    await init_chain()
    yield


app = FastAPI(title="MedLedger API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────── Alerts Engine ────────────────────────────

alerts: list[dict] = []
_recent_timestamps: list[float] = []


def _check_alerts(action: dict):
    """Rules engine — fires alerts based on audit events."""
    now = datetime.now(timezone.utc).isoformat()
    p = action.get("payload", {})
    at = action.get("action_type", "")

    if at == "DELETE":
        alerts.append({
            "id": len(alerts) + 1, "created_at": now, "severity": "CRITICAL",
            "message": f"Patient record deleted: {p.get('patient_name', 'Unknown')}",
            "related_action_id": action.get("id"), "acknowledged": False,
        })
    elif at == "UPDATE" and p.get("field") == "medications":
        alerts.append({
            "id": len(alerts) + 1, "created_at": now, "severity": "HIGH",
            "message": f"Medication change: {p.get('patient_name', '')} — {p.get('old_value', '')[:40]} → {p.get('new_value', '')[:40]}",
            "related_action_id": action.get("id"), "acknowledged": False,
        })

    # Burst detection
    _recent_timestamps.append(time.time())
    cutoff = time.time() - 60
    _recent_timestamps[:] = [t for t in _recent_timestamps if t > cutoff]
    if len(_recent_timestamps) > 5:
        if not any(a["message"].startswith("High activity") and not a["acknowledged"] for a in alerts):
            alerts.append({
                "id": len(alerts) + 1, "created_at": now, "severity": "MEDIUM",
                "message": f"High activity burst — {len(_recent_timestamps)} actions in 60s",
                "related_action_id": action.get("id"), "acknowledged": False,
            })

    if not action.get("verified", True):
        alerts.append({
            "id": len(alerts) + 1, "created_at": now, "severity": "CRITICAL",
            "message": "Action failed verification — manual review recommended",
            "related_action_id": action.get("id"), "acknowledged": False,
        })


# ──────────────────────────── WebSocket Hub ────────────────────────────

connected_clients: List[WebSocket] = []


async def broadcast(data: dict):
    if data.get("type") == "action":
        _check_alerts(data)

    message = json.dumps(data, default=str)
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
        pass
    except Exception:
        pass
    finally:
        if ws in connected_clients:
            connected_clients.remove(ws)


# ──────────────────────────── Audit API ────────────────────────────

@app.get("/audit/log")
async def audit_log():
    return await get_full_log()


@app.get("/audit/verify")
async def audit_verify():
    return await verify_chain()


# ──────────────────────────── Patients ────────────────────────────

@app.get("/patients/current")
async def patients_current():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM patients ORDER BY id")
        return [dict(row) for row in await cursor.fetchall()]


@app.get("/patients/{patient_id}/history")
async def patient_history(patient_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM patient_history WHERE patient_id = ? ORDER BY changed_at DESC", (patient_id,)
        )
        return [dict(row) for row in await cursor.fetchall()]


# ──────────────────────────── Single Agent ────────────────────────────

@app.post("/agent/run")
async def agent_run(task: AgentTask):
    agent_name = task.agent_name or "MedLedger Agent"
    asyncio.create_task(_run_agent(task.task, agent_name, task.api_key))
    return {"status": "started", "task": task.task, "agent_name": agent_name}


async def _run_agent(task_str: str, agent_name: str, api_key: str = None):
    try:
        from backend.agent import run_agent_task
        await run_agent_task(task_str, broadcast_fn=broadcast, agent_name=agent_name, api_key=api_key)
    except ImportError as e:
        await broadcast({"type": "error", "message": f"Agent deps not installed: {e}"})
    except Exception as e:
        await broadcast({"type": "error", "message": f"Agent error: {str(e)}"})


# ──────────────────────────── Multi-Agent ────────────────────────────

@app.post("/agent/multi")
async def agent_multi(task: MultiAgentTask):
    """Run multiple agents sequentially sharing one audit chain. Cross-signed."""
    asyncio.create_task(_run_multi(task.agents, task.api_key))
    return {"status": "started", "agents": [a["name"] for a in task.agents]}


async def _run_multi(agents_config: list[dict], api_key: str = None):
    try:
        from backend.agent import run_multi_agent
        await run_multi_agent(agents_config, broadcast_fn=broadcast, api_key=api_key)
    except ImportError as e:
        await broadcast({"type": "error", "message": f"Agent deps not installed: {e}"})
    except Exception as e:
        await broadcast({"type": "error", "message": f"Multi-agent error: {str(e)}"})


# ──────────────────────────── Auditing Agent ────────────────────────────

@app.post("/agent/audit")
async def agent_audit():
    """Run the auditing agent — checks chain integrity, data quality, and patterns."""
    asyncio.create_task(_run_audit())
    return {"status": "started", "agent": "AUDITOR"}


async def _run_audit():
    try:
        from backend.agent import run_audit_agent
        await run_audit_agent(broadcast_fn=broadcast)
    except Exception as e:
        await broadcast({"type": "error", "message": f"Audit agent error: {str(e)}"})


# ──────────────────────────── API Keys ────────────────────────────

@app.get("/api/key-status")
async def api_key_status():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    has_key = bool(key and key.startswith("sk-"))
    mem = memory_status()
    return {
        "has_key": has_key,
        "key_preview": f"{key[:12]}...{key[-4:]}" if has_key and len(key) > 16 else None,
        "memory": mem,
    }


@app.post("/api/set-key")
async def set_api_key(body: dict):
    key = body.get("key", "")
    if key:
        os.environ["ANTHROPIC_API_KEY"] = key
        return {"status": "ok", "has_key": True}
    return {"status": "error", "message": "No key provided"}


@app.post("/api/set-memory-key")
async def set_memory_key(body: dict):
    key = body.get("key", "")
    if key:
        os.environ["SUPERMEMORY_API_KEY"] = key
        reset_client()
        return {"status": "ok", "memory": memory_status()}
    return {"status": "error", "message": "No key provided"}


@app.get("/api/memory-status")
async def get_memory_status():
    return memory_status()


# ──────────────────────────── Tamper ────────────────────────────

@app.post("/audit/tamper")
async def audit_tamper():
    result = await tamper_record()
    if result:
        await broadcast({"type": "tamper", "message": "Record tampered!", "tampered_id": result})
    return {"status": "tampered", "tampered_id": result}


@app.post("/audit/restore")
async def audit_restore():
    result = await restore_record()
    if result:
        await broadcast({"type": "restored", "message": "Chain restored."})
    return {"status": "restored"}


# ──────────────────────────── Alerts ────────────────────────────

@app.get("/alerts")
async def get_alerts():
    return alerts


@app.post("/alerts/{alert_id}/ack")
async def ack_alert(alert_id: int):
    for a in alerts:
        if a["id"] == alert_id:
            a["acknowledged"] = True
            return {"status": "acknowledged"}
    return {"status": "not_found"}


# ──────────────────────────── Export ────────────────────────────

@app.get("/audit/export")
async def audit_export_json():
    log = await get_full_log()
    verification = await verify_chain()
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "verification": verification,
        "audit_log": log,
    }


@app.get("/audit/export/csv")
async def audit_export_csv():
    log = await get_full_log()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["block", "timestamp", "action_type", "agent_id", "payload_summary", "hash", "prev_hash", "verified"])
    for i, row in enumerate(log):
        p = row.get("payload", {})
        summary = p.get("query", "") or p.get("patient_name", "") or str(p.get("patient_id", ""))
        writer.writerow([
            i + 1, row["timestamp"], row["action_type"], row["agent_id"],
            summary[:60], row["hash"][:16], row["prev_hash"][:16], row["verified"],
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=medledger-audit-{datetime.now().strftime('%Y%m%d')}.csv"},
    )


# ──────────────────────────── Stats ────────────────────────────

@app.get("/stats")
async def stats():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        active = (await (await db.execute("SELECT COUNT(*) as c FROM patients WHERE deleted = 0")).fetchone())["c"]
        deleted = (await (await db.execute("SELECT COUNT(*) as c FROM patients WHERE deleted = 1")).fetchone())["c"]
        total_actions = (await (await db.execute("SELECT COUNT(*) as c FROM audit_log")).fetchone())["c"]
        changes = (await (await db.execute("SELECT COUNT(*) as c FROM patient_history")).fetchone())["c"]
    return {
        "active_patients": active, "deleted_patients": deleted,
        "total_actions": total_actions, "total_changes": changes,
        "unread_alerts": len([a for a in alerts if not a["acknowledged"]]),
        "memory": memory_status()["status"],
    }


# ──────────────────────────── Appointments ────────────────────────────

@app.get("/appointments/upcoming")
async def upcoming_appointments():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM appointments WHERE status = 'scheduled' ORDER BY scheduled_for ASC LIMIT 20"
        )
        return [dict(r) for r in await cursor.fetchall()]


@app.get("/patients/{patient_id}/appointments")
async def patient_appointments(patient_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM appointments WHERE patient_id = ? ORDER BY scheduled_for DESC", (patient_id,)
        )
        return [dict(r) for r in await cursor.fetchall()]


@app.post("/appointments")
async def create_appointment(body: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            """INSERT INTO appointments (patient_id, patient_name, doctor_name, appointment_type, scheduled_for, duration_minutes, status, notes, created_at, created_by)
               VALUES (?, ?, ?, ?, ?, ?, 'scheduled', ?, ?, ?)""",
            (body["patient_id"], body.get("patient_name", ""), body["doctor_name"],
             body["appointment_type"], body["scheduled_for"],
             body.get("duration_minutes", 30), body.get("notes", ""), now, body.get("created_by", "agent")),
        )
        await db.commit()
    return {"status": "created"}


@app.post("/appointments/{appt_id}/cancel")
async def cancel_appointment(appt_id: int, body: dict = None):
    body = body or {}
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE appointments SET status = 'cancelled', notes = notes || ? WHERE id = ?",
                         (f" [Cancelled: {body.get('reason', '')}]", appt_id))
        await db.commit()
    return {"status": "cancelled"}


# ──────────────────────────── Lab Results ────────────────────────────

@app.get("/patients/{patient_id}/labs")
async def patient_labs(patient_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM lab_results WHERE patient_id = ? ORDER BY resulted_at DESC", (patient_id,)
        )
        return [dict(r) for r in await cursor.fetchall()]


# ──────────────────────────── Clinical Notes ────────────────────────────

@app.get("/patients/{patient_id}/notes")
async def patient_notes(patient_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM patient_notes WHERE patient_id = ? ORDER BY drafted_at DESC", (patient_id,)
        )
        return [dict(r) for r in await cursor.fetchall()]


@app.post("/patients/{patient_id}/notes")
async def create_note(patient_id: int, body: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "INSERT INTO patient_notes (patient_id, note_type, content, drafted_by, drafted_at) VALUES (?, ?, ?, ?, ?)",
            (patient_id, body.get("note_type", "SOAP"), body["content"], body.get("drafted_by", "agent"), now),
        )
        await db.commit()
    return {"status": "created"}


@app.post("/notes/{note_id}/finalize")
async def finalize_note(note_id: int, body: dict = None):
    body = body or {}
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE patient_notes SET status = 'finalized', finalized_by = ?, finalized_at = ? WHERE id = ?",
            (body.get("finalized_by", "Dr. Agent"), now, note_id),
        )
        await db.commit()
    return {"status": "finalized"}


# ──────────────────────────── Risk Scores ────────────────────────────

@app.get("/patients/risks")
async def all_patient_risks():
    return await get_all_patient_risks()


@app.get("/patients/{patient_id}/risk")
async def patient_risk(patient_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
        p = await cursor.fetchone()
        if not p:
            return {"error": "not found"}
    return calculate_patient_risk(dict(p))


# ──────────────────────────── Care Team ────────────────────────────

@app.get("/patients/{patient_id}/care-team")
async def patient_care_team(patient_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM care_team_log WHERE patient_id = ? ORDER BY timestamp DESC LIMIT 50",
            (patient_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]


# ──────────────────────────── Handoff Report ────────────────────────────

@app.get("/reports/handoff")
async def handoff_report():
    """Generate shift handoff report from recent audit activity."""
    log = await get_full_log()
    # Last 20 actions as a reasonable session window
    recent = log[-20:] if len(log) > 20 else log

    patients_accessed = []
    meds_changed = []
    for a in recent:
        p = a.get("payload", {})
        if a["action_type"] in ("VIEW", "UPDATE", "DELETE"):
            name = p.get("patient_name", f"Patient #{p.get('patient_id', '?')}")
            if name not in patients_accessed:
                patients_accessed.append(name)
        if a["action_type"] == "UPDATE" and p.get("field") == "medications":
            meds_changed.append({
                "patient": p.get("patient_name"),
                "old": p.get("old_value", ""),
                "new": p.get("new_value", ""),
            })

    unacked = [a for a in alerts if not a["acknowledged"]]
    critical_alerts = [a for a in unacked if a.get("severity") == "CRITICAL"]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_actions": len(recent),
        "patients_accessed": patients_accessed,
        "medications_changed": meds_changed,
        "critical_alerts": critical_alerts,
        "unacknowledged_alerts": len(unacked),
    }


@app.get("/reports/handoff/html")
async def handoff_report_html():
    """Generate printable HTML handoff report."""
    report = await handoff_report()
    meds_rows = ""
    for m in report["medications_changed"]:
        meds_rows += f"<tr><td>{m['patient']}</td><td>{m['old'][:60]}</td><td>{m['new'][:60]}</td></tr>"

    patients_list = "".join(f"<li>{p}</li>" for p in report["patients_accessed"])
    alerts_list = "".join(f"<li><strong>{a['severity']}:</strong> {a['message']}</li>" for a in report["critical_alerts"])

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>MedLedger Shift Handoff Report</title>
<style>
body {{ font-family: 'Segoe UI', system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 24px; color: #1a202c; }}
h1 {{ color: #1e3a5f; border-bottom: 2px solid #2563eb; padding-bottom: 8px; }}
h2 {{ color: #334155; margin-top: 24px; }}
table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
th {{ background: #f1f5f9; text-align: left; padding: 8px 12px; border-bottom: 2px solid #e2e8f0; font-size: 12px; text-transform: uppercase; }}
td {{ padding: 8px 12px; border-bottom: 1px solid #f0f0f0; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }}
.stat {{ display: inline-block; background: #f1f5f9; padding: 8px 16px; border-radius: 8px; margin: 4px; text-align: center; }}
.stat-val {{ font-size: 24px; font-weight: 700; color: #1e3a5f; display: block; }}
.stat-lbl {{ font-size: 11px; color: #64748b; text-transform: uppercase; }}
.sig {{ margin-top: 48px; border-top: 1px solid #e2e8f0; padding-top: 16px; }}
ul {{ padding-left: 20px; }}
li {{ margin-bottom: 4px; }}
</style></head><body>
<h1>MedLedger — Shift Handoff Report</h1>
<p>Generated: {report['generated_at']}</p>
<div>
<span class="stat"><span class="stat-val">{report['total_actions']}</span><span class="stat-lbl">Actions</span></span>
<span class="stat"><span class="stat-val">{len(report['patients_accessed'])}</span><span class="stat-lbl">Patients</span></span>
<span class="stat"><span class="stat-val">{len(report['medications_changed'])}</span><span class="stat-lbl">Med Changes</span></span>
<span class="stat"><span class="stat-val">{report['unacknowledged_alerts']}</span><span class="stat-lbl">Unacked Alerts</span></span>
</div>
<h2>Patients Accessed</h2>
<ul>{patients_list if patients_list else '<li>None</li>'}</ul>
<h2>Medication Changes</h2>
{'<table><thead><tr><th>Patient</th><th>Previous</th><th>Updated</th></tr></thead><tbody>' + meds_rows + '</tbody></table>' if meds_rows else '<p>No medication changes during this shift.</p>'}
<h2>Critical Alerts</h2>
{('<ul>' + alerts_list + '</ul>') if alerts_list else '<p>No critical alerts.</p>'}
<div class="sig">
<p><strong>Signed Off By:</strong> ____________________</p>
<p><strong>Date/Time:</strong> ____________________</p>
</div>
</body></html>"""
    return HTMLResponse(html)


# ──────────────────────────── Rounds Summary ────────────────────────────

@app.get("/patients/{patient_id}/rounds-summary")
async def rounds_summary(patient_id: int):
    """Clean one-page patient summary for morning rounds."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
        p = await cursor.fetchone()
        if not p:
            return HTMLResponse("<h1>Patient not found</h1>")
        p = dict(p)

        labs_cursor = await db.execute(
            "SELECT * FROM lab_results WHERE patient_id = ? ORDER BY resulted_at DESC LIMIT 10", (patient_id,)
        )
        labs = [dict(r) for r in await labs_cursor.fetchall()]

        appts_cursor = await db.execute(
            "SELECT * FROM appointments WHERE patient_id = ? AND status = 'scheduled' ORDER BY scheduled_for ASC LIMIT 5", (patient_id,)
        )
        appts = [dict(r) for r in await appts_cursor.fetchall()]

        notes_cursor = await db.execute(
            "SELECT * FROM patient_notes WHERE patient_id = ? ORDER BY drafted_at DESC LIMIT 1", (patient_id,)
        )
        last_note = await notes_cursor.fetchone()

    risk = calculate_patient_risk(p)
    allergy_conflicts = check_current_allergy_conflicts(p.get("allergies", ""), p.get("medications", ""))
    risk_color = {"CRITICAL": "#dc2626", "HIGH": "#d97706", "MEDIUM": "#ca8a04", "LOW": "#16a34a"}.get(risk["risk_level"], "#6b7280")

    age = risk.get("age", "?")

    labs_rows = ""
    for lab in labs:
        status_color = {"high": "#d97706", "critical": "#dc2626", "low": "#2563eb", "normal": "#16a34a"}.get(lab["status"], "#6b7280")
        labs_rows += f"""<tr>
            <td>{lab['test_name']}</td>
            <td><strong>{lab['value']}</strong> {lab['unit']}</td>
            <td>{lab['reference_range_low']}-{lab['reference_range_high']} {lab['unit']}</td>
            <td style="color:{status_color};font-weight:600;">{lab['status'].upper()}</td>
            <td>{lab['resulted_at']}</td>
        </tr>"""

    appts_rows = ""
    for a in appts:
        appts_rows += f"<tr><td>{a['appointment_type']}</td><td>{a['scheduled_for']}</td><td>{a['doctor_name']}</td><td>{a['notes']}</td></tr>"

    note_excerpt = ""
    if last_note:
        note_excerpt = f"<p><em>{dict(last_note)['content'][:200]}...</em></p>"

    conflict_banner = ""
    if allergy_conflicts:
        conflict_items = "".join(f"<li>{c['description']}</li>" for c in allergy_conflicts)
        conflict_banner = f'<div role="alert" style="background:#fee2e2;border:1px solid #fca5a5;padding:12px;border-radius:8px;margin-bottom:16px;"><strong>Allergy Conflicts:</strong><ul>{conflict_items}</ul></div>'

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Rounds Summary — {p['first_name']} {p['last_name']}</title>
<style>
body {{ font-family: 'Segoe UI', system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; color: #1a202c; font-size: 13px; }}
h1 {{ color: #1e3a5f; font-size: 20px; margin-bottom: 4px; }}
h2 {{ color: #334155; font-size: 14px; margin-top: 16px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; }}
table {{ width: 100%; border-collapse: collapse; margin: 8px 0; }}
th {{ background: #f7fafc; text-align: left; padding: 6px 10px; border-bottom: 2px solid #e2e8f0; font-size: 11px; text-transform: uppercase; }}
td {{ padding: 6px 10px; border-bottom: 1px solid #f0f0f0; }}
.header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #2563eb; padding-bottom: 8px; margin-bottom: 12px; }}
.risk-badge {{ display: inline-block; padding: 4px 12px; border-radius: 6px; color: white; font-weight: 700; font-size: 12px; }}
.meta {{ color: #64748b; font-size: 12px; }}
.factors {{ list-style: disc; padding-left: 20px; }}
.factors li {{ margin-bottom: 2px; }}
</style></head><body>
<div class="header">
    <div>
        <h1>{p['first_name']} {p['last_name']}</h1>
        <span class="meta">MRN: {p['mrn']} | DOB: {p['dob']} (Age {age}) | Blood Type: {p.get('blood_type', '?')}</span>
    </div>
    <span class="risk-badge" style="background:{risk_color};">{risk['risk_level']} RISK (Score: {risk['score']})</span>
</div>
{conflict_banner}
<h2>Active Problems</h2>
<p>{p['diagnosis']}</p>
<h2>Current Medications</h2>
<p>{p['medications']}</p>
<h2>Allergies</h2>
<p>{p['allergies']}</p>
<h2>Risk Factors</h2>
<ul class="factors">{''.join(f'<li>{f}</li>' for f in risk['factors']) if risk['factors'] else '<li>None identified</li>'}</ul>
<h2>Lab Results</h2>
{'<table><thead><tr><th>Test</th><th>Result</th><th>Ref Range</th><th>Status</th><th>Date</th></tr></thead><tbody>' + labs_rows + '</tbody></table>' if labs_rows else '<p>No recent labs.</p>'}
<h2>Upcoming Appointments</h2>
{'<table><thead><tr><th>Type</th><th>Date</th><th>Doctor</th><th>Notes</th></tr></thead><tbody>' + appts_rows + '</tbody></table>' if appts_rows else '<p>No upcoming appointments.</p>'}
<h2>Latest Clinical Note</h2>
{note_excerpt if note_excerpt else '<p>No clinical notes on file.</p>'}
<h2>Emergency Contact</h2>
<p>{p.get('emergency_contact', 'Not on file')}</p>
<p style="margin-top:16px;color:#94a3b8;font-size:11px;">Generated {datetime.now(timezone.utc).isoformat()} — MedLedger Rounds Summary</p>
</body></html>"""
    return HTMLResponse(html)


# ──────────────────────────── Startup ────────────────────────────



# ──────────────────────────── Serve Frontend ────────────────────────────

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "build")

if os.path.isdir(FRONTEND_DIR):
    from fastapi.staticfiles import StaticFiles
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="frontend-static")

    @app.get("/dashboard/{full_path:path}", include_in_schema=False)
    @app.get("/dashboard", include_in_schema=False)
    async def serve_frontend(full_path: str = ""):
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
