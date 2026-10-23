# Maruthuva Mozhi — Requirements

## Overview
Maruthuva Mozhi (Tamil: மருத்துவ மொழி, "Medical Language") is an AI agent that translates
synthetic medical documents — prescriptions, lab reports, and discharge summaries — into simple,
understandable Tamil for Tamil-speaking patients and family caregivers.

It extracts text from uploaded files or pasted content, classifies the document with Strands
Decider 2B (#guardrails), translates the result into Tamil, and verifies that the Tamil output
preserves all clinical details correctly.

---

## Users
- Tamil-speaking patients and family caregivers in India who struggle to understand English or
  transliterated medical documents.

---

## Input Method (MVP)

**Primary: Pasted medical text.** The user types or pastes the raw text of a medical document
into the chat or web UI.

**Also supported (MVP):** File upload via the web UI or as a base64-encoded payload to the
`ingest_document` tool. Accepted formats:

| Format | Extraction method |
|---|---|
| `.txt` | Direct UTF-8 read |
| `.pdf` | `pdfminer.six` text extraction; fall back to OCR if < 20 characters extracted |
| `.png`, `.jpg`, `.jpeg` | `pytesseract` OCR |

**Graceful degradation:** If Tesseract is not installed, OCR attempts must return a clear error
message (`"Tesseract is not installed or not found on PATH. Install it to enable OCR."`) and
must not crash the agent. PDF text extraction still works without Tesseract.

**Not in scope for MVP:** Audio input, DICOM, TIFF, multi-page PDF image extraction beyond the
first page fallback, real-time camera capture.

---

## Functional Requirements

### FR-1 Document ingestion (new)
- `agent/ingestion.py` provides two functions:
  - `ingest_uploaded_file(file_bytes: bytes, filename: str) -> dict` — detects format from
    filename extension, extracts raw text, returns a dict with keys `raw_text`, `method`,
    `filename`, `page_count` (PDF only, else 1), `confidence` (1.0 for txt, 0.9 for PDF text,
    0.7 for OCR, 0.0 on failure).
  - `extract_clinical_fields(raw_text: str) -> dict` — parses the raw text with regex to
    identify `drug_names`, `dosages`, `frequencies`, `durations`, `dates`, `warnings`, and
    `unreadable_sections`. Never infers missing values; absent fields are empty lists.
- The `ingest_document` Strands tool (in `tools.py`) accepts a base64-encoded file and calls
  `ingest_uploaded_file`. It surfaces extraction confidence and any error message to the agent.
- Documents are not stored after the response is returned. No files are written to disk during
  normal operation.

### FR-2 Strands Decider 2B classification (three-level safety gate) — unchanged
Classify each document using Strands Decider 2B (#guardrails pattern) with three levels:

| Level | Trigger | Action |
|---|---|---|
| **Emergency** | Immediate life-threatening concern (emergency symptoms, dangerous drug combination, critically abnormal lab values) | Deny the translation. Call `emergency_guidance()` immediately. Deliver Tamil + English emergency advice to the user regardless of the tool-call denial. Never withhold emergency guidance because a tool call was blocked. |
| **Needs professional review** | Medication concern, unusual dosage, drug-interaction warning, or missing clinical detail that does not meet emergency threshold | Guide: explain only the independently clear parts of the document. Do not translate ambiguous sections. Direct user to a qualified healthcare professional for the unclear parts. Never guess missing clinical details. |
| **Clear** | All instructions explicit, no conflicts, no safety concerns | Proceed: translate the full document to simple Tamil. |

### FR-3 Tamil translation — upgraded
- The phrase dictionary (`TAMIL_PHRASES`) in `tools.py` must contain **at least 40 entries**
  covering prescription, lab report, and discharge summary language.
- Entries must cover:
  - Frequency patterns (once/twice/three/four times daily, morning, evening, bedtime, hourly)
  - Meal relations (after meals, before meals, with food, on empty stomach)
  - Route/form (tablet, capsule, syrup, injection, drops, ointment, inhaler)
  - Duration phrases (for N days/weeks/months, complete the full course)
  - Action instructions (stop if, consult your doctor, do not exceed, avoid alcohol, avoid driving)
  - Lab interpretation phrases (within normal range, above normal range, below normal range,
    borderline, refer to physician, retest required)
  - Discharge summary phrases (admitted for, discharged on, follow-up on, rest advised)
  - Safety warnings (do not crush, take on empty stomach, store in refrigerator, keep out of reach)
- **Preservation rule:** drug names, numeric dosages, units (mg, ml, g, mcg, IU, %), and dates
  are copied verbatim into the Tamil output. They are never translated or paraphrased.
- **Fallback:** unmatched segments are kept in English with a Tamil parenthetical note:
  `(மொழிபெயர்க்கப்படவில்லை — உங்கள் மருத்துவரிடம் கேளுங்கள்)`.
- Returns `{ "original": str, "tamil": str, "document_type": str, "preserved_values": list }`.
- Original instruction shown alongside the Tamil explanation in every response.

### FR-4 Medical meaning verification (new)
- `agent/verification.py` provides `verify_translation(original_text, tamil_text, clinical_fields) -> dict`.
- Checks that every drug name, dosage, unit, date, and warning extracted by
  `extract_clinical_fields` appears (verbatim or transliterated) in the Tamil output.
- Returns `{ "passed": bool, "missing": list, "altered": list, "warnings": list, "score": float }`.
- The `verify_medical_translation` Strands tool (in `tools.py`) calls this function and returns
  the result to the agent so it can report any discrepancy to the user.
- The agent surfaces verification failures in its reply — it does not silently discard them.

### FR-5 Ambiguous-document handling — unchanged
- For documents classified as "needs professional review":
  - Identify and explain only the parts that are independently clear.
  - Never fill in, guess, or infer missing dosages, timings, diagnoses, or drug interactions.
  - Append a Tamil-language advisory: "தெளிவற்ற விவரங்களுக்கு, தகுதிவாய்ந்த மருத்துவரை அணுகவும்."

### FR-6 Emergency handling — unchanged
- For documents classified as "emergency":
  - Call `emergency_guidance()` immediately, even though the translation tool call is denied.
  - Return guidance in both Tamil and English, including emergency numbers 108 and 112.

### FR-7 Web UI — upgraded
- **Two input tabs:** "Upload Document" and "Paste Text".
  - Upload tab: file picker accepting `.txt`, `.pdf`, `.png`, `.jpg`, `.jpeg`; shows extraction
    preview (raw text + confidence + method) before the agent processes it.
  - Paste tab: textarea, existing behaviour.
- **Side-by-side display:** original extracted text on the left, Tamil explanation on the right.
- **Verification panel:** shows verification score, any missing or altered clinical values.
- **Safety badge:** `CLEAR` (green), `NEEDS REVIEW` (amber), `EMERGENCY` (red) — derived from
  the decider verdict.
- **Font:** Noto Sans Tamil for Tamil script rendering.
- **Footer:** "Built with the AWS User Group Madurai Strands Decider hackathon kit".
- New API endpoints on `demo/server.py`:
  - `POST /api/upload` (multipart form-data): accepts the file, calls `ingest_document`, returns
    extraction preview.
  - `POST /api/verify`: accepts `{ original, tamil, clinical_fields }`, calls
    `verify_medical_translation`, returns verification result.

---

## Synthetic Data Requirements

### FR-8 Document templates
- `agent/data/templates/` contains **6 `.txt` template files**, each beginning with the header:
  ```
  FICTIONAL — FOR DEMO/TESTING ONLY. Not a real medical document.
  ```
- One template per category:
  1. Clear prescription (all clinical values explicit)
  2. Clear lab report (all values within normal range, clear interpretation)
  3. Ambiguous prescription (missing frequency or unclear dose)
  4. Ambiguous lab report (borderline values, conflicting reference range)
  5. Medication-concern prescription (unusual dose note or drug-interaction warning)
  6. Emergency case (emergency symptoms: chest pain + shortness of breath)
- Drug names must be well-known generic names with clearly fictional patient context, or
  completely fictional drug names. No real patient names, IDs, or clinic details.

### FR-9 Eval cases extended
- `agent/eval_cases.jsonl` must contain **36 labelled cases** (12 tune / 24 test).
- The 24 existing cases are retained as-is.
- 12 new test-split cases to add (2 per category):
  - 2 clear prescription
  - 2 clear lab report
  - 2 ambiguous prescription
  - 2 ambiguous lab report
  - 2 medication concern (needs review, not emergency)
  - 2 emergency
- State strings in all cases must match the exact format the wiring sends to the decider.

---

## Non-Functional Requirements
- **No real patient data.** All documents used in development, tests, and the demo are
  synthetic and clearly labelled FICTIONAL. No real patient names, IDs, or records.
- **No document storage.** Uploaded files are not written to disk and are not retained after
  the response is returned.
- **Clinical-value integrity.** Drug names, dosages, units, and dates are never altered,
  rounded, or inferred. Missing values are flagged, not substituted.
- **No diagnosis or prescription change.** The agent never suggests a diagnosis, changes a dose,
  or recommends stopping or starting medication.
- **Safety-conservative.** Decider confidence below 0.65 falls back to "needs professional
  review" rather than proceeding with translation.
- **OCR optional.** The agent must function fully (pasted text + PDF text extraction) without
  Tesseract installed. OCR unavailability produces a clear message, not a crash.
- **No Memory or Gateway.** `agent/features.yaml` remains empty. AgentCore Memory and Gateway
  are out of scope for this MVP.
- **Kit compatibility.** All LLM calls go through `decider_kit.llm.agent_model()` / `ask()`.
  No direct boto3 `converse` or `invoke_model` calls. The `QUESTIONS` dict in `decision.py`
  is importable by `./kit bench`.

---

## Decision Pattern
- **Pattern tag**: `#guardrails`
- **Three noul questions**: `is_clear`, `needs_clarification`, `safety_concern` (see design.md).
- **Wiring**: `MedicalTranslationGuard` (Strands `InterventionHandler`) in `agent/decision.py`.
  Guards `translate_to_tamil` only; other tools run untouched.
- **Emergency path**: `emergency_guidance()` called from within the handler on Deny; its output
  always reaches the user even when translation is blocked.
