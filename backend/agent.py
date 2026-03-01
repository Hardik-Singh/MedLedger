"""
MedLedger Browser Use Agent
Browser-use agent that navigates the patient portal with real clicks.
Actions are cryptographically signed into the audit chain as the agent works.
Supports multi-agent workflows and Supermemory for persistent memory.
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Callable, Awaitable, Optional

import aiosqlite
from backend.database import DB_PATH
from backend.audit_chain import sign_action, verify_chain, get_full_log
from backend.memory import store_interaction, recall_patient, recall_context, memory_status
from backend.interactions import check_interactions, check_allergy
from backend.dosage_checker import check_medication_string
from backend.risk_engine import calculate_patient_risk

# ──────────────────────────── Browser Use imports ────────────────────────────

try:
    from browser_use.agent.service import Agent
    from browser_use.browser.session import BrowserSession
    from browser_use.controller import Controller
    from browser_use.llm.anthropic.chat import ChatAnthropic
    HAS_BROWSER_USE = True
except ImportError:
    HAS_BROWSER_USE = False

PORTAL_URL = os.getenv("PORTAL_URL", "http://localhost:8001")


# ──────────────────────────── Audit-Signing Tools ────────────────────────────

def register_audit_tools(controller: "Controller", agent_id: str, broadcast_fn, action_count: list, patients_touched: set):
    """Register lightweight audit-signing tools on the controller.
    These sign actions into the chain WITHOUT bypassing the browser — the agent
    still navigates the portal UI, but calls these to create audit records."""

    @controller.action(
        "Sign a SEARCH action into the audit chain. Call this AFTER you search in the portal UI. "
        "query: the search term you used."
    )
    async def audit_search(query: str):
        action = await sign_action("SEARCH", {"query": query}, agent_id=agent_id)
        action_count[0] += 1
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        await store_interaction(agent_id, "SEARCH", {"query": query})
        return f"Audit: search for '{query}' signed to chain"

    @controller.action(
        "Sign a VIEW action into the audit chain. Call this AFTER you view a patient in the portal UI. "
        "patient_name: the patient's full name you viewed."
    )
    async def audit_view(patient_name: str):
        # look up id
        pid = None
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            like = f"%{patient_name}%"
            cur = await db.execute(
                "SELECT id FROM patients WHERE (first_name || ' ' || last_name LIKE ?) AND deleted = 0", (like,)
            )
            row = await cur.fetchone()
            if row:
                pid = row["id"]
                patients_touched.add(pid)
        action = await sign_action("VIEW", {"patient_id": pid, "patient_name": patient_name}, agent_id=agent_id)
        action_count[0] += 1
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        await store_interaction(agent_id, "VIEW", {"patient_id": pid, "patient_name": patient_name})
        return f"Audit: view of {patient_name} signed to chain"

    @controller.action(
        "Sign an UPDATE action into the audit chain. Call this AFTER you update a patient field in the portal UI. "
        "patient_name: full name, field: which field, old_value: previous value, new_value: new value."
    )
    async def audit_update(patient_name: str, field: str, old_value: str, new_value: str):
        pid = None
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            like = f"%{patient_name}%"
            cur = await db.execute(
                "SELECT id FROM patients WHERE (first_name || ' ' || last_name LIKE ?) AND deleted = 0", (like,)
            )
            row = await cur.fetchone()
            if row:
                pid = row["id"]
                patients_touched.add(pid)
        payload = {"patient_id": pid, "patient_name": patient_name, "field": field, "old_value": old_value, "new_value": new_value}
        action = await sign_action("UPDATE", payload, agent_id=agent_id)
        action_count[0] += 1
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        await store_interaction(agent_id, "UPDATE", payload)
        return f"Audit: update of {patient_name}.{field} signed to chain"

    @controller.action(
        "Sign a HISTORY action into the audit chain. Call this AFTER you view a patient's history in the portal."
    )
    async def audit_history(patient_name: str):
        pid = None
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            like = f"%{patient_name}%"
            cur = await db.execute(
                "SELECT id FROM patients WHERE (first_name || ' ' || last_name LIKE ?) AND deleted = 0", (like,)
            )
            row = await cur.fetchone()
            if row:
                pid = row["id"]
                patients_touched.add(pid)
        action = await sign_action("HISTORY", {"patient_id": pid, "patient_name": patient_name}, agent_id=agent_id)
        action_count[0] += 1
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        return f"Audit: history view of {patient_name} signed to chain"

    @controller.action(
        "Sign a LAB_REVIEW action into the audit chain. Call this AFTER you view lab results in the portal."
    )
    async def audit_labs(patient_name: str):
        pid = None
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            like = f"%{patient_name}%"
            cur = await db.execute(
                "SELECT id FROM patients WHERE (first_name || ' ' || last_name LIKE ?) AND deleted = 0", (like,)
            )
            row = await cur.fetchone()
            if row:
                pid = row["id"]
                patients_touched.add(pid)
        action = await sign_action("LAB_REVIEW", {"patient_id": pid, "patient_name": patient_name}, agent_id=agent_id)
        action_count[0] += 1
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        return f"Audit: lab review of {patient_name} signed to chain"

    @controller.action(
        "Sign an APPOINTMENTS action into the audit chain. Call this AFTER you view appointments in the portal."
    )
    async def audit_appointments(patient_name: str):
        pid = None
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            like = f"%{patient_name}%"
            cur = await db.execute(
                "SELECT id FROM patients WHERE (first_name || ' ' || last_name LIKE ?) AND deleted = 0", (like,)
            )
            row = await cur.fetchone()
            if row:
                pid = row["id"]
                patients_touched.add(pid)
        action = await sign_action("APPOINTMENTS", {"patient_id": pid, "patient_name": patient_name}, agent_id=agent_id)
        action_count[0] += 1
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        return f"Audit: appointments view of {patient_name} signed to chain"


# ──────────────────────────── System Prompt Builder ────────────────────────────

PORTAL_SYSTEM_PROMPT = """You are {agent_name}, an AI medical records assistant.

You navigate the MedLedger Patient Portal in a real browser. The portal is already open.

HOW TO WORK:
1. You are on the portal at {portal_url}. If you see a login page, log in with username "demo" and password "demo123".
2. Use the portal UI to accomplish the task — search for patients, click their names to view records, click Edit to modify fields, etc.
3. IMPORTANT: After each significant action (search, view, update, etc.), call the corresponding audit_* tool to sign the action into the cryptographic audit chain. This is required for compliance.

AUDIT TOOLS (call these AFTER doing the action in the browser):
- audit_search(query) — after searching
- audit_view(patient_name) — after viewing a patient record
- audit_update(patient_name, field, old_value, new_value) — after editing a field
- audit_history(patient_name) — after viewing history
- audit_labs(patient_name) — after viewing lab results
- audit_appointments(patient_name) — after viewing appointments

RULES:
- Navigate the portal using clicks, form inputs, and links — this is visible to the user watching.
- Always call the audit tool after performing the corresponding browser action.
- When updating medications, make sure to set the FULL medication string.
- View a patient first before updating so you know current values.
- Focus ONLY on what the user asked. Do not take extra actions.
- When done, stop immediately.
"""


async def _build_system_prompt(agent_name: str, task: str, agent_id: str, step: int = 0, total_steps: int = 0) -> str:
    """Build system prompt for portal-navigating agent."""
    prompt = PORTAL_SYSTEM_PROMPT.format(agent_name=agent_name, portal_url=PORTAL_URL)

    if step > 0:
        prompt = prompt.replace(
            f"You are {agent_name}, an AI medical records assistant.",
            f"You are {agent_name}, step {step} of {total_steps} in a multi-agent workflow.",
        )

    # Recall relevant memories from supermemory
    mem_status = memory_status()
    if mem_status["status"] == "active":
        memories = await recall_context(agent_id, task, limit=3)
        if memories:
            prompt += f"\n--- Recalled Context (from past sessions) ---\n{memories}\n--- End Recalled Context ---"

    return prompt


# ──────────────────────────── Auditing Agent ────────────────────────────

async def run_audit_agent(broadcast_fn: Optional[Callable[[dict], Awaitable]] = None):
    """
    Auditing agent — verifies chain integrity, checks for anomalies,
    and stores findings in memory. Runs without browser-use.
    """
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

    # 2. Check for suspicious patterns in audit log
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

    # 4. Store audit findings in memory
    audit_summary = "\n".join(findings)
    await store_interaction(agent_id, "AUDIT", {"summary": audit_summary}, audit_summary)

    # 5. Complete
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
    """Run a browser-use agent that navigates the patient portal with real clicks."""
    if not HAS_BROWSER_USE:
        raise ImportError("Agent deps not installed: browser-use and langchain-anthropic are required. Run: pip install browser-use langchain-anthropic")

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

    llm = ChatAnthropic(model="claude-sonnet-4-20250514", timeout=120)

    system_msg = await _build_system_prompt(agent_name, task, agent_id)

    browser_session = BrowserSession(
        headless=True,
        disable_security=True,
    )

    agent = Agent(
        task=f"Go to {PORTAL_URL} and complete this task: {task}",
        llm=llm,
        controller=controller,
        browser_session=browser_session,
        extend_system_message=system_msg,
        use_vision=False,
        max_actions_per_step=5,
    )

    try:
        result = await agent.run(max_steps=25)
        elapsed = round(time.time() - start_time, 1)

        # Store completion in memory
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
    except Exception as e:
        elapsed = round(time.time() - start_time, 1)
        if broadcast_fn:
            await broadcast_fn({"type": "error", "message": f"Agent error: {str(e)}", "agent_name": agent_name})
    finally:
        await browser_session.stop()


# ──────────────────────────── Multi-Agent Workflow ────────────────────────────

async def run_multi_agent(
    agents_config: list[dict],
    broadcast_fn: Optional[Callable[[dict], Awaitable]] = None,
    api_key: str = None,
):
    """
    Run multiple agents sequentially. Each agent's actions are signed with its own
    identity, but all share the same audit chain — so agent B's first action links
    to agent A's last action. This creates a cross-signed, multi-agent audit trail.

    agents_config: [{"name": "Triage Bot", "task": "..."}, {"name": "Updater Bot", "task": "..."}]
    """
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

        llm = ChatAnthropic(model="claude-sonnet-4-20250514", timeout=120)

        system_msg = await _build_system_prompt(agent_name, task, agent_id, step=i+1, total_steps=len(agents_config))

        browser_session = BrowserSession(
            headless=True,
            disable_security=True,
        )

        agent = Agent(
            task=f"Go to {PORTAL_URL} and complete this task: {task}",
            llm=llm,
            controller=controller,
            browser_session=browser_session,
            extend_system_message=system_msg,
            use_vision=False,
            max_actions_per_step=5,
        )

        try:
            result = await agent.run(max_steps=25)
        finally:
            await browser_session.stop()
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

    if broadcast_fn:
        await broadcast_fn({"type": "multi_agent_complete", "results": results})

    return results
