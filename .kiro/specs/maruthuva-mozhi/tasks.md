# Maruthuva Mozhi — Tasks

---

## Phase 1: Spec ✅
- [x] requirements.md — input methods, safety gate, verification, upgrade constraints
- [x] design.md — architecture, ingestion/verification modules, tool specs, UI, eval cases
- [x] tasks.md — this file

---

## Phase 2: Core agent (already implemented) ✅
- [x] `agent/AGENT.md` — use case, users, decision, data, tools, constraints
- [x] `agent/decision.py` — `PATTERN_TAG="#guardrails"`, `QUESTIONS`, `MedicalTranslationGuard`
- [x] `agent/tools.py` — `extract_medical_text`, `translate_to_tamil` (mock), `emergency_guidance`
- [x] `agent/agent.py` — `NAME`, `HackathonAgent`, `chat()`, `MedicalTranslationGuard` wired in
- [x] `agent/data/medical_samples.json` — 6 synthetic documents
- [x] `agent/eval_cases.jsonl` — 24 labelled cases (12 tune / 12 test)
- [x] `agent/demo_script.yaml` — scripted conversation turns
- [x] `agent/features.yaml` — empty (no Memory or Gateway)

---

## Phase 3: Upgrade — dependencies and data

- [ ] **Update `requirements.txt`** — add: `pdfminer.six`, `pdf2image`, `pytesseract`, `Pillow`, `reportlab`
  - Import `pdf2image` and `pytesseract` lazily (inside try/except) so agent runs without Tesseract

- [ ] **Create `agent/data/templates/`** — 6 `.txt` synthetic document templates
  - Each file starts with: `FICTIONAL — FOR DEMO/TESTING ONLY. Not a real medical document.`
  - [ ] `clear_prescription.txt` — fictional drug, all values explicit, one warning
  - [ ] `clear_lab_report.txt` — 4 lab values, all within reference ranges, clear interpretation
  - [ ] `ambiguous_prescription.txt` — drug name present, frequency missing, dose partially illegible
  - [ ] `ambiguous_lab_report.txt` — two borderline values, conflicting reference ranges
  - [ ] `medication_concern.txt` — unusual dose note + drug interaction warning (not emergency)
  - [ ] `emergency_case.txt` — severe chest pain + shortness of breath + "CALL EMERGENCY SERVICES"

---

## Phase 4: Upgrade — ingestion and verification modules

- [ ] **Implement `agent/ingestion.py`**
  - [ ] `ingest_uploaded_file(file_bytes, filename) -> dict` with keys: `raw_text`, `method`,
    `filename`, `page_count`, `confidence`, `error`
    - [ ] `.txt` → UTF-8 decode, `confidence=1.0`
    - [ ] `.pdf` → pdfminer.six; if < 20 chars, fall back to pytesseract on first page (`confidence=0.7`)
    - [ ] `.png`/`.jpg`/`.jpeg` → pytesseract OCR (`confidence=0.7`)
    - [ ] Tesseract absent → return `method="error"`, `confidence=0.0`, message "Tesseract is not
      installed or not found on PATH. Install it to enable OCR." — no crash
  - [ ] `extract_clinical_fields(raw_text) -> dict` with keys: `drug_names`, `dosages`,
    `frequencies`, `durations`, `dates`, `warnings`, `unreadable_sections`
    - [ ] Regex patterns only; no inference of missing values
    - [ ] Absent fields are empty lists

- [ ] **Implement `agent/verification.py`**
  - [ ] `verify_translation(original_text, tamil_text, clinical_fields) -> dict`
    - [ ] Check each drug name, dosage, and date appears verbatim in `tamil_text`
    - [ ] Detect altered numerics (value present in source but different in tamil output)
    - [ ] Check warnings referenced at least partially
    - [ ] `score = 1.0 - (missing + altered) / max(1, total_checked)`
    - [ ] `passed = score >= 0.85 and len(altered) == 0`

---

## Phase 5: Upgrade — tools and agent

- [ ] **Upgrade `translate_to_tamil` in `agent/tools.py`**
  - [ ] Replace mock lookup with phrase-dictionary algorithm
  - [ ] `TAMIL_PHRASES` dict with **≥ 40 entries** covering:
    - [ ] Frequency: once/twice/three/four times daily, morning, night, bedtime, every 4-6/8/12 h
    - [ ] Meal relations: after meals, before meals, with food, on empty stomach, 30 min before
    - [ ] Form: tablet, capsule, syrup, injection, drops, ointment, inhaler
    - [ ] Duration: for 3/5/7/14/28 days, for 2 weeks, complete the full course
    - [ ] Action instructions: stop if rash, consult doctor, do not exceed, do not crush,
      avoid alcohol, avoid driving, do not stop suddenly, store in refrigerator, keep out of reach
    - [ ] Lab phrases: within/above/below normal range, borderline, refer to physician, retest required
    - [ ] Discharge phrases: admitted for, discharged on, follow-up on, rest advised
    - [ ] Safety (document-sourced): may cause drowsiness, may cause nausea, take with food if needed
  - [ ] Preservation: drug names, numerics+units, dates copied verbatim
  - [ ] Fallback: unmatched segments → English text + `(மொழிபெயர்க்கப்படவில்லை — உங்கள் மருத்துவரிடம் கேளுங்கள்)`
  - [ ] Returns `{ "original", "tamil", "document_type", "preserved_values" }`

- [ ] **Add `ingest_document` tool to `agent/tools.py`**
  - [ ] `@tool def ingest_document(file_base64: str, filename: str) -> dict`
  - [ ] Decodes base64, calls `ingestion.ingest_uploaded_file`, then `ingestion.extract_clinical_fields`
  - [ ] Returns combined dict (ingestion result + `clinical_fields`)

- [ ] **Add `verify_medical_translation` tool to `agent/tools.py`**
  - [ ] `@tool def verify_medical_translation(original_text: str, tamil_text: str) -> dict`
  - [ ] Calls `ingestion.extract_clinical_fields(original_text)` then `verification.verify_translation`
  - [ ] Returns verification dict

- [ ] **Update `TOOLS` list** in `agent/tools.py` to include the two new tools

- [ ] **Update `agent/agent.py` system prompt** to mention the two new tools and verification step

---

## Phase 6: Upgrade — web UI

- [ ] **Upgrade `demo/server.py`**
  - [ ] Add `POST /api/upload` (multipart form-data, field `file`): read bytes, call
    `ingestion.ingest_uploaded_file`, return JSON with `raw_text`, `method`, `confidence`,
    `page_count`, `clinical_fields`, optional `error`
  - [ ] Add `POST /api/verify`: body `{ original, tamil }`, call `verification.verify_translation`,
    return `{ passed, missing, altered, warnings, score }`

- [ ] **Upgrade `demo/static/index.html`**
  - [ ] Two-tab input: "Upload Document" and "Paste Text"
  - [ ] Upload tab: file picker (`.txt`, `.pdf`, `.png`, `.jpg`, `.jpeg`), extraction preview
    (method, confidence, page count, collapsible raw text)
  - [ ] Paste tab: textarea + document-type selector — existing behaviour
  - [ ] Side-by-side panel: original text (left) + Tamil explanation (right)
  - [ ] Safety badge: CLEAR (green) / NEEDS REVIEW (amber) / EMERGENCY (red)
  - [ ] Verification panel: score, missing values, altered values, warnings (hidden until translation done)
  - [ ] Noto Sans Tamil font from Google Fonts
  - [ ] AWSUGM footer: "Built with the AWS User Group Madurai Strands Decider hackathon kit"

---

## Phase 7: Upgrade — eval cases and tests

- [ ] **Extend `agent/eval_cases.jsonl` to 36 cases (12 tune / 24 test)**
  - [ ] 12 existing tune cases — unchanged
  - [ ] 12 existing test cases — unchanged
  - [ ] Add 12 new test cases (2 per category: clear prescription, clear lab, ambiguous
    prescription, ambiguous lab, medication concern, emergency)
  - [ ] State strings must match the exact format the wiring sends to the decider

- [ ] **Create `tests/test_upgrade.py`**
  - [ ] Ingestion: `.txt` file → `method="txt"`, `confidence=1.0`
  - [ ] Ingestion: minimal PDF → `method="pdf_text"`
  - [ ] Ingestion: Tesseract absent → no crash, `method="error"`, message contains "Tesseract"
  - [ ] `extract_clinical_fields`: known synthetic text → expected drug/dosage/frequency
  - [ ] Verification passing: all values preserved → `passed=True`
  - [ ] Verification missing: one value dropped → `passed=False`, `missing` non-empty
  - [ ] Verification altered: numeric changed → `altered` non-empty
  - [ ] `ingest_document` tool: base64 txt → returns `raw_text` and `clinical_fields`
  - [ ] `verify_medical_translation` tool: returns `passed` and `score`
  - [ ] `translate_to_tamil`: `TAMIL_PHRASES` has ≥ 40 entries
  - [ ] `translate_to_tamil`: drug name preserved verbatim in output
  - [ ] `translate_to_tamil`: unmatched segment → fallback note in output
  - [ ] Decision safety block: known emergency state → `Deny`
  - [ ] Decision guide: known ambiguous state → `Guide`
  - [ ] Decision proceed: known clear state → `Proceed`
  - [ ] Safety enforcement: emergency never bypasses Deny regardless of `is_clear`

---

## Phase 8: Verification and benchmark

- [ ] **Run `./kit test`** — all tests pass (existing + `tests/test_upgrade.py`)
- [ ] **Run `./kit run`** — scripted conversation completes without error
- [ ] **Manual test checklist:**
  - [ ] Upload `.txt` template → extraction preview shows, agent translates
  - [ ] Upload `.pdf` file → text extracted, agent translates
  - [ ] Upload `.png` (if Tesseract installed) → OCR text, agent translates
  - [ ] Upload `.png` (no Tesseract) → clear error message, no crash
  - [ ] Paste clear prescription → full Tamil translation, side-by-side display
  - [ ] Paste ambiguous prescription → partial explanation, professional advisory, no guessed values
  - [ ] Paste emergency case → Deny fires, emergency guidance in reply, 112 present
  - [ ] Verification panel → shows score ≥ 0.85, no missing values for clear case
  - [ ] Safety badge → correct colour for each case type
  - [ ] Drug names and dosages preserved verbatim in Tamil output
- [ ] **Run `./kit bench --split tune`** — review accuracy per question, tune if any < 80%
- [ ] **Run `./kit bench --split test`** — record final numbers (accuracy, latency, cost)
- [ ] Verify test split was never used for tuning

---

## Phase 9: README and submission check

- [ ] `./kit readme` — auto-generate README.md
- [ ] Verify "Built with the AWS User Group Madurai Strands Decider hackathon kit" is present
- [ ] `./kit check` — fix every FAIL

---

## Constraints (carry through all phases)
- All data: synthetic and clearly labelled FICTIONAL — FOR DEMO/TESTING ONLY.
- No real patient data anywhere: code, tests, templates, eval cases, or demo.
- Never alter clinical values. Never guess missing details.
- Emergency guidance always delivered even when tool call is denied.
- For ambiguous docs: explain only clear parts, never fill in missing clinical details.
- No documents stored after response. File bytes in memory only during request handling.
- OCR (Tesseract) is optional: agent must work without it, with a clear error, not a crash.
- All LLM calls via `decider_kit.llm.agent_model()` — no direct boto3 calls.
- `QUESTIONS` dict in `decision.py` importable by `./kit bench`.
- Kit credit line in all generated files, demo footer, README, and article.
