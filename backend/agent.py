"""
MedLedger Browser Use Agent
Real browser-use integration — the agent navigates the patient portal with a
browser, clicking through pages, searching, viewing vitals, editing records.
Each action is cryptographically signed into the audit chain.
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Callable, Awaitable, Optional

import aiosqlite
from backend.database import DB_PATH
from backend.audit_chain import sign_action, verify_chain, get_full_log
from backend.memory import store_interaction, recall_context, memory_status

# ──────────────────────────── Browser Use imports ────────────────────────────

try:
    from browser_use.agent.service import Agent
    from browser_use.browser.session import BrowserSession
    from browser_use.controller import Controller
    from langchain_anthropic import ChatAnthropic
    HAS_BROWSER_USE = True
except ImportError:
    HAS_BROWSER_USE = False

PORTAL_URL = os.environ.get("PORTAL_URL", "http://localhost:8001")


# ──────────────────────────── Audit-Signing Tools ────────────────────────────
# These tools ONLY sign actions into the blockchain audit chain.
# The actual data operations happen through the browser navigating the portal.

def register_audit_tools(controller: "Controller", agent_id: str, broadcast_fn, action_count: list, patients_touched: set):
    """Register audit-signing tools on the browser-use controller."""

    @controller.action("Sign a SEARCH action into the audit chain after searching for patients in the portal browser.")
    async def audit_search(query: str):
        action = await sign_action("SEARCH", {"query": query}, agent_id=agent_id)
        action_count[0] += 1
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        await store_interaction(agent_id, "SEARCH", {"query": query})
        return f"Audit signed: SEARCH for '{query}'"

    @controller.action("Sign a VIEW action into the audit chain after viewing a patient record in the portal browser.")
    async def audit_view(patient_id: int, patient_name: str):
        action = await sign_action("VIEW", {"patient_id": patient_id, "patient_name": patient_name}, agent_id=agent_id)
        action_count[0] += 1
        patients_touched.add(patient_id)
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        await store_interaction(agent_id, "VIEW", {"patient_id": patient_id, "patient_name": patient_name})
        return f"Audit signed: VIEW {patient_name} (#{patient_id})"

    @controller.action(
        "Sign an UPDATE action into the audit chain after updating a patient field in the portal. "
        "Call this AFTER you have saved the changes through the portal edit form."
    )
    async def audit_update(patient_id: int, patient_name: str, field: str, old_value: str, new_value: str):
        payload = {
            "patient_id": patient_id,
            "patient_name": patient_name,
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
        }
        action = await sign_action("UPDATE", payload, agent_id=agent_id)
        action_count[0] += 1
        patients_touched.add(patient_id)
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        await store_interaction(agent_id, "UPDATE", payload)
        return f"Audit signed: UPDATE {patient_name}.{field} '{old_value}' -> '{new_value}'"

    @controller.action("Sign a DELETE action into the audit chain after deleting a patient in the portal browser.")
    async def audit_delete(patient_id: int, patient_name: str):
        payload = {"patient_id": patient_id, "patient_name": patient_name}
        action = await sign_action("DELETE", payload, agent_id=agent_id)
        action_count[0] += 1
        patients_touched.add(patient_id)
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        await store_interaction(agent_id, "DELETE", payload)
        return f"Audit signed: DELETE {patient_name}"

    @controller.action("Sign a LAB_REVIEW action after reviewing a patient's lab results or vitals in the portal.")
    async def audit_lab_review(patient_id: int, patient_name: str):
        action = await sign_action("LAB_REVIEW", {"patient_id": patient_id, "patient_name": patient_name}, agent_id=agent_id)
        action_count[0] += 1
        patients_touched.add(patient_id)
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        return f"Audit signed: LAB_REVIEW for {patient_name}"

    @controller.action("Sign an APPOINTMENTS action after checking a patient's upcoming appointments in the portal.")
    async def audit_appointments(patient_id: int, patient_name: str):
        action = await sign_action("APPOINTMENTS", {"patient_id": patient_id, "patient_name": patient_name}, agent_id=agent_id)
        action_count[0] += 1
        patients_touched.add(patient_id)
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        return f"Audit signed: APPOINTMENTS for {patient_name}"

    @controller.action("Sign a HISTORY action after reviewing a patient's change history in the portal.")
    async def audit_history(patient_id: int, patient_name: str):
        action = await sign_action("HISTORY", {"patient_id": patient_id, "patient_name": patient_name}, agent_id=agent_id)
        action_count[0] += 1
        patients_touched.add(patient_id)
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        return f"Audit signed: HISTORY for {patient_name}"


# ──────────────────────────── System Prompt ────────────────────────────

async def _build_system_prompt(agent_name: str, task: str, agent_id: str) -> str:
    """Build system prompt that instructs the agent to navigate the portal."""
    parts = [
        f"You are {agent_name}, an AI medical records agent.",
        "",
        f"You have a browser. Navigate the MedLedger Patient Portal at {PORTAL_URL} to accomplish your task.",
        "",
        "STEP-BY-STEP WORKFLOW:",
        f"1. Go to {PORTAL_URL}",
        "2. You will see a login page. Enter username 'demo' and password 'demo123', then click 'Sign In'",
        "3. After login you land on the Dashboard. Use the navigation links to go to Patients, Appointments, etc.",
        "4. Use the portal to accomplish your task:",
        "   - Click 'Patients' in the nav bar to see the patient list",
        "   - Use the search box to find patients by name, MRN, diagnosis, or medication",
        "   - Click on a patient name or 'View' button to see their full record",
        "   - On the patient detail page, click tabs to view Vitals & Labs, Appointments, History",
        "   - Click 'Edit' to modify a patient record, fill in the form, click 'Save Changes'",
        "   - Click 'Delete' to remove a patient (with confirmation)",
        "",
        "5. IMPORTANT — After EACH significant action, call the matching audit tool to sign it:",
        "   - audit_search(query) — after searching for patients",
        "   - audit_view(patient_id, patient_name) — after opening a patient record",
        "   - audit_update(patient_id, patient_name, field, old_value, new_value) — after saving changes",
        "   - audit_delete(patient_id, patient_name) — after deleting a patient",
        "   - audit_lab_review(patient_id, patient_name) — after reviewing labs/vitals",
        "   - audit_appointments(patient_id, patient_name) — after checking appointments",
        "   - audit_history(patient_id, patient_name) — after viewing change history",
        "",
        "RULES:",
        "- Always use the BROWSER to interact with the portal — click, type, scroll",
        "- Read data from what you see on the page, don't guess or hallucinate values",
        "- Note old values BEFORE making edits so you can report them accurately in audit_update",
        "- Sign every meaningful action into the audit chain",
        "- When updating medications, type the FULL medication list (all meds, not just the changed one)",
    ]

    # Add recalled memories if available
    mem_status = memory_status()
    if mem_status["status"] == "active":
        memories = await recall_context(agent_id, task, limit=3)
        if memories:
            parts.append(f"\n--- Recalled Context (from past sessions) ---\n{memories}\n---")

    return "\n".join(parts)


# ──────────────────────────── Auditing Agent (no browser) ────────────────────

async def run_audit_agent(broadcast_fn: Optional[Callable[[dict], Awaitable]] = None):
    """Auditing agent — verifies chain integrity, checks for anomalies.
    Runs without browser-use (pure data checks)."""
    agent_id = "auditor"
    findings = []

    if broadcast_fn:
        await broadcast_fn({"type": "agent_start", "agent_name": "AUDITOR", "task": "Data integrity audit"})

    # 1. Verify chain integrity
    chain_status = await verify_chain()
    action = await sign_action("AUDIT", {
        "check": "chain_integrity",
        "intact": chain_status["intact"],
        "total_actions": chain_status["total_actions"],
    }, agent_id=agent_id)
    if broadcast_fn:
        await broadcast_fn({"type": "action", **action})

    if chain_status["intact"]:
        findings.append(f"Chain integrity: PASSED ({chain_status['total_actions']} actions verified)")
    else:
        findings.append(f"Chain integrity: FAILED at block {chain_status.get('broken_at')} — {chain_status.get('error')}")

    # 2. Check for suspicious patterns
    log = await get_full_log()
    delete_count = sum(1 for a in log if a["action_type"] == "DELETE")
    update_count = sum(1 for a in log if a["action_type"] == "UPDATE")
    failed_count = sum(1 for a in log if not a["verified"])
    agents_seen = list(set(a["agent_id"] for a in log))

    if delete_count > 3:
        findings.append(f"WARNING: {delete_count} deletions detected — elevated risk")
    if failed_count > 0:
        findings.append(f"CRITICAL: {failed_count} failed verifications — potential tampering")
    if update_count > 10:
        findings.append(f"NOTE: {update_count} updates — high modification activity")

    action = await sign_action("AUDIT", {
        "check": "pattern_analysis",
        "deletes": delete_count,
        "updates": update_count,
        "failed_verifications": failed_count,
        "agents": agents_seen,
    }, agent_id=agent_id)
    if broadcast_fn:
        await broadcast_fn({"type": "action", **action})

    # 3. Check patient data consistency
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM patients WHERE deleted = 0")
        patients = [dict(r) for r in await cursor.fetchall()]

    issues = []
    for p in patients:
        if not p.get("medications"):
            issues.append(f"Patient {p['first_name']} {p['last_name']} has no medications listed")
        if not p.get("phone"):
            issues.append(f"Patient {p['first_name']} {p['last_name']} missing phone number")
        if not p.get("emergency_contact"):
            issues.append(f"Patient {p['first_name']} {p['last_name']} missing emergency contact")

    if issues:
        findings.extend([f"DATA: {i}" for i in issues[:5]])

    action = await sign_action("AUDIT", {
        "check": "data_completeness",
        "patients_checked": len(patients),
        "issues_found": len(issues),
    }, agent_id=agent_id)
    if broadcast_fn:
        await broadcast_fn({"type": "action", **action})

    # 4. Store and complete
    audit_summary = "\n".join(findings)
    await store_interaction(agent_id, "AUDIT", {"summary": audit_summary}, audit_summary)

    complete_action = await sign_action("TASK_COMPLETE", {
        "task": "Data integrity audit",
        "result": audit_summary,
    }, agent_id=agent_id)
    if broadcast_fn:
        await broadcast_fn({"type": "action", **complete_action})
        await broadcast_fn({
            "type": "task_complete",
            "result": audit_summary,
            "agent_name": "AUDITOR",
            "summary": {
                "total_actions": 4,
                "patients_touched": len(patients),
                "elapsed_seconds": 0,
                "task": "Data integrity audit",
                "findings": findings,
            },
        })

    return findings


# ──────────────────────────── Single Agent Runner ────────────────────────────

async def run_agent_task(
    task: str,
    broadcast_fn: Optional[Callable[[dict], Awaitable]] = None,
    agent_name: str = "MedLedger Agent",
    api_key: str = None,
):
    """Run a browser-use agent that navigates the patient portal."""
    if not HAS_BROWSER_USE:
        raise ImportError("browser-use and langchain-anthropic are required. Run: pip install browser-use langchain-anthropic")

    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key

    agent_id = agent_name.lower().replace(" ", "-")
    start_time = time.time()
    action_count = [0]
    patients_touched = set()

    if broadcast_fn:
        await broadcast_fn({"type": "agent_start", "agent_name": agent_name, "task": task})

    controller = Controller()
    register_audit_tools(controller, agent_id, broadcast_fn, action_count, patients_touched)

    llm = ChatAnthropic(model_name="claude-sonnet-4-20250514", timeout=120, stop=None)
    browser_session = BrowserSession(headless=True, disable_security=True)

    system_msg = await _build_system_prompt(agent_name, task, agent_id)

    agent = Agent(
        task=task,
        llm=llm,
        controller=controller,
        browser_session=browser_session,
        extend_system_message=system_msg,
        use_vision=True,
        max_actions_per_step=5,
    )

    try:
        result = await agent.run()
        elapsed = round(time.time() - start_time, 1)

        await store_interaction(agent_id, "TASK_COMPLETE", {"task": task}, str(result)[:300])

        if broadcast_fn:
            complete_action = await sign_action("TASK_COMPLETE", {"task": task, "result": str(result)}, agent_id=agent_id)
            await broadcast_fn({"type": "action", **complete_action})
            await broadcast_fn({
                "type": "task_complete",
                "result": str(result),
                "agent_name": agent_name,
                "summary": {
                    "total_actions": action_count[0] + 1,
                    "patients_touched": len(patients_touched),
                    "elapsed_seconds": elapsed,
                    "task": task,
                },
            })
    finally:
        await browser_session.close()


# ──────────────────────────── Multi-Agent Workflow ────────────────────────────

async def run_multi_agent(
    agents_config: list[dict],
    broadcast_fn: Optional[Callable[[dict], Awaitable]] = None,
    api_key: str = None,
):
    """Run multiple agents sequentially. Each agent navigates the portal independently.
    All share one audit chain — agent B's actions link to agent A's last action."""
    if not HAS_BROWSER_USE:
        raise ImportError("browser-use and langchain-anthropic are required")

    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key

    if broadcast_fn:
        await broadcast_fn({
            "type": "multi_agent_start",
            "agents": [a["name"] for a in agents_config],
        })

    results = []
    for i, agent_conf in enumerate(agents_config):
        agent_name = agent_conf["name"]
        task = agent_conf["task"]

        if broadcast_fn:
            await broadcast_fn({
                "type": "agent_handoff",
                "from_agent": agents_config[i - 1]["name"] if i > 0 else None,
                "to_agent": agent_name,
                "step": i + 1,
                "total_steps": len(agents_config),
            })

        agent_id = agent_name.lower().replace(" ", "-")
        start_time = time.time()
        action_count = [0]
        patients_touched = set()

        if broadcast_fn:
            await broadcast_fn({"type": "agent_start", "agent_name": agent_name, "task": task})

        controller = Controller()
        register_audit_tools(controller, agent_id, broadcast_fn, action_count, patients_touched)

        llm = ChatAnthropic(model_name="claude-sonnet-4-20250514", timeout=120, stop=None)
        browser_session = BrowserSession(headless=True, disable_security=True)

        system_msg = await _build_system_prompt(agent_name, task, agent_id)

        agent = Agent(
            task=task,
            llm=llm,
            controller=controller,
            browser_session=browser_session,
            extend_system_message=system_msg,
            use_vision=True,
            max_actions_per_step=5,
        )

        try:
            result = await agent.run()
            elapsed = round(time.time() - start_time, 1)
            summary = {
                "agent_name": agent_name,
                "total_actions": action_count[0],
                "patients_touched": len(patients_touched),
                "elapsed_seconds": elapsed,
                "task": task,
            }
            results.append(summary)

            await store_interaction(agent_id, "TASK_COMPLETE", {"task": task}, str(result)[:300])

            if broadcast_fn:
                complete_action = await sign_action(
                    "TASK_COMPLETE",
                    {"task": task, "result": str(result), "agent_step": i + 1},
                    agent_id=agent_id,
                )
                await broadcast_fn({"type": "action", **complete_action})
                await broadcast_fn({"type": "task_complete", "result": str(result), "agent_name": agent_name, "summary": summary})
        finally:
            await browser_session.close()

    if broadcast_fn:
        await broadcast_fn({"type": "multi_agent_complete", "results": results})

    return results
