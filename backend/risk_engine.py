"""
MedLedger Patient Risk Stratification Engine
Calculates risk scores based on conditions, medications, age, and activity.
"""

import re
from datetime import datetime, timezone
from typing import Optional

import aiosqlite
from backend.database import DB_PATH


def _calculate_age(dob_str: str) -> int:
    """Calculate age from DOB string."""
    try:
        dob = datetime.strptime(dob_str, "%Y-%m-%d")
        today = datetime.now()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception:
        return 0


def _count_medications(med_string: str) -> int:
    """Count the number of medications in a medication string."""
    if not med_string:
        return 0
    return len([m for m in re.split(r'[,;]\s*', med_string) if m.strip()])


def calculate_patient_risk(patient: dict, recent_updates: int = 0) -> dict:
    """Calculate risk score for a patient."""
    score = 0
    factors = []

    age = _calculate_age(patient.get("dob", ""))
    diagnosis = (patient.get("diagnosis", "") or "").lower()
    medications = patient.get("medications", "") or ""
    allergies = (patient.get("allergies", "") or "").lower()
    med_count = _count_medications(medications)

    # Age factors
    if age > 75:
        score += 3
        factors.append("Advanced age (>75)")
    elif age > 60:
        score += 1
        factors.append("Older adult (>60)")

    # Condition factors
    if "diabetes" in diagnosis or "diabetic" in diagnosis:
        score += 2
        factors.append("Diabetic")
    if "atrial fibrillation" in diagnosis or "afib" in diagnosis:
        score += 3
        factors.append("Afib — stroke risk")
    if "hypertension" in diagnosis:
        score += 1
        factors.append("Hypertensive")
    if "tumor" in diagnosis or "cancer" in diagnosis or "oncology" in diagnosis:
        score += 4
        factors.append("Oncology patient")
    if "heart failure" in diagnosis or "chf" in diagnosis:
        score += 3
        factors.append("Heart failure")
    if "copd" in diagnosis:
        score += 2
        factors.append("COPD")
    if "renal" in diagnosis or "kidney" in diagnosis:
        score += 2
        factors.append("Renal impairment")

    # Medication count (polypharmacy risk)
    if med_count > 5:
        score += 2
        factors.append(f"Polypharmacy ({med_count} medications)")
    elif med_count > 3:
        score += 1
        factors.append(f"Multiple medications ({med_count})")

    # Allergy flags
    if allergies and allergies not in ("none known", "nkda", "none", ""):
        score += 1
        factors.append("Known allergies on file")

    # Recent activity
    if recent_updates > 5:
        score += 2
        factors.append("Frequent recent record changes")
    elif recent_updates > 2:
        score += 1
        factors.append("Recent record changes")

    # Determine risk level
    if score >= 8:
        risk_level = "CRITICAL"
    elif score >= 5:
        risk_level = "HIGH"
    elif score >= 3:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "risk_level": risk_level,
        "score": score,
        "factors": factors,
        "age": age,
    }


RISK_COLORS = {
    "CRITICAL": "#ef4444",
    "HIGH": "#f59e0b",
    "MEDIUM": "#eab308",
    "LOW": "#22c55e",
}


async def get_all_patient_risks() -> list[dict]:
    """Calculate risk scores for all active patients."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM patients WHERE deleted = 0")
        patients = [dict(r) for r in await cursor.fetchall()]

    results = []
    for p in patients:
        risk = calculate_patient_risk(p)
        results.append({
            "patient_id": p["id"],
            "patient_name": f"{p['first_name']} {p['last_name']}",
            **risk,
        })

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results
