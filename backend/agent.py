"""
MedLedger Browser Use Agent
Clean browser-use integration with cryptographically signed tool calls.
Supports multi-agent workflows where agents can cross-sign each other's actions.
Integrates Supermemory for persistent patient interaction memory.
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
# Guarded so the rest of the backend works without browser-use installed.
# To install: pip install browser-use langchain-anthropic && playwright install chromium

try:
    from browser_use.agent.service import Agent
    from browser_use.browser.session import BrowserSession
    from browser_use.controller import Controller
    from langchain_anthropic import ChatAnthropic
    HAS_BROWSER_USE = True
except ImportError:
    HAS_BROWSER_USE = False


# ──────────────────────────── Tool Definitions ────────────────────────────

def register_tools(controller: "Controller", agent_id: str, broadcast_fn, action_count: list, patients_touched: set):
    """Register all MedLedger tools on a browser-use controller.
    Each tool signs its action into the audit chain before executing."""

    @controller.action("List all patients in the system with their basic info.")
    async def list_patients():
        action = await sign_action("SEARCH", {"query": "*all*"}, agent_id=agent_id)
        action_count[0] += 1
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, first_name, last_name, mrn, diagnosis, medications FROM patients WHERE deleted = 0 ORDER BY last_name"
            )
            result = json.dumps([dict(r) for r in await cursor.fetchall()], indent=2)
        await store_interaction(agent_id, "SEARCH", {"query": "*all*"}, result[:200])
        return result

    @controller.action("Search for a patient by name, MRN, diagnosis, or medication.")
    async def search_patient(query: str):
        action = await sign_action("SEARCH", {"query": query}, agent_id=agent_id)
        action_count[0] += 1
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            like = f"%{query}%"
            cursor = await db.execute(
                """SELECT id, first_name, last_name, mrn, diagnosis, medications
                   FROM patients
                   WHERE (first_name || ' ' || last_name LIKE ?
                       OR mrn LIKE ? OR diagnosis LIKE ? OR medications LIKE ?)
                     AND deleted = 0""",
                (like, like, like, like),
            )
            result = json.dumps([dict(r) for r in await cursor.fetchall()], indent=2)
        await store_interaction(agent_id, "SEARCH", {"query": query}, result[:200])
        return result

    @controller.action("View a patient's full record including demographics, diagnosis, medications, allergies, insurance, notes, and contact info.")
    async def view_patient(patient_id: int):
        action = await sign_action("VIEW", {"patient_id": patient_id}, agent_id=agent_id)
        action_count[0] += 1
        patients_touched.add(patient_id)
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
            row = await cursor.fetchone()
            result = json.dumps(dict(row), indent=2) if row else "Patient not found"

        # Recall past memories about this patient
        patient_name = ""
        if row:
            patient_name = f"{row['first_name']} {row['last_name']}"
        memories = await recall_patient(agent_id, patient_name=patient_name, patient_id=str(patient_id))
        await store_interaction(agent_id, "VIEW", {"patient_id": patient_id, "patient_name": patient_name}, result[:200])

        if memories:
            result += f"\n\n--- Previous Agent Interactions (from memory) ---\n{memories}"
        return result

    @controller.action(
        "Update a patient record field. field must be one of: "
        "first_name, last_name, dob, phone, insurance, allergies, diagnosis, medications, notes. "
        "value should be the complete new value for that field."
    )
    async def update_patient(patient_id: int, field: str, value: str):
        allowed = ["first_name", "last_name", "dob", "phone", "insurance", "allergies", "diagnosis", "medications", "notes"]
        if field not in allowed:
            return f"Field '{field}' not updatable. Allowed: {allowed}"
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM patients WHERE id = ? AND deleted = 0", (patient_id,))
            old = await cursor.fetchone()
            if not old:
                return "Patient not found"
            old_value = old[field] or ""
            patient_name = f"{old['first_name']} {old['last_name']}"

            # Medication safety checks
            warnings = []
            if field == "medications":
                # Check allergy conflicts
                allergy_result = check_allergy(old["allergies"] or "", value)
                if allergy_result and allergy_result.get("conflict"):
                    if broadcast_fn:
                        await broadcast_fn({"type": "interaction_alert", "severity": "CRITICAL",
                                            "message": f"ALLERGY CONFLICT: {patient_name} is allergic to {allergy_result['allergen']} — {allergy_result['medication']} is contraindicated"})
                    return f"BLOCKED: Allergy conflict — {allergy_result['description']}. Requires human override."

                # Check drug interactions
                interactions = check_interactions(old["medications"] or "", value)
                for ix in interactions:
                    if ix["severity"] == "CRITICAL":
                        if broadcast_fn:
                            await broadcast_fn({"type": "interaction_alert", "severity": "CRITICAL",
                                                "message": f"DRUG INTERACTION: {ix['drug_a']} + {ix['drug_b']} — {ix['description']}"})
                        return f"BLOCKED: Critical interaction — {ix['description']}. Requires human override."
                    else:
                        warnings.append(f"{ix['severity']}: {ix['drug_a']} + {ix['drug_b']} — {ix['description']}")
                        if broadcast_fn:
                            await broadcast_fn({"type": "interaction_alert", "severity": ix["severity"],
                                                "message": f"Drug interaction: {ix['drug_a']} + {ix['drug_b']} — {ix['description']}"})

                # Check dosage safety
                dosage_issues = check_medication_string(value)
                for d in dosage_issues:
                    if not d.get("safe", True):
                        if broadcast_fn:
                            await broadcast_fn({"type": "interaction_alert", "severity": d.get("severity", "HIGH"),
                                                "message": f"Dosage warning: {d['warning']}"})
                        if d.get("severity") == "CRITICAL":
                            return f"BLOCKED: {d['warning']}. Requires human override."
                    warnings.append(d["warning"])

            payload = {
                "patient_id": patient_id,
                "field": field,
                "old_value": old_value,
                "new_value": value,
                "patient_name": patient_name,
                "warnings": warnings if warnings else None,
            }
            action = await sign_action("UPDATE", payload, agent_id=agent_id)
            action_count[0] += 1
            patients_touched.add(patient_id)
            if broadcast_fn:
                await broadcast_fn({"type": "action", **action})
            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                """INSERT INTO patient_history
                   (patient_id, first_name, last_name, dob, mrn, diagnosis, medications,
                    allergies, last_visit, phone, insurance, change_type, changed_at,
                    changed_field, old_value, new_value)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,'UPDATE',?,?,?,?)""",
                (patient_id, old['first_name'], old['last_name'], old['dob'], old['mrn'],
                 old['diagnosis'], old['medications'], old['allergies'], old['last_visit'],
                 old['phone'], old['insurance'], now, field, old_value, value),
            )
            await db.execute(f"UPDATE patients SET {field} = ? WHERE id = ?", (value, patient_id))
            await db.commit()

            # Log to care team
            await db.execute(
                "INSERT INTO care_team_log (patient_id, provider_name, provider_role, action, timestamp) VALUES (?, ?, 'agent', ?, ?)",
                (patient_id, agent_id, f"Updated {field}", now),
            )
            await db.commit()

        await store_interaction(agent_id, "UPDATE", payload)
        result = f"Updated {field} from '{old_value}' to '{value}'"
        if warnings:
            result += f"\nWarnings: {'; '.join(warnings)}"
        return result

    @controller.action("Delete a patient record (soft delete — preserved for audit).")
    async def delete_patient(patient_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM patients WHERE id = ? AND deleted = 0", (patient_id,))
            old = await cursor.fetchone()
            if not old:
                return "Patient not found or already deleted"
            payload = {
                "patient_id": patient_id,
                "patient_name": f"{old['first_name']} {old['last_name']}",
                "mrn": old["mrn"],
            }
            action = await sign_action("DELETE", payload, agent_id=agent_id)
            action_count[0] += 1
            patients_touched.add(patient_id)
            if broadcast_fn:
                await broadcast_fn({"type": "action", **action})
            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                """INSERT INTO patient_history
                   (patient_id, first_name, last_name, dob, mrn, diagnosis, medications,
                    allergies, last_visit, phone, insurance, change_type, changed_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,'DELETE',?)""",
                (patient_id, old['first_name'], old['last_name'], old['dob'], old['mrn'],
                 old['diagnosis'], old['medications'], old['allergies'], old['last_visit'],
                 old['phone'], old['insurance'], now),
            )
            await db.execute("UPDATE patients SET deleted = 1, deleted_at = ? WHERE id = ?", (now, patient_id))
            await db.commit()
        await store_interaction(agent_id, "DELETE", payload)
        return f"Deleted {old['first_name']} {old['last_name']}"

    @controller.action("Get the full version history for a patient — all past changes with timestamps.")
    async def get_patient_history(patient_id: int):
        action = await sign_action("HISTORY", {"patient_id": patient_id}, agent_id=agent_id)
        action_count[0] += 1
        patients_touched.add(patient_id)
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM patient_history WHERE patient_id = ? ORDER BY changed_at DESC",
                (patient_id,),
            )
            rows = [dict(r) for r in await cursor.fetchall()]
        result = json.dumps(rows, indent=2) if rows else "No history found"
        await store_interaction(agent_id, "HISTORY", {"patient_id": patient_id}, result[:200])
        return result

    @controller.action("Recall what you or other agents know about a patient from previous sessions (uses long-term memory).")
    async def recall_memory(query: str):
        """Query supermemory for past interactions."""
        memories = await recall_context(agent_id, query)
        if not memories:
            return "No relevant memories found. Supermemory may not be configured."
        return f"Memories from past sessions:\n{memories}"

    @controller.action("Review lab results for a patient and flag abnormal values.")
    async def review_labs(patient_id: int):
        action = await sign_action("LAB_REVIEW", {"patient_id": patient_id}, agent_id=agent_id)
        action_count[0] += 1
        patients_touched.add(patient_id)
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM lab_results WHERE patient_id = ? ORDER BY resulted_at DESC", (patient_id,)
            )
            labs = [dict(r) for r in await cursor.fetchall()]
        if not labs:
            return "No lab results found for this patient."
        abnormals = [l for l in labs if l["status"] != "normal"]
        summary = f"Lab Results: {len(labs)} total, {len(abnormals)} abnormal\n"
        for l in labs:
            flag = f" ** {l['status'].upper()} **" if l["status"] != "normal" else ""
            summary += f"  {l['test_name']}: {l['value']} {l['unit']} (ref {l['reference_range_low']}-{l['reference_range_high']}){flag}\n"
        if abnormals and broadcast_fn:
            names = ", ".join(f"{l['test_name']} {l['status']}" for l in abnormals)
            await broadcast_fn({"type": "lab_alert", "patient_id": patient_id, "abnormal_count": len(abnormals), "summary": names})
        return summary

    @controller.action("View upcoming appointments for a patient.")
    async def view_appointments(patient_id: int):
        action = await sign_action("APPOINTMENTS", {"patient_id": patient_id}, agent_id=agent_id)
        action_count[0] += 1
        patients_touched.add(patient_id)
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM appointments WHERE patient_id = ? ORDER BY scheduled_for ASC", (patient_id,)
            )
            rows = [dict(r) for r in await cursor.fetchall()]
        return json.dumps(rows, indent=2) if rows else "No appointments found."

    @controller.action("Schedule a follow-up appointment for a patient.")
    async def schedule_appointment(patient_id: int, appointment_type: str, days_from_now: int, doctor: str):
        from datetime import timedelta
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT first_name, last_name FROM patients WHERE id = ?", (patient_id,))
            p = await cursor.fetchone()
            if not p:
                return "Patient not found"
            patient_name = f"{p['first_name']} {p['last_name']}"
            scheduled_for = (datetime.now(timezone.utc) + timedelta(days=days_from_now)).isoformat()
            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                """INSERT INTO appointments (patient_id, patient_name, doctor_name, appointment_type, scheduled_for, duration_minutes, status, notes, created_at, created_by)
                   VALUES (?, ?, ?, ?, ?, 30, 'scheduled', '', ?, ?)""",
                (patient_id, patient_name, doctor, appointment_type, scheduled_for, now, agent_id),
            )
            await db.commit()
        action = await sign_action("SCHEDULE", {"patient_id": patient_id, "patient_name": patient_name, "type": appointment_type, "doctor": doctor, "days_from_now": days_from_now}, agent_id=agent_id)
        action_count[0] += 1
        patients_touched.add(patient_id)
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        return f"Scheduled {appointment_type} with {doctor} for {patient_name} in {days_from_now} days"

    @controller.action("Review high risk patients — patients with CRITICAL or HIGH risk scores.")
    async def review_high_risk_patients():
        action = await sign_action("RISK_REVIEW", {"query": "high_risk"}, agent_id=agent_id)
        action_count[0] += 1
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM patients WHERE deleted = 0")
            patients = [dict(r) for r in await cursor.fetchall()]
        results = []
        for p in patients:
            risk = calculate_patient_risk(p)
            if risk["risk_level"] in ("CRITICAL", "HIGH"):
                results.append(f"{p['first_name']} {p['last_name']} (MRN: {p['mrn']}): {risk['risk_level']} (score {risk['score']}) — {', '.join(risk['factors'])}")
        if not results:
            return "No high risk patients identified."
        return "High Risk Patients:\n" + "\n".join(results)

    @controller.action("Check care team status for a patient — who has accessed the record recently.")
    async def check_care_team(patient_id: int):
        action = await sign_action("CARE_TEAM", {"patient_id": patient_id}, agent_id=agent_id)
        action_count[0] += 1
        patients_touched.add(patient_id)
        if broadcast_fn:
            await broadcast_fn({"type": "action", **action})
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM care_team_log WHERE patient_id = ? ORDER BY timestamp DESC LIMIT 20", (patient_id,)
            )
            rows = [dict(r) for r in await cursor.fetchall()]
        if not rows:
            return "No care team activity recorded for this patient."
        providers = set()
        agent_only = True
        for r in rows:
            providers.add(f"{r['provider_name']} ({r['provider_role']})")
            if r["provider_role"] != "agent":
                agent_only = False
        summary = f"Care team ({len(providers)} members): " + ", ".join(providers)
        if agent_only:
            summary += "\nWARNING: Only agent activity — no human provider has accessed this record recently."
        return summary


# ──────────────────────────── System Prompt Builder ────────────────────────────

async def _build_system_prompt(agent_name: str, task: str, agent_id: str, step: int = 0, total_steps: int = 0) -> str:
    """Build a context-rich system prompt, optionally with recalled memories."""
    parts = []

    if step > 0:
        parts.append(f"You are {agent_name}, step {step} of {total_steps} in a multi-agent workflow.")
    else:
        parts.append(f"You are {agent_name}, an AI medical records assistant.")

    parts.append(
        "You have tools to search, view, update, delete patients and check history. "
        "Use the tools directly — do NOT try to navigate the browser UI. "
        "When updating medications, set the FULL medication string (all meds, not just the changed one). "
        "View a patient first before updating so you know current values. Confirm what you did."
    )

    # Recall relevant memories from supermemory
    mem_status = memory_status()
    if mem_status["status"] == "active":
        memories = await recall_context(agent_id, task, limit=3)
        if memories:
            parts.append(f"\n--- Recalled Context (from past sessions) ---\n{memories}\n--- End Recalled Context ---")
        parts.append("You have long-term memory. Use recall_memory to look up past interactions.")

    return " ".join(parts)


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
    """Run a single browser-use agent with cryptographically signed tool calls."""
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
    register_tools(controller, agent_id, broadcast_fn, action_count, patients_touched)

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
    finally:
        await browser_session.close()


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
        register_tools(controller, agent_id, broadcast_fn, action_count, patients_touched)

        llm = ChatAnthropic(model_name="claude-sonnet-4-20250514", timeout=120, stop=None)
        browser_session = BrowserSession(headless=True, disable_security=True)

        system_msg = await _build_system_prompt(agent_name, task, agent_id, step=i+1, total_steps=len(agents_config))

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
