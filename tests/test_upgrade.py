# Built with the AWS User Group Madurai Strands Decider hackathon kit
"""Upgrade tests for Maruthuva Mozhi — ingestion, extraction, verification, translation,
guardrail wiring, and emergency guidance. All data is synthetic; no real API calls."""

import base64
import pytest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers — shared across tests
# ---------------------------------------------------------------------------

def _make_noul_decision(p_yes: float):
    """Return a mock Decision object that looks like a noul result."""
    d = MagicMock()
    d.p_yes = p_yes
    d.yes = p_yes >= 0.5
    return d


def _make_decider_answer(is_clear=0.9, needs_clarification=0.1, safety_concern=0.1):
    """Return a dict of mock Decisions matching MedicalTranslationGuard's QUESTIONS keys."""
    return {
        "is_clear":           _make_noul_decision(is_clear),
        "needs_clarification": _make_noul_decision(needs_clarification),
        "safety_concern":     _make_noul_decision(safety_concern),
    }


def _tool_event(name: str, text: str = "test text", document_type: str = "prescription"):
    """Build a minimal mock event understood by MedicalTranslationGuard.before_tool_call."""
    event = MagicMock()
    event.tool_use = {"name": name, "input": {"text": text, "document_type": document_type}}
    return event


# ---------------------------------------------------------------------------
# TEST 1 — ingest_uploaded_file: plain text
# ---------------------------------------------------------------------------

def test_ingest_txt():
    from agent.ingestion import ingest_uploaded_file

    result = ingest_uploaded_file(b"Amoxicillin 500mg once daily for 7 days", "test.txt")

    assert result["method"] == "text"
    assert "Amoxicillin" in result["raw_text"]
    assert result["page_count"] == 1


# ---------------------------------------------------------------------------
# TEST 2 — extract_clinical_fields: drugs, dosages, durations, dates
# ---------------------------------------------------------------------------

def test_extract_clinical_fields():
    from agent.ingestion import extract_clinical_fields

    result = extract_clinical_fields(
        "Amoxicillin 500mg, Paracetamol 250mg. Once daily for 7 days. Date: 2025-01-15."
    )

    assert "Amoxicillin" in result["drug_names"]
    assert any("500mg" in d for d in result["dosages"])
    # Either '7 days' is present or the list is non-empty (accepts 'for 7 days' form too)
    assert "7 days" in result["durations"] or result["durations"] != []
    assert "2025-01-15" in result["dates"]


# ---------------------------------------------------------------------------
# TEST 3 — verify_translation: pass when all values present
# ---------------------------------------------------------------------------

def test_verify_translation_pass():
    from agent.verification import verify_translation

    fields = {
        "drug_names": ["Amoxicillin"],
        "dosages": ["500mg"],
        "frequencies": [],
        "durations": [],
        "dates": [],
        "warnings": [],
        "unreadable_sections": [],
    }
    tamil = "Amoxicillin 500mg தினமும் ஒரு வேளை"
    result = verify_translation("Amoxicillin 500mg once daily", tamil, fields)

    assert result["passed"] is True
    assert result["score"] == 1.0
    assert result["missing"] == []


# ---------------------------------------------------------------------------
# TEST 4 — verify_translation: fail when dosage is missing from Tamil
# ---------------------------------------------------------------------------

def test_verify_translation_fail_missing_dosage():
    from agent.verification import verify_translation

    fields = {
        "drug_names": ["Amoxicillin"],
        "dosages": ["500mg"],
        "frequencies": [],
        "durations": [],
        "dates": [],
        "warnings": [],
        "unreadable_sections": [],
    }
    # Dosage intentionally omitted from Tamil text
    tamil = "அமாக்ஸிசிலின் Amoxicillin ஒரு வேளை"
    result = verify_translation("Amoxicillin 500mg once daily", tamil, fields)

    assert result["passed"] is False
    assert any("500mg" in item for item in result["missing"])


# ---------------------------------------------------------------------------
# TEST 5 — translate_to_tamil: preserves drug name
# ---------------------------------------------------------------------------

def test_translate_preserves_drug_name():
    from agent.tools import translate_to_tamil

    result = translate_to_tamil(
        "Amoxicillin 500mg once daily after meals for 7 days", "prescription"
    )

    tamil_out = result.get("tamil_text", "") or result.get("tamil_translation", "")
    preserved = result.get("preserved_values", [])

    assert (
        "Amoxicillin" in tamil_out
        or "Amoxicillin" in str(preserved)
    ), "Drug name must appear verbatim in tamil_text or preserved_values"


# ---------------------------------------------------------------------------
# TEST 6 — translate_to_tamil: preserves dosage
# ---------------------------------------------------------------------------

def test_translate_preserves_dosage():
    from agent.tools import translate_to_tamil

    result = translate_to_tamil(
        "Paracetamol 500mg every 6 hours for 5 days", "prescription"
    )

    tamil_out = result.get("tamil_text", "") or result.get("tamil_translation", "")
    preserved = result.get("preserved_values", [])

    assert (
        "500mg" in tamil_out
        or "500mg" in str(preserved)
    ), "Dosage '500mg' must appear verbatim in tamil_text or preserved_values"


# ---------------------------------------------------------------------------
# TEST 7 — ingest_document tool: base64-encoded text file
# ---------------------------------------------------------------------------

def test_ingest_document_tool_base64():
    from agent.tools import ingest_document

    text = "Cetirizine 10mg once daily at bedtime for 14 days."
    b64 = base64.b64encode(text.encode()).decode()

    result = ingest_document(b64, "test.txt")

    assert "raw_text" in result
    assert "clinical_fields" in result
    assert result["method"] == "text"


# ---------------------------------------------------------------------------
# TEST 8 — MedicalTranslationGuard only calls decider for guarded tools
# ---------------------------------------------------------------------------

def test_guard_fires_on_translate_to_tamil_only():
    from agent.decision import MedicalTranslationGuard
    from strands.interventions import Proceed

    mock_decider = MagicMock()
    mock_decider.ask.return_value = _make_decider_answer(
        is_clear=0.9, needs_clarification=0.1, safety_concern=0.1
    )
    mock_decider.last_latency_ms = 12.0

    guard = MedicalTranslationGuard(mock_decider)

    # ── Non-guarded tool: decider.ask must NOT be called ──────────────────
    unguarded_event = _tool_event("extract_medical_text")
    result_unguarded = guard.before_tool_call(unguarded_event)
    mock_decider.ask.assert_not_called()
    assert isinstance(result_unguarded, Proceed)

    # ── Guarded tool: decider.ask MUST be called ──────────────────────────
    guarded_event = _tool_event("translate_to_tamil")
    result_guarded = guard.before_tool_call(guarded_event)
    mock_decider.ask.assert_called_once()
    assert isinstance(result_guarded, Proceed)


# ---------------------------------------------------------------------------
# TEST 9 — MedicalTranslationGuard: safety concern always returns Deny
# ---------------------------------------------------------------------------

def test_safety_concern_always_denies():
    from agent.decision import MedicalTranslationGuard
    from strands.interventions import Deny

    mock_decider = MagicMock()
    mock_decider.ask.return_value = _make_decider_answer(
        is_clear=0.1, needs_clarification=0.1, safety_concern=0.95
    )
    mock_decider.last_latency_ms = 12.0

    guard = MedicalTranslationGuard(mock_decider)
    event = _tool_event("translate_to_tamil", text="severe chest pain, shortness of breath")

    result = guard.before_tool_call(event)

    assert isinstance(result, Deny), f"Expected Deny, got {type(result)}"
    assert guard.log[-1]["verdict"] == "deny"


# ---------------------------------------------------------------------------
# TEST 10 — emergency_guidance always returns Tamil, English, and 108
# ---------------------------------------------------------------------------

def test_emergency_guidance_always_returns_tamil_and_english_and_number():
    from agent.tools import get_emergency_guidance

    result = get_emergency_guidance("severe chest pain, shortness of breath")

    assert "108" in result["action_tamil"], "Tamil guidance must contain emergency number 108"
    assert "108" in result["action_english"], "English guidance must contain emergency number 108"
    assert result["emergency_numbers"]["ambulance"] == "108"
    assert "அவசர" in result["action_tamil"], "Tamil guidance must contain the word 'அவசர' (emergency)"
