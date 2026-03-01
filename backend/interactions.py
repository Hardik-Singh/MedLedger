"""
MedLedger Medication Interaction Checker
Hardcoded drug interaction database — no external API needed.
"""

import re
from typing import Optional

INTERACTIONS = {
    ("warfarin", "aspirin"): {"severity": "CRITICAL", "description": "Major bleeding risk — concurrent use contraindicated"},
    ("metformin", "alcohol"): {"severity": "HIGH", "description": "Risk of lactic acidosis"},
    ("ssri", "tramadol"): {"severity": "HIGH", "description": "Serotonin syndrome risk"},
    ("lisinopril", "potassium"): {"severity": "MEDIUM", "description": "Hyperkalemia risk — monitor levels"},
    ("adderall", "maoi"): {"severity": "CRITICAL", "description": "Hypertensive crisis risk — do not combine"},
    ("warfarin", "ibuprofen"): {"severity": "CRITICAL", "description": "Severely increased bleeding risk"},
    ("metformin", "contrast"): {"severity": "HIGH", "description": "Hold metformin before contrast procedures"},
    ("apixaban", "aspirin"): {"severity": "HIGH", "description": "Increased bleeding risk"},
    ("sertraline", "tramadol"): {"severity": "HIGH", "description": "Serotonin syndrome risk"},
    ("levothyroxine", "calcium"): {"severity": "MEDIUM", "description": "Calcium reduces levothyroxine absorption — separate by 4 hours"},
    ("ibuprofen", "naproxen"): {"severity": "HIGH", "description": "Duplicate NSAID — increased GI bleeding risk"},
    ("omeprazole", "clopidogrel"): {"severity": "HIGH", "description": "Omeprazole reduces clopidogrel efficacy"},
    ("acetaminophen", "warfarin"): {"severity": "MEDIUM", "description": "May increase INR — monitor if chronic use"},
    ("ssri", "nsaid"): {"severity": "MEDIUM", "description": "Increased bleeding risk with concurrent use"},
    ("metoprolol", "verapamil"): {"severity": "HIGH", "description": "Severe bradycardia and heart block risk"},
    ("digoxin", "amiodarone"): {"severity": "CRITICAL", "description": "Digoxin toxicity — reduce dose by 50%"},
}

# SSRI class members for matching
SSRI_DRUGS = {"sertraline", "fluoxetine", "paroxetine", "citalopram", "escitalopram", "fluvoxamine"}
NSAID_DRUGS = {"ibuprofen", "naproxen", "celecoxib", "meloxicam", "diclofenac", "indomethacin", "ketorolac"}

ALLERGY_DRUG_CLASSES = {
    "penicillin": ["amoxicillin", "ampicillin", "piperacillin", "nafcillin", "penicillin"],
    "sulfa": ["sulfamethoxazole", "sulfadiazine", "furosemide", "hydrochlorothiazide"],
    "sulfa drugs": ["sulfamethoxazole", "sulfadiazine", "furosemide", "hydrochlorothiazide"],
    "codeine": ["codeine", "hydrocodone", "oxycodone"],
    "aspirin": ["aspirin", "ibuprofen", "naproxen", "celecoxib"],
    "nsaids": ["aspirin", "ibuprofen", "naproxen", "celecoxib", "meloxicam", "diclofenac"],
    "iodine contrast": ["iodine", "contrast"],
    "latex": [],
}


def _normalize(med: str) -> str:
    """Normalize a medication string to a base drug name."""
    med = med.lower().strip()
    # Strip dosage and frequency info
    med = re.sub(r'\d+\s*(mg|mcg|ml|iu|units?)\b.*', '', med).strip()
    # Strip common suffixes
    for suffix in [" tablets", " capsules", " cream", " gel", " spray", " drops", " solution", " er", " xr", " sr", " prn", " daily", " bid", " tid", " qid"]:
        med = med.replace(suffix, "")
    return med.strip()


def _parse_medications(med_string: str) -> list[str]:
    """Parse a medication string into individual drug names."""
    meds = []
    for part in re.split(r'[,;]\s*', med_string):
        name = _normalize(part)
        if name and len(name) > 1:
            meds.append(name)
    return meds


def _get_drug_class(drug: str) -> Optional[str]:
    """Check if a drug belongs to a class."""
    if drug in SSRI_DRUGS:
        return "ssri"
    if drug in NSAID_DRUGS:
        return "nsaid"
    return None


def check_interactions(current_medications: str, new_medication: str) -> list[dict]:
    """Check for interactions between current meds and a new medication."""
    current = _parse_medications(current_medications)
    new_drug = _normalize(new_medication)
    new_class = _get_drug_class(new_drug)

    results = []
    for curr in current:
        curr_class = _get_drug_class(curr)

        # Check direct interaction
        for (drug_a, drug_b), info in INTERACTIONS.items():
            # Check both orderings and class-based matching
            matches = False
            if (curr == drug_a and new_drug == drug_b) or (curr == drug_b and new_drug == drug_a):
                matches = True
            elif curr_class and ((curr_class == drug_a and new_drug == drug_b) or (new_drug == drug_a and curr_class == drug_b)):
                matches = True
            elif new_class and ((curr == drug_a and new_class == drug_b) or (new_class == drug_a and curr == drug_b)):
                matches = True

            if matches:
                results.append({
                    "drug_a": curr,
                    "drug_b": new_drug,
                    "severity": info["severity"],
                    "description": info["description"],
                })

    return results


def check_allergy(patient_allergies: str, new_medication: str) -> Optional[dict]:
    """Check if a medication conflicts with patient allergies."""
    if not patient_allergies or patient_allergies.lower() in ("none known", "nkda", "none", ""):
        return None

    new_drug = _normalize(new_medication)
    allergies = [a.strip().lower() for a in re.split(r'[,;]\s*', patient_allergies)]

    for allergy in allergies:
        # Direct match
        if allergy in new_drug or new_drug in allergy:
            return {
                "conflict": True,
                "allergen": allergy,
                "medication": new_drug,
                "description": f"Patient has documented {allergy} allergy — {new_drug} is contraindicated",
            }
        # Class-based match
        class_drugs = ALLERGY_DRUG_CLASSES.get(allergy, [])
        if new_drug in class_drugs:
            return {
                "conflict": True,
                "allergen": allergy,
                "medication": new_drug,
                "description": f"Patient allergic to {allergy} — {new_drug} is in the same drug class",
            }

    return None


def check_current_allergy_conflicts(allergies: str, medications: str) -> list[dict]:
    """Check all current medications against allergies."""
    if not allergies or allergies.lower() in ("none known", "nkda", "none", ""):
        return []

    meds = _parse_medications(medications)
    conflicts = []
    for med in meds:
        result = check_allergy(allergies, med)
        if result:
            conflicts.append(result)
    return conflicts
