# Maruthuva Mozhi — Design

---

## Architecture

```
User pastes text OR uploads file (.txt / .pdf / .png / .jpg)
    ↓
[File upload path]                         [Paste path]
POST /api/upload                           chat textarea
    ↓                                           ↓
agent/ingestion.py                         HackathonAgent.chat()
  ingest_uploaded_file()                        ↓
    ↓                                  Strands Agent (LLM via ugmdu)
extract_clinical_fields()                       ↓
    ↓                              extract_medical_text(document, type)
ingest_document tool result                     ↓
    ↓___________________________→  [MedicalTranslationGuard fires on translate_to_tamil]
                                        ↓
                                  Decider.ask(state, QUESTIONS)
                                        ↓
    ┌────────────────────────────────────────────────────────────────────┐
    │ safety_concern ≥ 0.5  →  Deny()  →  call emergency_guidance()    │
    │                            ↓                                       │
    │                  return emergency reply (Tamil + English + 112)    │
    ├────────────────────────────────────────────────────────────────────┤
    │ needs_clarification ≥ 0.5  →  Guide(feedback)                     │
    │                            ↓                                       │
    │                   LLM explains clear parts only                    │
    │                   + Tamil advisory → consult professional          │
    ├────────────────────────────────────────────────────────────────────┤
    │ is_clear ≥ 0.5  →  Proceed()                                      │
    │                            ↓                                       │
    │              translate_to_tamil(text, document_type)               │
    │              → Tamil explanation, original side-by-side            │
    │                            ↓                                       │
    │              verify_medical_translation(original, tamil, fields)   │
    │              → verification panel in UI                            │
    └────────────────────────────────────────────────────────────────────┘
```

**Key invariants:**
- `emergency_guidance()` is always called and always reaches the user when `safety_concern ≥ 0.5`.
- A guided call retried unchanged is denied (convergence guarantee).
- No document bytes are written to disk during normal operation.
- All LLM calls go through `decider_kit.llm.agent_model()`.

---

## Module: agent/ingestion.py (new)

### `ingest_uploaded_file(file_bytes: bytes, filename: str) -> dict`

Detects format from the filename extension and extracts raw text.

```
filename extension   →   extraction path
.txt                 →   UTF-8 decode
.pdf                 →   pdfminer.six high_level.extract_text()
                         if len(raw_text.strip()) < 20:
                             fall back to pytesseract on first page via pdf2image
.png / .jpg / .jpeg  →   pytesseract.image_to_string() on PIL.Image
```

Return dict:

| Key | Type | Notes |
|---|---|---|
| `raw_text` | str | Extracted text. Empty string on failure. |
| `method` | str | `"txt"`, `"pdf_text"`, `"pdf_ocr"`, `"image_ocr"`, `"error"` |
| `filename` | str | Original filename |
| `page_count` | int | Number of pages (PDF), else 1 |
| `confidence` | float | 1.0 txt / 0.9 pdf_text / 0.7 pdf_ocr or image_ocr / 0.0 error |
| `error` | str \| None | Human-readable error message if extraction failed |

**Tesseract not installed:** catch `pytesseract.TesseractNotFoundError` (and `OSError` as
fallback). Return `method="error"`, `confidence=0.0`,
`error="Tesseract is not installed or not found on PATH. Install it to enable OCR."`.
Do not raise. pdfminer.six text extraction must still work in the same call.

### `extract_clinical_fields(raw_text: str) -> dict`

Regex-based parser. Returns:

| Key | Type | Example values |
|---|---|---|
| `drug_names` | list[str] | `["Amoxicillin", "Paracetamol"]` |
| `dosages` | list[str] | `["500mg", "1g", "10ml"]` |
| `frequencies` | list[str] | `["three times daily", "once daily"]` |
| `durations` | list[str] | `["7 days", "2 weeks"]` |
| `dates` | list[str] | `["2026-10-15", "15/10/2026"]` |
| `warnings` | list[str] | `["Stop if rash develops", "Avoid alcohol"]` |
| `unreadable_sections` | list[str] | Segments matching illegibility markers |

Absent fields are empty lists. Never infers or fills in missing values.

---

## Module: agent/verification.py (new)

### `verify_translation(original_text: str, tamil_text: str, clinical_fields: dict) -> dict`

Checks that clinical values extracted by `extract_clinical_fields` are preserved in the Tamil
output. The check is string-based (presence, not semantic):

1. For each drug name, dosage, unit, and date in `clinical_fields`: confirm it appears verbatim
   in `tamil_text`. Collect non-appearing items into `missing`.
2. Scan `tamil_text` for numerics that differ from the source. Collect into `altered`.
3. Collect any `warnings` from `clinical_fields` that are not referenced (even partially) in
   `tamil_text` into `warnings`.
4. `score = 1.0 - (len(missing) + len(altered)) / max(1, total_checked)`.
5. `passed = score >= 0.85 and len(altered) == 0`.

Return dict:

| Key | Type |
|---|---|
| `passed` | bool |
| `missing` | list[str] |
| `altered` | list[str] |
| `warnings` | list[str] |
| `score` | float (0.0–1.0) |

---

## Tools additions (agent/tools.py)

### Upgraded: `translate_to_tamil`

Replace the current mock lookup with a **phrase-dictionary implementation**:

```python
TAMIL_PHRASES: dict[str, str] = {
    # Frequency
    "once daily":             "ஒரு நாளில் ஒரு முறை",
    "twice daily":            "ஒரு நாளில் இரண்டு முறை",
    "thrice daily":           "ஒரு நாளில் மூன்று முறை",
    "three times daily":      "ஒரு நாளில் மூன்று முறை",
    "four times daily":       "ஒரு நாளில் நான்கு முறை",
    "every morning":          "ஒவ்வொரு காலையிலும்",
    "in the morning":         "காலையில்",
    "at bedtime":             "தூங்குவதற்கு முன்",
    "at night":               "இரவில்",
    "every 4-6 hours":        "ஒவ்வொரு 4–6 மணி நேரத்திற்கும்",
    "every 8 hours":          "ஒவ்வொரு 8 மணி நேரத்திற்கும்",
    "every 12 hours":         "ஒவ்வொரு 12 மணி நேரத்திற்கும்",
    # Meal relations
    "after meals":            "சாப்பிட்ட பிறகு",
    "before meals":           "சாப்பிடுவதற்கு முன்",
    "with food":              "உணவுடன்",
    "on empty stomach":       "வெறும் வயிற்றில்",
    "30 minutes before eating": "சாப்பிடுவதற்கு 30 நிமிடங்கள் முன்",
    # Form
    "tablet":                 "மாத்திரை",
    "capsule":                "காப்சூல்",
    "syrup":                  "சிரப்",
    "injection":              "ஊசி",
    "drops":                  "சொட்டு மருந்து",
    "ointment":               "களிம்பு",
    "inhaler":                "இன்ஹேலர்",
    # Duration
    "for 7 days":             "7 நாட்களுக்கு",
    "for 5 days":             "5 நாட்களுக்கு",
    "for 3 days":             "3 நாட்களுக்கு",
    "for 14 days":            "14 நாட்களுக்கு",
    "for 28 days":            "28 நாட்களுக்கு",
    "for 2 weeks":            "2 வாரங்களுக்கு",
    "complete the full course": "முழு மருந்து கோர்ஸையும் முடிக்கவும்",
    # Action instructions
    "stop if rash develops":  "தோல் அரிப்பு ஏற்பட்டால் நிறுத்தவும்",
    "consult your doctor":    "உங்கள் மருத்துவரை அணுகவும்",
    "do not exceed":          "அதிகமாக எடுக்காதீர்கள்",
    "do not crush":           "மெல்லாமல் அல்லது நொறுக்காமல் விழுங்கவும்",
    "avoid alcohol":          "மதுவை தவிர்க்கவும்",
    "avoid driving":          "வாகனம் ஓட்டுவதை தவிர்க்கவும்",
    "do not stop suddenly":   "திடீரென நிறுத்தாதீர்கள்",
    "store in refrigerator":  "குளிர்சாதனப்பெட்டியில் வையுங்கள்",
    "keep out of reach":      "குழந்தைகளின் எட்டாத இடத்தில் வையுங்கள்",
    # Lab interpretation
    "within normal range":    "சாதாரண அளவில் உள்ளது",
    "above normal range":     "சாதாரண அளவை விட அதிகமாக உள்ளது",
    "below normal range":     "சாதாரண அளவை விட குறைவாக உள்ளது",
    "borderline":             "எல்லை அளவில் உள்ளது",
    "refer to physician":     "மருத்துவரிடம் அனுப்பவும்",
    "retest required":        "மீண்டும் சோதிக்க வேண்டும்",
    # Discharge phrases
    "admitted for":           "அனுமதிக்கப்பட்டது",
    "discharged on":          "விடுவிக்கப்பட்டது",
    "follow-up on":           "மறு பரிசோதனை",
    "rest advised":           "ஓய்வு அறிவுறுத்தப்படுகிறது",
    # Safety warnings (document-sourced)
    "do not take on empty stomach": "வெறும் வயிற்றில் எடுக்காதீர்கள்",
    "may cause drowsiness":   "தூக்கம் வரலாம்",
    "may cause nausea":       "குமட்டல் ஏற்படலாம்",
    "take with food if needed": "தேவைப்பட்டால் சாப்பிட்டதும் எடுக்கவும்",
}
```

Algorithm:
1. Normalise input to lowercase for matching; preserve originals for output assembly.
2. Try longest-match first (sort phrases descending by length).
3. Replace matched segments with Tamil equivalents.
4. Preserve drug names, numerics with units, and date strings verbatim using a regex pre-scan.
5. Unmatched segments: keep in English + append Tamil fallback note.
6. Return `{ "original": original_text, "tamil": assembled_result, "document_type": document_type, "preserved_values": list_of_preserved }`.

### New tool: `ingest_document`

```python
@tool
def ingest_document(file_base64: str, filename: str) -> dict:
    """Extract text from an uploaded medical document (txt/pdf/png/jpg).
    file_base64: base64-encoded file bytes. Returns extraction result with raw_text,
    method, confidence, page_count, and any error message."""
```

Calls `ingestion.ingest_uploaded_file(base64.b64decode(file_base64), filename)` then
`ingestion.extract_clinical_fields(result["raw_text"])`.
Returns the combined dict (ingestion result + `clinical_fields`).

### New tool: `verify_medical_translation`

```python
@tool
def verify_medical_translation(original_text: str, tamil_text: str) -> dict:
    """Check that the Tamil translation preserves all clinical values from the original text.
    Returns passed (bool), missing values, altered values, warnings, and a score 0-1."""
```

Calls `ingestion.extract_clinical_fields(original_text)` then
`verification.verify_translation(original_text, tamil_text, clinical_fields)`.
Returns the verification dict.

---

## Decision Pattern: MedicalTranslationGuard (#guardrails) — unchanged

Already implemented in `agent/decision.py`. No changes needed to the decision pattern, the
state format, or the three QUESTIONS for the upgrade. The guard fires on `translate_to_tamil`
only; the two new tools run without interception.

### State string format
```
Medical document text being translated for a Tamil-speaking patient.

--- EXTRACTED MEDICAL TEXT ---
{extracted_text}

--- DOCUMENT TYPE ---
{document_type}
```

### Questions (unchanged)

| Key | Type | Question summary |
|---|---|---|
| `is_clear` | noul | All values explicit and unambiguous? |
| `needs_clarification` | noul | Contains gaps or conflicts a professional must resolve? |
| `safety_concern` | noul | Emergency or life-threatening concern present? |

Full question text and option descriptions are in `agent/decision.py`.

---

## Synthetic data

### agent/data/templates/ — 6 .txt files

Each file begins with:
```
FICTIONAL — FOR DEMO/TESTING ONLY. Not a real medical document.
```

| Filename | Content |
|---|---|
| `clear_prescription.txt` | Fictional drug, explicit dose/frequency/duration, one warning |
| `clear_lab_report.txt` | Fictional patient, 4 lab values all within reference ranges |
| `ambiguous_prescription.txt` | Drug name present, frequency missing, dose partially illegible |
| `ambiguous_lab_report.txt` | Two borderline values, conflicting reference ranges, no follow-up |
| `medication_concern.txt` | Unusual dose note + drug interaction warning, not emergency |
| `emergency_case.txt` | Severe chest pain, shortness of breath, "CALL EMERGENCY SERVICES" |

Drug names: use well-known generics (Amoxicillin, Metformin, Amlodipine) with clearly fictional
patient names, dates, and clinic names. No real clinic names or real patient IDs.

---

## Web UI (demo/server.py + demo/static/index.html)

### New endpoints on demo/server.py

**`POST /api/upload`** (multipart form-data, field `file`):
- Reads file bytes and filename from the upload.
- Calls `ingest_document` (or `ingestion.ingest_uploaded_file` directly for the preview step).
- Returns JSON: `{ raw_text, method, confidence, page_count, clinical_fields, error? }`.

**`POST /api/verify`**:
- Body: `{ "original": str, "tamil": str }`.
- Calls `verification.verify_translation` (or `verify_medical_translation` tool).
- Returns JSON: `{ passed, missing, altered, warnings, score }`.

### demo/static/index.html — single-page app

```
┌─────────────────────────────────────────────────────────┐
│  Maruthuva Mozhi  மருத்துவ மொழி                         │
│  ┌────────────────────────────────────────────────────┐  │
│  │ [ Upload Document ] [ Paste Text ]                 │  │
│  │                                                    │  │
│  │ Upload tab:                                        │  │
│  │   [  Choose file (.txt .pdf .png .jpg)  ]          │  │
│  │   Extraction preview: method | confidence | pages  │  │
│  │   [ Extracted text preview (collapsible) ]         │  │
│  │                                                    │  │
│  │ Paste tab:                                         │  │
│  │   [ textarea ]                                     │  │
│  │   [ Document type: Prescription ▼ ]                │  │
│  └────────────────────────────────────────────────────┘  │
│  [ Translate ]                                           │
│                                                          │
│  ┌──── Safety badge ──────────────────────────────────┐  │
│  │  ● CLEAR / ⚠ NEEDS REVIEW / 🚨 EMERGENCY          │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌── Original ─────────┐  ┌── Tamil Explanation ──────┐  │
│  │ (extracted text)    │  │ (tamil output)             │  │
│  └─────────────────────┘  └────────────────────────────┘ │
│                                                          │
│  ┌── Verification ──────────────────────────────────┐    │
│  │  Score: 0.95  ✓ Passed                           │    │
│  │  Missing: —   Altered: —   Warnings: —           │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  Built with the AWS User Group Madurai Strands Decider   │
│  hackathon kit                                           │
└─────────────────────────────────────────────────────────┘
```

- Noto Sans Tamil loaded from Google Fonts for Tamil script rendering.
- Safety badge colour: green (#22c55e) for CLEAR, amber (#f59e0b) for NEEDS REVIEW,
  red (#ef4444) for EMERGENCY.
- Verification panel appears only after a successful translation.
- Decider probabilities displayed in a collapsible "Decision details" section.
- No documents are stored by the server; file bytes remain in memory only during request handling.

---

## eval_cases.jsonl — 36 cases (12 tune / 24 test)

The 24 existing cases are unchanged. 12 new cases are added to the test split:

| # | Category | Expected |
|---|---|---|
| 25 | Clear prescription — single antibiotic, all values explicit | is_clear=yes, needs_clarification=no, safety_concern=no |
| 26 | Clear prescription — antihistamine, daytime/nighttime instruction | is_clear=yes, needs_clarification=no, safety_concern=no |
| 27 | Clear lab report — complete blood count, all within range | is_clear=yes, needs_clarification=no, safety_concern=no |
| 28 | Clear lab report — lipid panel, all values normal | is_clear=yes, needs_clarification=no, safety_concern=no |
| 29 | Ambiguous prescription — drug name readable, dose illegible | is_clear=no, needs_clarification=yes, safety_concern=no |
| 30 | Ambiguous prescription — conflicting frequency (once vs twice) | is_clear=no, needs_clarification=yes, safety_concern=no |
| 31 | Ambiguous lab report — urine culture result pending | is_clear=no, needs_clarification=yes, safety_concern=no |
| 32 | Ambiguous lab report — TSH with no interpretation given | is_clear=no, needs_clarification=yes, safety_concern=no |
| 33 | Medication concern — drug interaction warning, not emergency | is_clear=no, needs_clarification=yes, safety_concern=no |
| 34 | Medication concern — unusually high dose noted by pharmacist | is_clear=no, needs_clarification=yes, safety_concern=no |
| 35 | Emergency — severe chest pain + left arm pain onset | is_clear=no, needs_clarification=no, safety_concern=yes |
| 36 | Emergency — sudden unconsciousness, suspected overdose | is_clear=no, needs_clarification=no, safety_concern=yes |

All new cases use the same state string format as the existing ones.

---

## Tests: tests/test_upgrade.py

Covers (all using synthetic data only):

| Test group | What is tested |
|---|---|
| Ingestion — txt | `ingest_uploaded_file` on a `.txt` file returns `method="txt"`, `confidence=1.0` |
| Ingestion — PDF text | `ingest_uploaded_file` on a minimal PDF returns `method="pdf_text"` |
| Ingestion — Tesseract absent | Graceful error (no crash, `method="error"`, message includes "Tesseract") |
| `extract_clinical_fields` | Drug name, dosage, frequency, date extracted from known synthetic text |
| Verification — passing | `verify_translation` returns `passed=True` when all values preserved |
| Verification — missing | `verify_translation` returns `passed=False` and lists missing value |
| Verification — altered | `verify_translation` detects numeric alteration |
| `ingest_document` tool | Returns `raw_text` and `clinical_fields` for a base64-encoded `.txt` |
| `verify_medical_translation` tool | Returns `passed` and `score` for known input |
| `translate_to_tamil` — phrase coverage | At least 40 phrase entries in `TAMIL_PHRASES` |
| `translate_to_tamil` — value preservation | Drug name and dosage appear verbatim in output |
| `translate_to_tamil` — fallback note | Unmatched segment triggers Tamil fallback note |
| Decision — safety block | `safety_concern=yes` returns `Deny` (uses existing test scaffolding) |
| Decision — clarification guide | `needs_clarification=yes` returns `Guide` |
| Decision — clear proceed | `is_clear=yes` returns `Proceed` |
| Safety enforcement | A known emergency state never bypasses Deny regardless of `is_clear` |

---

## requirements.txt additions

| Package | Purpose |
|---|---|
| `pdfminer.six` | PDF text extraction |
| `pdf2image` | PDF-to-image for OCR fallback |
| `pytesseract` | OCR wrapper (Tesseract must be installed separately) |
| `Pillow` | Image loading for OCR |
| `reportlab` | (optional) generate synthetic PDF test fixtures |

Note: `pytesseract` and `pdf2image` are imported lazily or inside try/except blocks so the
agent runs correctly when Tesseract and Poppler are not installed.

---

## Agent contract (agent/agent.py) — unchanged

```python
NAME = "Maruthuva Mozhi"

class HackathonAgent:
    def __init__(self, eager: bool | None = None): ...
    def chat(self, message: str, session_id: str = "default",
             images: list | None = None) -> dict:
        # returns: reply, decisions, model_id, latency_ms
```

`TOOLS` in `tools.py` extended to include `ingest_document` and `verify_medical_translation`.
Agent system prompt updated to mention the two new tools and the verification step.
