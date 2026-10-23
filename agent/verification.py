"""
Built with the AWS User Group Madurai Strands Decider hackathon kit

Medical Meaning Verification for Maruthuva Mozhi.

Compares a Tamil explanation against extracted clinical fields from the source
document to ensure nothing critical was dropped or altered in translation.
"""

import re


# Common Tamil transliteration patterns for drug names.
# Maps lowercase ASCII fragments to possible Tamil script substrings.
# Extend this table as real-world cases surface.
_TRANSLITERATION_HINTS: dict[str, list[str]] = {
    "amoxicillin":  ["அமாக்ஸிசிலின்", "அமாக்ஸிஸிலின்", "அமோக்ஸிசிலின்"],
    "metformin":    ["மெட்ஃபார்மின்", "மெட்ஃபோர்மின்", "மெட்ஃபார்மின"],
    "paracetamol":  ["பாராசிட்டமால்", "பாரசிட்டமால்"],
    "ibuprofen":    ["இபுபுரோஃபன்", "இப்யூபுரோஃபன்"],
    "azithromycin": ["அசித்ரோமைசின்", "அஸித்ரோமைசின்"],
    "aspirin":      ["அஸ்பிரின்", "ஆஸ்பிரின்"],
    "atorvastatin": ["அட்டோர்வாஸ்டாட்டின்", "அட்டோர்வஸ்டாடின்"],
    "omeprazole":   ["ஒமெப்ரஸோல்", "ஓமிப்ரஸோல்"],
    "cetirizine":   ["செட்டிரிசின்", "சட்டிரிஜின்"],
    "amlodipine":   ["அம்லோடிபைன்", "அம்லோடிபின்"],
}


def _drug_in_tamil(drug: str, tamil_text: str) -> bool:
    """Return True if the drug name appears verbatim (case-insensitive) or via
    a known Tamil transliteration in *tamil_text*."""
    if drug.lower() in tamil_text.lower():
        return True
    hints = _TRANSLITERATION_HINTS.get(drug.lower(), [])
    return any(hint in tamil_text for hint in hints)


def _parse_dosage(dosage_str: str) -> tuple[str, str] | tuple[None, None]:
    """Split a dosage string such as '500mg' or '10 mcg' into (numeric, unit).

    Returns (None, None) when parsing fails.
    """
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*([a-zA-Z%]+)\s*$", dosage_str.strip())
    if m:
        return m.group(1), m.group(2).lower()
    return None, None


def _dosage_verbatim_in_text(dosage_str: str, text: str) -> tuple[bool, bool]:
    """Check whether *dosage_str* appears verbatim in *text*.

    Returns (present: bool, altered: bool).
    - present=True  → the exact numeric+unit pair was found.
    - altered=True  → a *different* numeric value with the *same* unit was found
                      (possible substitution error).
    """
    number, unit = _parse_dosage(dosage_str)
    if number is None:
        # Fall back to a plain substring check when parsing fails.
        return dosage_str.lower() in text.lower(), False

    # Exact match (allow optional space between number and unit).
    exact_pattern = re.compile(
        r"\b" + re.escape(number) + r"\s*" + re.escape(unit) + r"\b",
        re.IGNORECASE,
    )
    if exact_pattern.search(text):
        return True, False

    # Check for same unit with a different number (altered dosage).
    any_unit_pattern = re.compile(
        r"\b(\d+(?:\.\d+)?)\s*" + re.escape(unit) + r"\b",
        re.IGNORECASE,
    )
    if any_unit_pattern.search(text):
        return False, True  # unit present but number differs

    return False, False


def verify_translation(
    original_text: str,
    tamil_text: str,
    clinical_fields: dict,
) -> dict:
    """Verify that a Tamil explanation faithfully preserves critical clinical
    information extracted from *original_text*.

    Parameters
    ----------
    original_text:
        The source medical document text (used for context; not deeply parsed
        here — the caller's extractor already populated *clinical_fields*).
    tamil_text:
        The Tamil explanation produced by the agent.
    clinical_fields:
        Dict with keys:
        - drug_names      : list[str]
        - dosages         : list[str]   e.g. ['500mg', '10 mcg']
        - frequencies     : list[str]   (not checked for presence; reserved)
        - durations       : list[str]   (not checked for presence; reserved)
        - dates           : list[str]
        - warnings        : list[str]
        - unreadable_sections : list[str]  (not checked; informational only)

    Returns
    -------
    dict with keys:
        passed   : bool   – True when missing and altered are both empty
        missing  : list[str]
        altered  : list[str]
        warnings : list[str]  – warnings from clinical_fields absent in tamil_text
        score    : float  0.0 – 1.0
    """
    missing: list[str] = []
    altered: list[str] = []
    total_fields = 0

    # ── 1. Drug names ────────────────────────────────────────────────────────
    for drug in clinical_fields.get("drug_names", []):
        if not drug:
            continue
        total_fields += 1
        if not _drug_in_tamil(drug, tamil_text):
            missing.append(f"drug: {drug}")

    # ── 2. Dosages ───────────────────────────────────────────────────────────
    for dosage in clinical_fields.get("dosages", []):
        if not dosage:
            continue
        total_fields += 1
        present, is_altered = _dosage_verbatim_in_text(dosage, tamil_text)
        if is_altered:
            altered.append(f"dosage: {dosage}")
        elif not present:
            missing.append(f"dosage: {dosage}")

    # ── 3. Dates ─────────────────────────────────────────────────────────────
    for date in clinical_fields.get("dates", []):
        if not date:
            continue
        total_fields += 1
        if date not in tamil_text:
            missing.append(f"date: {date}")

    # ── 4. Score ─────────────────────────────────────────────────────────────
    if total_fields == 0:
        score = 1.0
    else:
        bad = len(missing) + len(altered)
        score = max(0.0, (total_fields - bad) / total_fields)

    # ── 5. Passed ────────────────────────────────────────────────────────────
    passed = len(missing) == 0 and len(altered) == 0

    # ── 6. Warnings not communicated ─────────────────────────────────────────
    uncommunicated_warnings: list[str] = []
    for warning in clinical_fields.get("warnings", []):
        if not warning:
            continue
        # A warning should appear either verbatim or its key tokens should be
        # present. We do a simple verbatim substring check; callers that want
        # semantic matching can extend this.
        if warning not in tamil_text:
            uncommunicated_warnings.append(warning)

    return {
        "passed": passed,
        "missing": missing,
        "altered": altered,
        "warnings": uncommunicated_warnings,
        "score": round(score, 4),
    }
