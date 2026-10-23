"""REUSABLE DECISION PATTERN: medical translation safety guardrail  (#guardrails)

What it does
    Before the translation tool runs, Strands Decider 2B checks the extracted medical text:
    - Is it clear, complete, and safe to translate as-is (no missing dosages, no conflicting info)?
    - Does it need clarification (ambiguous timing, missing frequency, unreadable values)?
    - Is there a potential safety or emergency concern (emergency symptoms, dangerous combinations)?
    Clear text is translated; ambiguous text is flagged with an advisory; safety concerns are
    escalated immediately without translation.

Typed questions and options
    is_clear (noul): clear vs ambiguous instruction
    needs_clarification (noul): ambiguity requiring professional review
    safety_concern (noul): emergency or safety-critical situation
    See QUESTIONS below.

Wiring
    `MedicalTranslationGuard` is a Strands `InterventionHandler`; agent/agent.py passes it:
        Agent(..., interventions=[MedicalTranslationGuard(decider)])
    It intercepts calls to `translate_to_tamil` only; other tools run untouched.
    A guided call that is retried unchanged is denied (Guide must converge).

How to reuse it
    Copy this file and adapt QUESTIONS descriptions for your domain's safety criteria.
    The three-question clear/ambiguous/escalate pattern works for any domain where acting on
    incomplete or dangerous information causes harm. Adjust the threshold (default 0.5) and
    the feedback messages to match your domain's language and risk tolerance.
"""

from __future__ import annotations

import json
from typing import Any

from strands.interventions import Deny, Guide, InterventionHandler, Proceed

from decider_kit import Decider
from decider_kit.patterns.guardrails import render_messages

PATTERN_TAG = "#guardrails"
GUARDED_TOOLS = {"translate_to_tamil"}

QUESTIONS = {
    "is_clear": Decider.noul(
        "Is this medical instruction or lab result completely clear and ready to translate with no ambiguity? Dosages, frequencies, dates, and medication names must all be explicit and unambiguous. There must be no conflicting information.",
        {"true": "Yes, completely clear with all details explicit and unambiguous.",
         "false": "No, there is ambiguity, missing information, or conflicting details."}),
    "needs_clarification": Decider.noul(
        "Does this medical instruction or lab result contain any ambiguity that requires professional clarification before the patient acts on it? Look for unreadable text, missing dosages, unclear frequencies, conflicting reference ranges, incomplete instructions, or missing follow-up guidance.",
        {"true": "Yes, professional clarification required before patient acts on this.",
         "false": "No, the instruction is complete and unambiguous."}),
    "safety_concern": Decider.noul(
        "Does this document describe an emergency, acute safety concern, or life-threatening situation that requires immediate professional intervention? Look for symptoms of stroke, heart attack, anaphylaxis, severe allergic reaction, loss of consciousness, respiratory distress, severe acute symptoms, or severe medication errors.",
        {"true": "Yes, immediate emergency or acute safety concern requiring intervention.",
         "false": "No emergency or acute safety concern."}),
}


class MedicalTranslationGuard(InterventionHandler):
    name = "medical-translation-guard"

    def __init__(self, decider: Decider, threshold: float = 0.5):
        self.decider = decider
        self.threshold = threshold
        self.log: list[dict[str, Any]] = []
        self._guided: set[str] = set()

    def before_invocation(self, event, **kwargs):
        self._guided.clear()
        return Proceed()

    def before_tool_call(self, event, **kwargs):
        name = event.tool_use["name"]
        if name not in GUARDED_TOOLS:
            return Proceed()

        args = event.tool_use.get("input") or {}
        sig = f"{name}:{json.dumps(args, sort_keys=True)}"
        if sig in self._guided:
            self.log.append({"pattern": PATTERN_TAG, "tool": name, "verdict": "deny",
                             "reason": "Retried a guided call without changes."})
            return Deny(reason="This translation was already flagged. Please address the concern with a qualified healthcare professional.")

        text = args.get("text", "")
        document_type = args.get("document_type", "unknown")
        state = (
            "Medical document text being translated for a Tamil-speaking patient.\n\n"
            f"--- EXTRACTED MEDICAL TEXT ---\n{text}\n\n"
            f"--- DOCUMENT TYPE ---\n{document_type}"
        )

        a = self.decider.ask(state, QUESTIONS)
        is_clear = a["is_clear"].p_yes or 0.0
        needs_clarification = a["needs_clarification"].p_yes or 0.0
        safety_concern = a["safety_concern"].p_yes or 0.0

        rec = {
            "pattern": PATTERN_TAG,
            "tool": name,
            "document_type": document_type,
            "is_clear": round(is_clear, 3),
            "needs_clarification": round(needs_clarification, 3),
            "safety_concern": round(safety_concern, 3),
            "decider_ms": round(self.decider.last_latency_ms or 0),
        }

        if safety_concern >= self.threshold:
            rec["verdict"] = "deny"
            self.log.append(rec)
            return Deny(
                reason=(
                    "SAFETY ESCALATION: This medical text contains potential emergency or safety-critical information. "
                    "Do NOT translate. Call the emergency_guidance tool immediately and direct the patient to emergency services."
                )
            )

        if needs_clarification >= self.threshold:
            rec["verdict"] = "guide"
            self._guided.add(sig)
            self.log.append(rec)
            return Guide(
                feedback=(
                    "CLARIFICATION NEEDED: This medical text is ambiguous or incomplete. "
                    "Do not translate it as-is. Provide a partial explanation of what is readable, "
                    "and strongly advise the patient to consult a qualified healthcare professional "
                    "before acting on this document. State clearly in Tamil: இந்த ஆவணம் தெளிவற்றது. "
                    "ஒரு மருத்துவரை அணுகவும்."
                )
            )

        if is_clear >= self.threshold:
            rec["verdict"] = "proceed"
            self.log.append(rec)
            return Proceed()

        # Low confidence across all questions — conservative fallback
        rec["verdict"] = "guide"
        self._guided.add(sig)
        self.log.append(rec)
        return Guide(
            feedback=(
                "LOW CONFIDENCE: The guardrail could not clearly classify this medical text. "
                "Treat it as ambiguous. Provide what context you can and advise consulting a "
                "qualified healthcare professional before taking any action based on this document."
            )
        )
