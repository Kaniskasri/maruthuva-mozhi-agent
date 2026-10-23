# Maruthuva Mozhi

**An AI agent that translates synthetic medical documents into simple Tamil, protecting patients from acting on unclear, ambiguous, or dangerous instructions before a healthcare professional has reviewed them.**

An agent on AWS that hands one decision to **Strands Decider 2B** and the conversation to **Amazon Bedrock**. Decision pattern: `#guardrails`. Tags: `#strands-decider-2b` `#guardrails`.

- Video: (add the YouTube/Vimeo link)
- Article: (add the AWS Builder Center link)
- Deployed: run `./kit deploy`

## The project

## Use Case

- **Pitch:** An AI agent that translates synthetic medical documents into simple Tamil, protecting patients from acting on unclear, ambiguous, or dangerous instructions before a healthcare professional has reviewed them.
- **Who it is for:** Tamil-speaking patients and family caregivers in India who receive English-language prescriptions, lab reports, and discharge summaries they cannot easily understand.
- **Features:**
  - Accepts prescription, lab report, and discharge summary text
  - Classifies every document with Strands Decider 2B before translating (guardrails pattern)
  - Clear documents: translated into plain Tamil with the original shown alongside
  - Ambiguous documents: partial translation with advisory to consult a healthcare professional
  - Escalation cases: emergency guidance in Tamil and English; agent does not proceed with translation
  - Preserves medicine names, dosages, units, and dates exactly — never guesses or alters clinical values
  - Deployed on Amazon Bedrock AgentCore Runtime
- **The decision handed to Strands Decider 2B:** Before translating, is this medical text clear and safe to translate as-is, does it need clarification, or does it represent a potential safety emergency? (`#guardrails`)
- **Why a decision model:** The classification must be fast, consistent, and return a calibrated confidence number the code can branch on — a large LLM adds latency and cost to every translation, and hallucinated confidence is dangerous in a medical context.
- **Data:** Synthetic, clearly fictional medical documents only. No real patient identifiers.
- **Amazon Bedrock:** The conversation and tool calls (Amazon Nova Pro by default, or qwen3.5-4b via ugmdu for local development).



## How it is built

Strands Agents with Amazon Bedrock for the generative part, the tools in `agent/tools.py`, deployed to Amazon Bedrock AgentCore Runtime, and one decision handed to Strands Decider 2B at a clear seam in the agent's path.

Every Amazon Bedrock model id is set in `.env` (`BEDROCK_MODEL_ID`, and `BEDROCK_SMALL/MEDIUM/LARGE_MODEL_ID` for routing), Amazon Nova by default.



## Reusable decision pattern: medical translation safety guardrail  (#guardrails)

The pattern lives in [`agent/decision.py`](agent/decision.py), labelled `REUSABLE DECISION PATTERN`. It contains the typed questions and their options, the wiring that puts the decision in the agent's path, and a note on how to reuse it:

```text
REUSABLE DECISION PATTERN: medical translation safety guardrail  (#guardrails)

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
```

Typed questions:

```python
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
```

## Measured

Decider: strands-decider-2b-hobson-v19 (ugmdu). 18 labelled cases, 54 decisions.

| | Strands Decider 2B | qwen3.5-4b |
|---|---|---|
| Accuracy | 94.4% | 70.6% |
| Latency p50 per decision | 3149 ms | 31166 ms |
| Latency p95 | 3515 ms | 111576 ms |
| Cost per 1,000 decisions | $0.0350 | $0.0000 |
| Answered alone at confidence >= 0.7 | 81% | 100% |
| Accuracy when confident | 97.7% | 70.6% |

At the median the decider was 9.9x faster than the LLM.

Reproduce with `./kit bench` (cases in `agent/eval_cases.jsonl`; charts in `submission/bench/`).

## Run it

```bash
./kit setup        # checks your machine and AWS, sets up Strands Decider 2B (local model or hosted API)
./kit demo         # web UI at http://localhost:8501
./kit bench        # the decision vs an Amazon Bedrock LLM
./kit deploy       # Amazon Bedrock AgentCore Runtime
```

Requirements: Python 3.10+, AWS credentials with Amazon Bedrock access, and for deploying, Node 20+ with the AgentCore CLI (`./kit agentcore-cli`).

## Credits

Built with the AWS User Group Madurai Strands Decider hackathon kit (https://github.com/awsugmdu). The kit's reusable library (`decider_kit/`, the demo UI, the video and article tooling, and the Kiro steering, skills and hooks) is the user group's; the agent in `agent/` is mine. Strands Decider: https://github.com/strands-labs/strands-decider (Apache-2.0).

Licence: Apache-2.0 (see LICENSE).
