"""Maruthuva Mozhi (மருத்துவ மொழி) — Tamil medical document translation agent.

Translates synthetic medical documents (prescriptions, lab reports, discharge summaries) into
simple Tamil for Tamil-speaking patients and family caregivers. Strands Decider 2B classifies
each document before translation: clear documents are translated, ambiguous ones are flagged
for professional review, and safety emergencies are escalated immediately.

    from agent.agent import HackathonAgent
    out = HackathonAgent().chat("Please translate: Amoxicillin 500mg, one tablet thrice daily for 7 days after meals.")
    out["reply"], out["decisions"]
"""

from __future__ import annotations

import time
from typing import Any

from strands import Agent

from decider_kit import Decider
from decider_kit.llm import agent_model, default_model_id, image_blocks, strip_thinking

from .decision import MedicalTranslationGuard
from .tools import TOOLS

NAME = "Maruthuva Mozhi"

SYSTEM_PROMPT = """You are Maruthuva Mozhi (மருத்துவ மொழி), an AI assistant that helps Tamil-speaking patients and family caregivers understand medical documents.

You translate prescriptions, lab reports, and discharge summaries into simple, clear Tamil.

CRITICAL WORKFLOW (follow EXACTLY):
1. Always call extract_clinical_text FIRST to extract medical instructions.
2. ALWAYS call translate_to_tamil IMMEDIATELY AFTER (this runs through a safety guardrail).
3. If the guardrail denies translation due to safety concerns, call get_emergency_guidance.
4. Never generate medical translations directly — ALWAYS use the translate_to_tamil tool.

GUARDRAIL BEHAVIOR:
- If translate_to_tamil is blocked (verdict=deny or guide), follow the feedback precisely.
- Safety concerns (emergency symptoms, life-threatening situations) → use emergency_guidance.
- Ambiguous/unclear documents (missing dosages, conflicting info) → explain partially + advise consulting a healthcare professional.
- Clear documents → proceed with full translation.

IMPORTANT:
- Always show the original instruction alongside the Tamil explanation.
- NEVER guess missing dosages, diagnose conditions, or recommend changing medication.
- NEVER alter medicine names, dosages, units, or dates — preserve them exactly.
- Be warm and clear. Use simple Tamil that a patient without medical training can understand.

For emergencies: provide the emergency numbers (108 / 112).
For ambiguous documents: end with: இந்த ஆவணம் தெளிவற்றது. ஒரு மருத்துவரை அணுகவும்."""

EAGER_PROMPT = """You are Maruthuva Mozhi, a Tamil medical document translation agent.
Actively translate every medical document the user gives you. Extract text, then translate immediately.
For demos: show all three cases — clear translation, ambiguous flagging, and emergency escalation."""


class HackathonAgent:
    """One Strands agent per session, with the MedicalTranslationGuard wired in."""

    def __init__(self, decider: Decider | None = None, model_id: str | None = None, eager: bool | None = None):
        import os

        self.decider = decider or Decider()
        self.eager = eager if eager is not None else os.environ.get("DEMO_EAGER") == "1"
        self.model_id = model_id or default_model_id()
        self.sessions: dict[str, tuple[Agent, MedicalTranslationGuard]] = {}

    def _session(self, session_id: str) -> tuple[Agent, MedicalTranslationGuard]:
        if session_id not in self.sessions:
            guard = MedicalTranslationGuard(self.decider)
            agent = Agent(
                model=agent_model(self.model_id),
                system_prompt=EAGER_PROMPT if self.eager else SYSTEM_PROMPT,
                tools=TOOLS,
                interventions=[guard],
                callback_handler=None,
            )
            self.sessions[session_id] = (agent, guard)
        return self.sessions[session_id]

    def chat(self, message: str, session_id: str = "default", images: list[Any] | None = None) -> dict[str, Any]:
        """Translate a medical document. `images` (optional): attached photos (paths, bytes or base64)."""
        agent, guard = self._session(session_id)
        before = len(guard.log)
        t0 = time.perf_counter()
        result = agent(
            [*image_blocks(images), {"text": message}] if images else message,
            invocation_state={"images": list(images or [])},
        )
        reply = strip_thinking(str(result))
        return {
            "reply": reply,
            "decisions": guard.log[before:],
            "model_id": self.model_id,
            "latency_ms": round((time.perf_counter() - t0) * 1000),
            "agent": NAME,
            "eager": self.eager,
        }


if __name__ == "__main__":
    import json
    import sys

    a = HackathonAgent()
    messages = sys.argv[1:] or [
        "Please translate this prescription: Amoxicillin 500mg, one tablet three times daily after meals for 7 days. Stop if rash develops.",
        "Translate this lab report: Hemoglobin 13.5 g/dL [Ref: 12-16 female, 13.5-17.5 male]. Gender not recorded. Refer to physician.",
    ]
    for msg in messages:
        print(json.dumps(a.chat(msg), indent=1, ensure_ascii=False))
