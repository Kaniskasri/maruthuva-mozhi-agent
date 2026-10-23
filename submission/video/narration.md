0. Maruthuva Mozhi helps Tamil-speaking patients understand medical documents. Strands Decider checks every document before translation — clear instructions are translated, ambiguous ones are flagged, and safety emergencies are escalated immediately.

1. An AI agent that translates medical documents into Tamil, with Strands Decider classifying each document before translation. What it does: Translate prescriptions, lab reports, and discharge summaries into simple Tamil. Strands Decider classifies every document: clear, ambiguous, or safety escalation. Preserves medicine names, dosages, and dates exactly — never guesses or alters clinical values. Emergency documents trigger immediate guidance in Tamil and English.

2. A clear prescription with explicit dosage and duration — the decider should classify this as safe to translate. The decider scored is clear 0.34, needs clarification 0.30, safety concern 0.11, so the verdict was guide, in 5.0 seconds.

3. An ambiguous lab report — gender is missing, so the normal range is unclear. The decider should flag this for clarification. The decider scored is clear 0.36, needs clarification 0.27, safety concern 0.10, so the verdict was guide, in 5.2 seconds.

4. An emergency escalation case — the decider detects a safety concern and the agent provides emergency guidance without translating. No decision was needed on this turn.

5. On 54 labelled decisions, with the decider on the AWS User Group Madurai hosted API, Strands Decider was 94% accurate at a median of 3149 milliseconds, against 71% and 31166 milliseconds for a hosted open LLM asked the same questions.

6. One forward pass per decision, calibrated probabilities the code can branch on, and Amazon Bedrock for the conversation. Safe, fast, and consistent — even for the most critical documents.