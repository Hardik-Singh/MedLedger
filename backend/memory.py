"""
MedLedger Memory Layer — Supermemory integration for persistent agent memory.
Agents store and recall patient interactions across sessions using container_tags
for per-patient memory isolation.

SDK: pip install supermemory (v3.27+)
API Key: https://console.supermemory.ai
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

try:
    from supermemory import AsyncSupermemory
    HAS_SUPERMEMORY = True
except ImportError:
    HAS_SUPERMEMORY = False

_client: Optional[object] = None


def get_client():
    """Get or create the async supermemory client."""
    global _client
    key = os.environ.get("SUPERMEMORY_API_KEY", "")
    if not key or not HAS_SUPERMEMORY:
        return None
    if _client is None:
        _client = AsyncSupermemory(api_key=key)
    return _client


def reset_client():
    """Reset the client (e.g. after key change)."""
    global _client
    _client = None


async def store_interaction(agent_id: str, action_type: str, payload: dict, result: str = ""):
    """Store a patient interaction as a memory.
    Uses container_tags for per-patient isolation and metadata for filtering."""
    client = get_client()
    if not client:
        return None

    patient_name = payload.get("patient_name", "")
    patient_id = payload.get("patient_id", "")
    field = payload.get("field", "")
    query = payload.get("query", "")

    # Build a human-readable memory
    if action_type == "SEARCH":
        content = f"Agent {agent_id} searched for: {query}. {result}"
    elif action_type == "VIEW":
        content = f"Agent {agent_id} viewed patient #{patient_id} ({patient_name}). {result}"
    elif action_type == "UPDATE":
        old_val = payload.get("old_value", "")
        new_val = payload.get("new_value", "")
        content = f"Agent {agent_id} updated {patient_name}'s {field} from '{old_val}' to '{new_val}'"
    elif action_type == "DELETE":
        content = f"Agent {agent_id} deleted patient {patient_name} ({payload.get('mrn', '')})"
    elif action_type == "HISTORY":
        content = f"Agent {agent_id} reviewed history for patient #{patient_id}. {result}"
    elif action_type == "TASK_COMPLETE":
        content = f"Agent {agent_id} completed task: {payload.get('task', '')}. Result: {result[:200]}"
    elif action_type == "AUDIT":
        content = f"Auditor checked: {payload.get('check', '')}. {payload.get('summary', '')[:200]}"
    else:
        content = f"Agent {agent_id} performed {action_type}: {json.dumps(payload)[:200]}"

    # Build container tags for isolation
    tags = ["medledger"]
    if patient_id:
        tags.append(f"patient_{patient_id}")
    if agent_id:
        tags.append(f"agent_{agent_id}")

    try:
        await client.add(
            content=content,
            container_tags=tags,
            metadata={
                "category": action_type.lower(),
                "agent_id": agent_id,
                "patient_id": str(patient_id),
                "patient_name": patient_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        return True
    except Exception:
        return False


async def recall_patient(agent_id: str, patient_name: str = "", patient_id: str = "", limit: int = 5) -> str:
    """Recall memories about a patient from past sessions.
    Uses search.memories() with container_tag for per-patient isolation."""
    client = get_client()
    if not client:
        return ""

    query = f"patient {patient_name}" if patient_name else f"patient #{patient_id}"
    tag = f"patient_{patient_id}" if patient_id else "medledger"

    try:
        results = await client.search.memories(
            q=f"{query} medical record interactions history",
            container_tag=tag,
            limit=limit,
        )
        if not results or not hasattr(results, "results") or not results.results:
            return ""
        memories = []
        for r in results.results:
            content = getattr(r, "content", "") or getattr(r, "text", "") or str(r)
            memories.append(f"- {content}")
        return "\n".join(memories)
    except Exception:
        return ""


async def recall_context(agent_id: str, task: str, limit: int = 5) -> str:
    """Recall relevant memories for a given task.
    Uses search.documents() for broad context across all patients."""
    client = get_client()
    if not client:
        return ""

    try:
        results = await client.search.documents(
            q=task,
            container_tags=["medledger"],
            limit=limit,
            include_summary=True,
        )
        if not results or not hasattr(results, "results") or not results.results:
            return ""
        memories = []
        for r in results.results:
            content = getattr(r, "summary", "") or getattr(r, "content", "") or getattr(r, "text", "") or str(r)
            memories.append(f"- {content}")
        return "\n".join(memories)
    except Exception:
        return ""


async def get_patient_profile(patient_id: str) -> dict:
    """Get supermemory profile for a patient — static facts + dynamic context.
    Uses client.profile() with container_tag for patient-level profile."""
    client = get_client()
    if not client:
        return {}

    try:
        result = await client.profile(
            container_tag=f"patient_{patient_id}",
            q="medical history medications allergies diagnosis",
        )
        profile_data = {}
        if hasattr(result, "profile"):
            if hasattr(result.profile, "static"):
                profile_data["static_facts"] = result.profile.static
            if hasattr(result.profile, "dynamic"):
                profile_data["recent_context"] = result.profile.dynamic
        return profile_data
    except Exception:
        return {}


def memory_status() -> dict:
    """Check if supermemory is configured and available."""
    key = os.environ.get("SUPERMEMORY_API_KEY", "")
    has_key = bool(key and len(key) > 5)
    return {
        "sdk_installed": HAS_SUPERMEMORY,
        "has_key": has_key,
        "key_preview": f"{key[:8]}...{key[-4:]}" if has_key and len(key) > 12 else None,
        "status": "active" if HAS_SUPERMEMORY and has_key else "inactive",
    }
