"""Maruthuva Mozhi tools — extract, translate, ingest, verify, and emergency guidance.

Built with the AWS User Group Madurai Strands Decider hackathon kit.

All Tamil text is derived from TAMIL_PHRASES (phrase-level dictionary) and preserves
clinical values (medicine names, dosages, units, frequencies, durations, dates) verbatim.
No real translation API is called; no real patient data is used.
"""

from __future__ import annotations

import re
from strands import tool
from agent.verification import verify_translation


# ─────────────────────────────────────────────────────────────────────────────
# Phrase-level Tamil dictionary (40+ entries)
# Keys: lowercase English phrases/words
# Values: Tamil equivalents
# ─────────────────────────────────────────────────────────────────────────────

TAMIL_PHRASES: dict[str, str] = {
    # ── Prescription frequency ──────────────────────────────────────────────
    "once daily":            "தினமும் ஒரு வேளை",
    "twice daily":           "தினமும் இரு வேளை",
    "three times daily":     "தினமும் மூன்று வேளை",
    "thrice daily":          "தினமும் மூன்று வேளை",
    "four times daily":      "தினமும் நான்கு வேளை",
    "every 4 hours":         "ஒவ்வொரு 4 மணி நேரத்திற்கும்",
    "every 6 hours":         "ஒவ்வொரு 6 மணி நேரத்திற்கும்",
    "every 8 hours":         "ஒவ்வொரு 8 மணி நேரத்திற்கும்",
    # ── Timing relative to food ──────────────────────────────────────────────
    "before meals":          "சாப்பிடுவதற்கு முன்",
    "after meals":           "சாப்பிட்டதும்",
    "with food":             "உணவுடன்",
    "at bedtime":            "தூங்குவதற்கு முன்",
    "in the morning":        "காலையில்",
    "in the evening":        "மாலையில்",
    # ── Conditional / duration ───────────────────────────────────────────────
    "as needed":             "தேவைப்படும்போது",
    "for x days":            "X நாட்களுக்கு",
    "stop if":               "இதை நிறுத்தவும் என்றால்",
    "do not exceed":         "அதிகமாக எடுக்காதீர்கள்",
    # ── Lifestyle instructions ───────────────────────────────────────────────
    "avoid alcohol":         "மதுவை தவிர்க்கவும்",
    "complete full course":  "முழு மருந்து கோர்ஸையும் முடிக்கவும்",
    "take with water":       "தண்ணீருடன் எடுக்கவும்",
    "do not crush":          "நொறுக்காதீர்கள்",
    "do not chew":           "மெல்லாதீர்கள்",
    # ── Professional consultation ────────────────────────────────────────────
    "consult doctor":        "மருத்துவரை அணுகவும்",
    "consult pharmacist":    "மருந்தாளரை அணுகவும்",
    # ── Lab report language ──────────────────────────────────────────────────
    "normal":                "இயல்பான நிலை",
    "elevated":              "அதிகமாக உள்ளது",
    "low":                   "குறைவாக உள்ளது",
    "within range":          "எல்லைக்குள் உள்ளது",
    "above range":           "எல்லைக்கு மேல்",
    "below range":           "எல்லைக்கு கீழ்",
    "retest required":       "மீண்டும் சோதனை தேவை",
    "refer to physician":    "மருத்துவரிடம் செல்லவும்",
    # ── Discharge summary language ───────────────────────────────────────────
    "rest for":              "ஓய்வெடுக்கவும்",
    "follow up":             "தொடர் சிகிச்சை",
    "drink plenty of fluids": "நிறைய தண்ணீர் குடிக்கவும்",
    "avoid smoking":         "புகைபிடிப்பதை தவிர்க்கவும்",
    "return to emergency":   "மீண்டும் அவசர சேவைக்கு வாருங்கள்",
    # ── Warning / safety language ────────────────────────────────────────────
    "stop if rash develops": "தோல் அலர்ஜி ஏற்பட்டால் நிறுத்தவும்",
    "seek medical attention": "மருத்துவ உதவி தேடவும்",
    "call emergency":        "அவசர சேவையை அழைக்கவும் (108)",
    # ── Route of administration ──────────────────────────────────────────────
    "oral":                  "வாய் வழியாக",
    "topical":               "தோலில் தடவ",
    "injection":             "ஊசி மூலம்",
}

# Regex for drug names + dosages to preserve verbatim
_PRESERVE_PATTERN = re.compile(
    r"\b[A-Z][a-zA-Z]+(?:-[A-Z][a-zA-Z]+)?"   # Capitalised word (drug name)
    r"\s+\d+(?:\.\d+)?\s*(?:mg|mcg|ml|g|IU|units?)\b"
    r"|\b\d+(?:\.\d+)?\s*(?:mg|mcg|ml|g|IU|units?)\b"  # dosage-only token
    r"|\b\d{4}-\d{2}-\d{2}\b"                            # ISO date
    r"|\b\d{1,2}/\d{1,2}/\d{4}\b"                        # slash date
)

# Regex for clinical dosage/date strings used when building preserved_values list
_CLINICAL_VALUE_PATTERN = re.compile(
    r"\b[A-Z][a-zA-Z]+(?:-[A-Z][a-zA-Z]+)?\s+\d+(?:\.\d+)?\s*(?:mg|mcg|ml|g|IU|units?)\b"
    r"|\b\d+(?:\.\d+)?\s*(?:mg|mcg|ml|g|IU|units?)\b"
    r"|\b\d{4}-\d{2}-\d{2}\b"
    r"|\b\d{1,2}/\d{1,2}/\d{4}\b",
    re.IGNORECASE,
)


def _find_tamil_for_segment(segment: str) -> str | None:
    """Return the Tamil phrase for a segment if any TAMIL_PHRASES key is found."""
    seg_lower = segment.lower().strip()
    # Try longest key first to avoid partial matches shadowing fuller ones
    for key in sorted(TAMIL_PHRASES, key=len, reverse=True):
        if key in seg_lower:
            return TAMIL_PHRASES[key]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic document library
# ─────────────────────────────────────────────────────────────────────────────

_SYNTHETIC_DOCUMENTS: dict[str, dict] = {
    "rx_001": {
        "id": "rx_001",
        "type": "prescription",
        "title": "Clear Prescription — Amoxicillin",
        "scenario": "clear",
        "text": (
            "Patient: Fictional Patient A  Date: 2024-03-15\n"
            "Dr. Fictional Physician, MBBS — Ref: FP-2024-001\n\n"
            "Rx:\n"
            "1. Amoxicillin 500mg — twice daily after meals for 7 days.\n"
            "2. Paracetamol 500mg — as needed for fever, max 4 doses/day.\n\n"
            "Warning: Discontinue and consult immediately if skin rash develops.\n"
            "Follow-up: 2024-03-22"
        ),
    },
    "rx_002": {
        "id": "rx_002",
        "type": "prescription",
        "title": "Ambiguous Prescription — Unspecified Duration",
        "scenario": "ambiguous",
        "text": (
            "Patient: Fictional Patient B  Date: 2024-04-10\n"
            "Dr. Fictional Physician — Ref: FP-2024-002\n\n"
            "Rx:\n"
            "1. Metformin 500mg — take as directed.\n"
            "2. [illegible] 10mg — [illegible]\n\n"
            "Note: Monitor blood sugar. Next review: [date not specified]."
        ),
    },
    "rx_003": {
        "id": "rx_003",
        "type": "prescription",
        "title": "Conflicting Instructions — Ibuprofen Dosage",
        "scenario": "conflicting",
        "text": (
            "Patient: Fictional Patient C  Date: 2024-05-01\n"
            "Dr. Fictional Physician — Ref: FP-2024-003\n\n"
            "Rx:\n"
            "1. Ibuprofen 400mg — three times daily.\n"
            "   [Handwritten note:] Ibuprofen 200mg — twice daily only.\n\n"
            "Allergy note: Patient has reported stomach sensitivity.\n"
            "Warning: Take with food. Do not exceed 1200mg per day."
        ),
    },
    "rx_004": {
        "id": "rx_004",
        "type": "prescription",
        "title": "Potential Emergency — Severe Allergy Warning",
        "scenario": "emergency",
        "text": (
            "Patient: Fictional Patient D  Date: 2024-06-20\n"
            "Dr. Fictional Physician — Ref: FP-2024-004\n\n"
            "Rx:\n"
            "1. Azithromycin 500mg — once daily for 3 days.\n\n"
            "URGENT WARNING: Patient has documented severe allergy to penicillin-class antibiotics.\n"
            "If patient develops difficulty breathing, swelling of face/lips/throat, or hives "
            "within 30 minutes of first dose — CALL EMERGENCY SERVICES IMMEDIATELY (108).\n"
            "Do NOT administer a second dose without physician review."
        ),
    },
    "lab_001": {
        "id": "lab_001",
        "type": "lab_report",
        "title": "Clear Lab Report — Blood Glucose",
        "scenario": "clear",
        "text": (
            "Patient: Fictional Patient E  Date: 2024-07-05\n"
            "Lab: Fictional Diagnostics — Ref: FD-2024-101\n\n"
            "Test: Fasting Blood Glucose\n"
            "Result: 98 mg/dL  (Normal range: 70–99 mg/dL)\n\n"
            "Test: HbA1c\n"
            "Result: 5.6%  (Normal: below 5.7%)\n\n"
            "Interpretation note: Results within normal limits. Review with your physician."
        ),
    },
    "lab_002": {
        "id": "lab_002",
        "type": "lab_report",
        "title": "Ambiguous Lab Report — Unreadable Values",
        "scenario": "ambiguous",
        "text": (
            "Patient: Fictional Patient F  Date: 2024-08-12\n"
            "Lab: Fictional Diagnostics — Ref: FD-2024-202\n\n"
            "Test: Complete Blood Count\n"
            "Haemoglobin: [smudged] g/dL  (Normal: 12–17 g/dL)\n"
            "WBC: 8.2 × 10³/μL  (Normal: 4.5–11.0)\n"
            "Platelets: [illegible]\n\n"
            "Note: Partial results only. Please request a repeat test."
        ),
    },
    "dc_001": {
        "id": "dc_001",
        "type": "discharge_summary",
        "title": "Discharge Summary — Post-Appendectomy",
        "scenario": "clear",
        "text": (
            "Patient: Fictional Patient G  Discharge Date: 2024-09-03\n"
            "Hospital: Fictional General Hospital — Ref: FGH-2024-301\n\n"
            "Diagnosis: Acute appendicitis (fictional)\n"
            "Procedure: Laparoscopic appendectomy (fictional)\n\n"
            "Discharge Medications:\n"
            "1. Amoxicillin-Clavulanate 625mg — twice daily for 5 days.\n"
            "2. Paracetamol 500mg — every 6 hours as needed for pain.\n"
            "3. Omeprazole 20mg — once daily before breakfast for 14 days.\n\n"
            "Follow-up: 2024-09-10 with surgeon.\n"
            "Warning: Return to emergency if fever above 38.5°C, increasing pain, or wound discharge."
        ),
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Extraction helpers (regex-based, no LLM)
# ─────────────────────────────────────────────────────────────────────────────

_DRUG_NAMES: list[str] = [
    "Amoxicillin", "Amoxicillin-Clavulanate", "Paracetamol", "Ibuprofen",
    "Metformin", "Azithromycin", "Cetirizine", "Omeprazole", "Amlodipine",
    "Atorvastatin", "Metronidazole", "Aspirin",
]

_DOSAGE_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(mg|mcg|ml|IU|g|%|mg/dL|mmol/L|×\s*10[³3]/μL)\b",
    re.IGNORECASE,
)

_FREQUENCY_PATTERN = re.compile(
    r"\b(once|twice|three times|four times|every \d+ hours?|"
    r"\d+\s*times?\s*(daily|a day)|daily|nocte|bd|tds|qid|od)\b",
    re.IGNORECASE,
)

_DURATION_PATTERN = re.compile(
    r"\bfor\s+(\d+)\s+(day|days|week|weeks|month|months)\b",
    re.IGNORECASE,
)

_DATE_PATTERN = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2}-\d{1,2}-\d{4})\b"
)

_WARNING_PATTERN = re.compile(
    r"(?:Warning|URGENT WARNING|Allergy note|Note)[:\s]+(.+?)(?:\n|$)",
    re.IGNORECASE,
)

_ILLEGIBLE_PATTERN = re.compile(
    r"\[(?:illegible|smudged|unclear|unreadable)[^\]]*\]",
    re.IGNORECASE,
)


def _extract_fields(text: str) -> dict:
    """Parse clinical fields from free-form medical text using regex."""
    drug_names = []
    for name in _DRUG_NAMES:
        if re.search(r"\b" + re.escape(name) + r"\b", text, re.IGNORECASE):
            drug_names.append(name)

    dosages = [
        m.group(0).replace(" ", "").lower()
        for m in _DOSAGE_PATTERN.finditer(text)
    ]
    seen: set[str] = set()
    unique_dosages: list[str] = []
    for d in dosages:
        if d not in seen:
            seen.add(d)
            unique_dosages.append(d)

    frequencies = list({m.group(0) for m in _FREQUENCY_PATTERN.finditer(text)})
    durations = [
        f"{m.group(1)} {m.group(2)}" for m in _DURATION_PATTERN.finditer(text)
    ]
    dates = list({m.group(0) for m in _DATE_PATTERN.finditer(text)})
    warnings = [m.group(1).strip() for m in _WARNING_PATTERN.finditer(text)]
    unreadable = [m.group(0) for m in _ILLEGIBLE_PATTERN.finditer(text)]

    return {
        "drug_names": drug_names,
        "dosages": unique_dosages,
        "frequencies": frequencies,
        "durations": durations,
        "dates": dates,
        "warnings": warnings,
        "unreadable_sections": unreadable,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tamil explanation builder (phrase-level matching)
# ─────────────────────────────────────────────────────────────────────────────

def _build_tamil_explanation(original_text: str, fields: dict) -> str:
    """Build a Tamil explanation that preserves all extracted clinical values verbatim.

    Medicine names, dosages, units, frequencies, durations, and dates are embedded
    as-is inside the Tamil text so that verify_translation can find them.
    """
    lines: list[str] = []

    unreadable = fields.get("unreadable_sections", [])
    has_unreadable = bool(unreadable)

    lines.append("📋 மருத்துவ ஆவண விளக்கம் (Tamil Medical Document Explanation)")
    lines.append("")

    drug_names = fields.get("drug_names", [])
    dosages = fields.get("dosages", [])
    frequencies = fields.get("frequencies", [])
    durations = fields.get("durations", [])

    if drug_names:
        lines.append("💊 மருந்துகள் (Medicines):")
        for i, drug in enumerate(drug_names):
            dose_str = dosages[i] if i < len(dosages) else ""
            freq_str = frequencies[0] if frequencies else ""
            dur_str = durations[0] if durations else ""

            freq_tamil = _find_tamil_for_segment(freq_str) if freq_str else ""
            entry = f"  • {drug}"
            if dose_str:
                entry += f" {dose_str}"
            if freq_str:
                entry += f" — {freq_tamil or freq_str}"
            if dur_str:
                entry += f" — {dur_str} வரை"
            lines.append(entry)
    else:
        lines.append("இந்த ஆவணத்தில் மருந்துகள் எதுவும் கண்டறியவில்லை.")

    lines.append("")

    dates = fields.get("dates", [])
    if dates:
        lines.append("📅 முக்கியமான தேதிகள் (Important Dates):")
        for d in dates:
            lines.append(f"  • {d}")
        lines.append("")

    warnings = fields.get("warnings", [])
    if warnings:
        lines.append("⚠️ எச்சரிக்கைகள் (Warnings — மூல ஆவணத்திலிருந்து / from original document):")
        for w in warnings:
            lines.append(f"  • {w}")
        lines.append("")

    if has_unreadable:
        lines.append(
            "❓ சில பகுதிகள் தெளிவாக இல்லை (Some sections are unclear):\n"
            "  " + ", ".join(unreadable) + "\n"
            "  இந்த தகவல்களை மருத்துவரிடம் கேளுங்கள்."
        )
        lines.append("")

    lines.append(
        "ℹ️  இந்த விளக்கம் உதவிக்காக மட்டுமே. எந்த மருத்துவ முடிவும் எடுப்பதற்கும் முன்\n"
        "    உங்கள் மருத்துவர் அல்லது மருந்தாளரிடம் கலந்தாலோசியுங்கள்.\n"
        "    (This explanation is for informational purposes only. Always consult your\n"
        "    healthcare professional before making any medical decisions.)"
    )

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Emergency guidance table (pre-written; no LLM)
# ─────────────────────────────────────────────────────────────────────────────

_EMERGENCY_KEYWORDS: list[tuple[list[str], dict]] = [
    (
        ["breathing", "breath", "throat", "swelling", "anaphylaxis", "hives", "rash severe"],
        {
            "type": "anaphylaxis",
            "tamil": (
                "🚨 அவசர நிலை — ஒவ்வாமை அதிர்ச்சி (Anaphylaxis)\n\n"
                "1. உடனடியாக 108 அல்லது 112 அழைக்கவும்.\n"
                "2. நோயாளியை படுக்க வையுங்கள்; கால்களை சற்று உயர்த்தவும்.\n"
                "3. மருந்தை உடனே நிறுத்தவும். மற்ற எந்த மருந்தும் தராதீர்கள்.\n"
                "4. நோயாளியை தனியாக விடாதீர்கள்.\n"
                "5. மருத்துவர் வரும் வரை கண்காணிக்கவும்."
            ),
            "english": (
                "🚨 EMERGENCY — Anaphylaxis (Severe Allergic Reaction)\n\n"
                "1. Call 108 or 112 IMMEDIATELY.\n"
                "2. Lay the patient flat; raise their legs slightly.\n"
                "3. Stop the medication immediately. Do not give any other medication.\n"
                "4. Do not leave the patient alone.\n"
                "5. Monitor until emergency services arrive."
            ),
        },
    ),
    (
        ["chest pain", "heart", "cardiac", "palpitation"],
        {
            "type": "cardiac",
            "tamil": (
                "🚨 அவசர நிலை — இதய பிரச்சினை\n\n"
                "1. உடனடியாக 108 அல்லது 112 அழைக்கவும்.\n"
                "2. நோயாளியை அமைதியாக உட்கார வையுங்கள்; படுக்க வைக்காதீர்கள்.\n"
                "3. இறுக்கமான ஆடைகளை தளர்த்தவும்.\n"
                "4. மருத்துவர் அறிவுரை இல்லாமல் எந்த மருந்தும் தராதீர்கள்.\n"
                "5. மருத்துவமனைக்கு தனியாக வாகனம் ஓட்டாதீர்கள்."
            ),
            "english": (
                "🚨 EMERGENCY — Cardiac Concern\n\n"
                "1. Call 108 or 112 IMMEDIATELY.\n"
                "2. Have the patient sit upright and still; do not lay them flat.\n"
                "3. Loosen any tight clothing.\n"
                "4. Do not give any medication without medical instruction.\n"
                "5. Do not drive yourself to hospital."
            ),
        },
    ),
    (
        ["overdose", "too much", "accidental", "poison", "ingested"],
        {
            "type": "overdose",
            "tamil": (
                "🚨 அவசர நிலை — அதிக மருந்து உட்கொண்டிருக்கலாம்\n\n"
                "1. உடனடியாக 108 அல்லது 1800-425-1213 (விஷம் கட்டுப்பாடு) அழைக்கவும்.\n"
                "2. மருந்து பாட்டில் அல்லது மருந்துச் சீட்டை தயாராக வையுங்கள்.\n"
                "3. வாந்தி எடுக்க வைக்காதீர்கள் — மருத்துவரின் அறிவுரை இல்லாமல்.\n"
                "4. நோயாளியை விழிப்பாக வையுங்கள்; பேசி ஆறுதல் சொல்லுங்கள்.\n"
                "5. உடனடியாக மருத்துவமனைக்கு செல்லவும்."
            ),
            "english": (
                "🚨 EMERGENCY — Possible Overdose\n\n"
                "1. Call 108 or Poison Control 1800-425-1213 IMMEDIATELY.\n"
                "2. Keep the medication bottle or prescription ready.\n"
                "3. Do NOT induce vomiting unless instructed by a medical professional.\n"
                "4. Keep the patient awake and calm.\n"
                "5. Go to hospital immediately."
            ),
        },
    ),
    (
        ["unconscious", "faint", "collapse", "seizure", "convulsion"],
        {
            "type": "unconscious",
            "tamil": (
                "🚨 அவசர நிலை — சுயநினைவு இழந்திருக்கலாம் / வலிப்பு\n\n"
                "1. உடனடியாக 108 அல்லது 112 அழைக்கவும்.\n"
                "2. நோயாளியை பாதுகாப்பான இடத்தில் படுக்க வையுங்கள்.\n"
                "3. தலைக்கு கீழே மென்மையான ஏதாவது வையுங்கள்.\n"
                "4. நோயாளியை கட்டிப் பிடிக்காதீர்கள் அல்லது வாயில் எதுவும் வைக்காதீர்கள்.\n"
                "5. வலிப்பு நின்ற பிறகும் அவர் சுயநினைவுக்கு வரும் வரை கண்காணிக்கவும்."
            ),
            "english": (
                "🚨 EMERGENCY — Unconsciousness / Seizure\n\n"
                "1. Call 108 or 112 IMMEDIATELY.\n"
                "2. Lay the patient in a safe position on the floor.\n"
                "3. Place something soft under their head.\n"
                "4. Do NOT restrain them or put anything in their mouth.\n"
                "5. Monitor after the seizure until they regain consciousness."
            ),
        },
    ),
]

_DEFAULT_EMERGENCY = {
    "type": "general",
    "tamil": (
        "🚨 அவசர நிலை — உடனடி நடவடிக்கை தேவை\n\n"
        "1. உடனடியாக அவசர சேவைகளை அழைக்கவும் (108 அல்லது 112).\n"
        "2. நோயாளியை தனியாக விடாதீர்கள்.\n"
        "3. மருத்துவர் வரும் வரை எந்த மருந்தும் தராதீர்கள்.\n"
        "4. மருத்துவமனைக்கு தனியாக வாகனம் ஓட்டாதீர்கள்.\n\n"
        "இது மருத்துவ அவசரநிலை. உங்கள் மருத்துவர் அல்லது அவசர சேவை மட்டுமே சிகிச்சை வழங்க முடியும்."
    ),
    "english": (
        "🚨 EMERGENCY — IMMEDIATE ACTION REQUIRED\n\n"
        "1. Call emergency services IMMEDIATELY (108 or 112 in India).\n"
        "2. Do not leave the patient alone.\n"
        "3. Do not administer any medication without medical supervision.\n"
        "4. Do not drive yourself to hospital — wait for emergency services.\n\n"
        "This is a medical emergency. Only emergency services or a healthcare professional can provide treatment."
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# @tool functions
# ─────────────────────────────────────────────────────────────────────────────

@tool
def extract_clinical_text(document_text: str) -> dict:
    """Extract clinical fields from a medical document (prescription, lab report, or discharge summary).

    Parses drug names, dosages, frequencies, durations, dates, warnings, and flags
    unreadable or illegible sections. Uses regex only — no LLM calls.

    Args:
        document_text: Raw text of the medical document (pasted or OCR-extracted).

    Returns:
        Dict with keys: drug_names, dosages, frequencies, durations, dates, warnings,
        unreadable_sections, and the original document_text.
    """
    fields = _extract_fields(document_text)
    has_unreadable = bool(fields["unreadable_sections"])
    return {
        **fields,
        "document_text": document_text,
        "has_unreadable_sections": has_unreadable,
        "extraction_note": (
            "Some sections are illegible and cannot be explained safely. "
            "Please consult your healthcare professional for complete information."
            if has_unreadable else
            "Extraction complete. All detected fields are listed above."
        ),
    }


@tool
def translate_to_tamil(original_text: str, document_type: str = "prescription") -> dict:
    """Translate extracted medical instructions into simple, natural Tamil using TAMIL_PHRASES.

    Iterates over sentences/clauses, matches against the TAMIL_PHRASES dictionary,
    and preserves all drug names, dosages, units, and dates verbatim. Segments with
    no matching phrase are passed through with a Tamil note directing the user to
    consult their doctor.

    Args:
        original_text:  The source medical text (pasted or OCR-extracted).
        document_type:  Type hint — 'prescription', 'lab_report', or 'discharge_summary'.

    Returns:
        Dict with: original_text, tamil_text, document_type, disclaimer,
        disclaimer_en, preserved_values, unmapped_segments, verification.
    """
    # Split into segments on sentence boundaries
    raw_segments = re.split(r"[.\n;]+", original_text)
    segments = [s.strip() for s in raw_segments if s.strip()]

    tamil_lines: list[str] = []
    unmapped_segments: list[str] = []

    for seg in segments:
        tamil_phrase = _find_tamil_for_segment(seg)
        if tamil_phrase:
            # Preserve any clinical values (drug+dose, dosage-only, dates) verbatim
            # by appending them after the Tamil phrase
            clinical_vals = _CLINICAL_VALUE_PATTERN.findall(seg)
            if clinical_vals:
                tamil_lines.append(f"{tamil_phrase} ({', '.join(clinical_vals)})")
            else:
                tamil_lines.append(tamil_phrase)
        else:
            # Pass the segment through with a clarifying Tamil note
            unmapped_segments.append(seg)
            tamil_lines.append(
                f"{seg} (மொழிபெயர்க்கப்படவில்லை — உங்கள் மருத்துவரிடம் கேளுங்கள்)"
            )

    tamil_text = "\n".join(tamil_lines)

    # Collect all preserved clinical values from the full original text
    preserved_values: list[str] = list(
        dict.fromkeys(m.group(0) for m in _CLINICAL_VALUE_PATTERN.finditer(original_text))
    )

    # Run internal verification
    fields = _extract_fields(original_text)
    verification = verify_translation(original_text, tamil_text, fields)

    disclaimer_ta = (
        "இந்த விளக்கம் உதவிக்காக மட்டுமே. எந்த மருத்துவ முடிவும் எடுப்பதற்கும் முன் "
        "உங்கள் மருத்துவர் அல்லது மருந்தாளரிடம் கலந்தாலோசியுங்கள்."
    )
    disclaimer_en = (
        "This explanation is for informational purposes only. "
        "Consult your healthcare professional before making any medical decisions."
    )

    return {
        "original_text": original_text,
        "tamil_text": tamil_text,
        "document_type": document_type,
        "disclaimer": disclaimer_ta,
        "disclaimer_en": disclaimer_en,
        "preserved_values": preserved_values,
        "unmapped_segments": unmapped_segments,
        "verification": verification,
    }


@tool
def get_emergency_guidance(concern: str) -> dict:
    """Return pre-written Tamil and English emergency guidance for a detected safety concern.

    Guidance is selected by keyword matching against the concern string. Never invents
    medical advice — all text is pre-written and reviewed for safety.

    Args:
        concern: A short description of the concern (e.g. 'difficulty breathing',
                 'chest pain', 'possible overdose').

    Returns:
        Dict with: concern, type, action_tamil, action_english, emergency_numbers.
    """
    concern_lower = concern.lower()
    selected = _DEFAULT_EMERGENCY
    for keywords, guidance in _EMERGENCY_KEYWORDS:
        if any(kw in concern_lower for kw in keywords):
            selected = guidance
            break

    return {
        "concern": concern,
        "type": selected["type"],
        "action_tamil": selected["tamil"],
        "action_english": selected["english"],
        "emergency_numbers": {
            "ambulance": "108",
            "emergency": "112",
            "poison_control": "1800-425-1213",
        },
    }


@tool
def list_synthetic_documents() -> dict:
    """Return a catalogue of built-in synthetic medical documents for demos and testing.

    Returns:
        Dict with a 'documents' list; each entry has id, type, title, and scenario.
    """
    return {
        "documents": [
            {
                "id": doc["id"],
                "type": doc["type"],
                "title": doc["title"],
                "scenario": doc["scenario"],
            }
            for doc in _SYNTHETIC_DOCUMENTS.values()
        ]
    }


@tool
def get_synthetic_document(doc_id: str) -> dict:
    """Return a specific synthetic medical document by its ID.

    Use list_synthetic_documents() first to see available IDs.

    Args:
        doc_id: Document identifier (e.g. 'rx_001', 'lab_001', 'dc_001').

    Returns:
        The full document dict, or an error dict if not found.
    """
    doc = _SYNTHETIC_DOCUMENTS.get(doc_id)
    if doc is None:
        available = list(_SYNTHETIC_DOCUMENTS.keys())
        return {
            "error": f"Document '{doc_id}' not found.",
            "available_ids": available,
        }
    return doc


@tool
def ingest_document(file_bytes_b64: str, filename: str) -> dict:
    """Ingest an uploaded medical document (base64-encoded).

    Supports .txt, .pdf, .png, .jpg, .jpeg. Extracts raw text via text parsing or
    OCR as appropriate, then extracts clinical fields. Never stores the file.

    Args:
        file_bytes_b64: Base64-encoded file content.
        filename:       Original filename including extension (e.g. 'prescription.pdf').

    Returns:
        Dict with: raw_text, method, filename, page_count, confidence, clinical_fields.
    """
    import base64
    from agent.ingestion import ingest_uploaded_file, extract_clinical_fields

    raw = base64.b64decode(file_bytes_b64)
    result = ingest_uploaded_file(raw, filename)
    result["clinical_fields"] = extract_clinical_fields(result["raw_text"])
    return result


@tool
def verify_medical_translation(original_text: str, tamil_text: str) -> dict:
    """Verify that a Tamil translation preserves all clinical values from the original.

    Checks drug names, dosages, and dates against the Tamil explanation. Returns a
    pass/fail result, lists of missing or altered values, and a quality score.

    Args:
        original_text: The source medical document text.
        tamil_text:    The Tamil explanation to verify.

    Returns:
        Dict with: passed, missing, altered, warnings, score.
    """
    from agent.ingestion import extract_clinical_fields

    fields = extract_clinical_fields(original_text)
    return verify_translation(original_text, tamil_text, fields)


# ─────────────────────────────────────────────────────────────────────────────
# Exported tool list (consumed by agent.py)
# ─────────────────────────────────────────────────────────────────────────────

TOOLS = [
    extract_clinical_text,
    translate_to_tamil,
    get_emergency_guidance,
    ingest_document,
    verify_medical_translation,
    list_synthetic_documents,
    get_synthetic_document,
]
