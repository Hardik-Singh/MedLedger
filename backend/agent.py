"""
MedLedger Browser Use Agent
Custom tools that cryptographically sign every action before executing.
"""

import asyncio
import json
import os
from typing import Callable, Awaitable, Optional

import aiosqlite
from backend.database import DB_PATH
from backend.audit_chain import sign_action

# Browser Use imports — guarded so the rest of the backend works without it
try:
    from browser_use import Agent, Browser, BrowserConfig
    from browser_use.controller.service import Controller
    from langchain_anthropic import ChatAnthropic
    HAS_BROWSER_USE = True
except ImportError:
    HAS_BROWSER_USE = False


async def run_agent_task(task: str, broadcast_fn: Optional[Callable[[dict], Awaitable]] = None):
    """Run a browser-use agent with cryptographically signed tool calls."""

    if not HAS_BROWSER_USE:
        raise ImportError("browser-use and langchain-anthropic must be installed")

    controller = Controller()

    # ── Custom tools — each one signs its action before executing ──

    @controller.action("Search for a patient by name or MRN")
    async def search_patient(query: str):
        action = await sign_action("SEARCH", {"query": query})
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, first_name, last_name, mrn, diagnosis FROM patients WHERE (first_name || ' ' || last_name LIKE ? OR mrn LIKE ?) AND deleted = 0",
                (f"%{query}%", f"%{query}%"),
            )
            results = [dict(row) for row in await cursor.fetchall()]
        return json.dumps(results, indent=2)

    @controller.action("View a patient's full details")
    async def view_patient(patient_id: int):
        action = await sign_action("VIEW", {"patient_id": patient_id})
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
            row = await cursor.fetchone()
            if not row:
                return "Patient not found"
            return json.dumps(dict(row), indent=2)

    @controller.action("Update a specific field of a patient record")
    async def update_patient(patient_id: int, field: str, value: str):
        allowed = ["first_name", "last_name", "dob", "phone", "insurance", "allergies", "diagnosis", "medications"]
        if field not in allowed:
            return f"Field '{field}' is not updatable. Allowed: {allowed}"

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM patients WHERE id = ? AND deleted = 0", (patient_id,))
            old = await cursor.fetchone()
            if not old:
                return "Patient not found"

            old_value = old[field]
            action = await sign_action("UPDATE", {
                "patient_id": patient_id,
                "field": field,
                "old_value": old_value,
                "new_value": value,
                "patient_name": f"{old['first_name']} {old['last_name']}",
            })
            if broadcast_fn:
                await broadcast_fn({"type": "action", **action})

            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                """INSERT INTO patient_history
                   (patient_id, first_name, last_name, dob, mrn, diagnosis, medications, allergies, last_visit, phone, insurance, change_type, changed_at, changed_field, old_value, new_value)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'UPDATE', ?, ?, ?, ?)""",
                (patient_id, old['first_name'], old['last_name'], old['dob'], old['mrn'], old['diagnosis'], old['medications'], old['allergies'], old['last_visit'], old['phone'], old['insurance'], now, field, old_value, value),
            )
            await db.execute(f"UPDATE patients SET {field} = ? WHERE id = ?", (value, patient_id))
            await db.commit()

        return f"Updated {field} from '{old_value}' to '{value}'"

    @controller.action("Delete a patient record (soft delete)")
    async def delete_patient(patient_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM patients WHERE id = ? AND deleted = 0", (patient_id,))
            old = await cursor.fetchone()
            if not old:
                return "Patient not found or already deleted"

            action = await sign_action("DELETE", {
                "patient_id": patient_id,
                "patient_name": f"{old['first_name']} {old['last_name']}",
                "mrn": old["mrn"],
            })
            if broadcast_fn:
                await broadcast_fn({"type": "action", **action})

            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                """INSERT INTO patient_history
                   (patient_id, first_name, last_name, dob, mrn, diagnosis, medications, allergies, last_visit, phone, insurance, change_type, changed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DELETE', ?)""",
                (patient_id, old['first_name'], old['last_name'], old['dob'], old['mrn'], old['diagnosis'], old['medications'], old['allergies'], old['last_visit'], old['phone'], old['insurance'], now),
            )
            await db.execute("UPDATE patients SET deleted = 1, deleted_at = ? WHERE id = ?", (now, patient_id))
            await db.commit()

        return f"Patient {old['first_name']} {old['last_name']} deleted"

    @controller.action("Get version history for a patient")
    async def get_patient_history(patient_id: int):
        action = await sign_action("HISTORY", {"patient_id": patient_id})
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM patient_history WHERE patient_id = ? ORDER BY changed_at DESC",
                (patient_id,),
            )
            rows = [dict(row) for row in await cursor.fetchall()]
        return json.dumps(rows, indent=2) if rows else "No history found"

    # ── Configure and run ──

    llm = ChatAnthropic(model_name="claude-sonnet-4-20250514", timeout=60, stop=None)

    browser = Browser(config=BrowserConfig(
        headless=True,
        disable_security=True,
    ))

    agent = Agent(
        task=task,
        llm=llm,
        controller=controller,
        browser=browser,
        use_vision=True,
    )

    try:
        result = await agent.run()
        if broadcast_fn:
            action = await sign_action("TASK_COMPLETE", {"task": task, "result": str(result)})
            await broadcast_fn({"type": "action", **action})
            await broadcast_fn({"type": "task_complete", "result": str(result)})
    finally:
        await browser.close()
