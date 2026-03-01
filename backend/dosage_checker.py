"""
MedLedger Drug Dosage Safety Checker
Verifies medication dosages are within safe bounds.
"""

import re
from typing import Optional

DOSAGE_BOUNDS = {
    "metformin": {"min_mg": 500, "max_mg": 2550, "max_renal_impaired_mg": 1000, "unit": "mg/day"},
    "lisinopril": {"min_mg": 5, "max_mg": 40, "unit": "mg/day"},
    "adderall": {"min_mg": 5, "max_mg": 60, "max_elderly_mg": 20, "unit": "mg/day"},
    "atorvastatin": {"min_mg": 10, "max_mg": 80, "unit": "mg/day"},
    "sertraline": {"min_mg": 25, "max_mg": 200, "unit": "mg/day"},
    "apixaban": {"min_mg": 2.5, "max_mg": 10, "unit": "mg twice daily"},
    "metoprolol": {"min_mg": 12.5, "max_mg": 200, "unit": "mg/day"},
    "levothyroxine": {"min_mcg": 25, "max_mcg": 200, "unit": "mcg/day"},
    "ozempic": {"min_mg": 0.25, "max_mg": 2.0, "unit": "mg/week"},
    "ambien": {"min_mg": 5, "max_mg": 10, "max_elderly_mg": 5, "unit": "mg"},
    "ibuprofen": {"min_mg": 200, "max_mg": 3200, "max_elderly_mg": 1200, "unit": "mg/day"},
    "naproxen": {"min_mg": 220, "max_mg": 1500, "max_elderly_mg": 660, "unit": "mg/day"},
    "acetaminophen": {"min_mg": 325, "max_mg": 4000, "max_elderly_mg": 3000, "unit": "mg/day"},
    "omeprazole": {"min_mg": 10, "max_mg": 40, "unit": "mg/day"},
    "claritin": {"min_mg": 5, "max_mg": 10, "unit": "mg/day"},
    "zyrtec": {"min_mg": 5, "max_mg": 10, "unit": "mg/day"},
    "chlorpromazine": {"min_mg": 10, "max_mg": 800, "max_elderly_mg": 200, "unit": "mg/day"},
}


def _extract_dose(med_string: str) -> tuple[Optional[str], Optional[float], Optional[str]]:
    """Extract drug name and dosage from a medication string."""
    med_string = med_string.lower().strip()

    # Match patterns like "Ibuprofen 400mg" or "Metformin 500 mg"
    match = re.search(r'([a-z]+)\s+(\d+\.?\d*)\s*(mg|mcg|ml|iu)', med_string)
    if match:
        drug = match.group(1)
        dose = float(match.group(2))
        unit = match.group(3)
        return drug, dose, unit

    return None, None, None


def check_dosage(medication: str, dose: float = None, patient_age: int = None, unit: str = "mg") -> dict:
    """Check if a medication dosage is within safe bounds."""
    drug_name = medication.lower().strip()

    # Try to extract dose from string if not provided separately
    if dose is None:
        extracted_drug, extracted_dose, extracted_unit = _extract_dose(medication)
        if extracted_drug and extracted_dose:
            drug_name = extracted_drug
            dose = extracted_dose
            unit = extracted_unit or "mg"

    if dose is None:
        return {"safe": True, "warning": None, "checked": False}

    bounds = DOSAGE_BOUNDS.get(drug_name)
    if not bounds:
        return {"safe": True, "warning": None, "checked": False}

    is_elderly = patient_age and patient_age >= 65

    # Determine appropriate max
    if is_elderly and "max_elderly_mg" in bounds:
        max_dose = bounds["max_elderly_mg"]
        age_note = " (elderly limit)"
    else:
        max_dose = bounds.get(f"max_{unit}", bounds.get("max_mg", 9999))
        age_note = ""

    min_dose = bounds.get(f"min_{unit}", bounds.get("min_mg", 0))

    if dose > max_dose:
        return {
            "safe": False,
            "warning": f"{drug_name.title()} {dose}{unit} exceeds maximum safe dose of {max_dose}{unit}{age_note}",
            "checked": True,
            "severity": "CRITICAL",
        }

    if dose < min_dose:
        return {
            "safe": False,
            "warning": f"{drug_name.title()} {dose}{unit} below minimum therapeutic dose of {min_dose}{unit}",
            "checked": True,
            "severity": "MEDIUM",
        }

    # Near maximum warning (>80% of max)
    if dose > max_dose * 0.8:
        return {
            "safe": True,
            "warning": f"{drug_name.title()} {dose}{unit} at upper therapeutic range (max: {max_dose}{unit}{age_note})",
            "checked": True,
            "severity": "MEDIUM",
        }

    return {"safe": True, "warning": None, "checked": True}


def check_medication_string(med_string: str, patient_age: int = None) -> list[dict]:
    """Check all medications in a medication string for dosage safety."""
    results = []
    for part in re.split(r'[,;]\s*', med_string):
        drug, dose, unit = _extract_dose(part)
        if drug and dose:
            result = check_dosage(drug, dose, patient_age, unit or "mg")
            if result.get("warning"):
                result["medication"] = part.strip()
                results.append(result)
    return results
