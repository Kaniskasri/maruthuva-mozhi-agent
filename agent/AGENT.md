# Maruthuva Mozhi (மருத்துவ மொழி)

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
