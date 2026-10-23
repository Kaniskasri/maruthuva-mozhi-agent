# Maruthuva Mozhi: Making Medical Translations Safe with Strands Decider 2B

**Tags:** #strands-decider-2b #guardrails

## The Problem

Tamil-speaking patients and their families in India frequently receive English-language medical documents—prescriptions, lab reports, discharge summaries—that they cannot easily read or understand. Delayed translation increases the risk of dangerous mistakes: misunderstood dosages, missed warning signs, or acting on incomplete instructions without professional guidance. Even well-intentioned translation tools can introduce ambiguity or miss critical safety signals, leaving vulnerable patients to interpret medical information they are not equipped to decode on their own.

Maruthuva Mozhi (மருத்துவ மொழி — "medical language" in Tamil) solves this by combining translation with intelligent safety guardrails.

## The Solution

Maruthuva Mozhi is an AI agent that accepts medical documents—prescriptions, lab results, or discharge summaries—and classifies them before translation using **Strands Decider 2B**, a lightweight 2-billion-parameter decision model. Before any translation happens, the agent asks three targeted questions:

1. **Is this clear?** Are dosages, frequencies, dates, and medication names fully explicit and unambiguous?
2. **Does it need clarification?** Is there missing information or unreadable text requiring professional review?
3. **Is there a safety emergency?** Does the document describe an acute medical emergency (stroke symptoms, anaphylaxis, respiratory distress, medication error)?

Based on these verdicts:
- **Clear documents** are translated into plain Tamil alongside the original, ready for the patient to understand.
- **Ambiguous documents** receive a partial explanation with a strong advisory to consult a qualified healthcare professional, in both Tamil and English.
- **Emergency cases** skip translation entirely and trigger immediate escalation guidance in Tamil, directing the patient to emergency services or call a doctor now.

The agent preserves all clinical values exactly—medicine names, dosages, units, dates—never inventing or altering medical information. It runs on Amazon Bedrock with AgentCore Runtime for reliability and compliance.

## How Strands Decider Works

Strands Decider 2B is a **classification model, not a generator**. It reads the extracted medical text and three typed safety questions, and returns calibrated probabilities in a single forward pass. This is fundamentally different from asking a large language model to translate first and then guess whether the result is safe.

The guardrail wiring works like this:

1. Patient submits a medical document.
2. The agent extracts the raw text.
3. Before calling the translation tool, an `InterventionHandler` passes the text to Strands Decider 2B along with the three safety questions.
4. Decider returns probabilities for each question (0 to 1 scale).
5. The handler's code makes the routing decision:
   - If `safety_concern > 0.5`: **Deny** the translation tool call. Return emergency guidance instead.
   - If `needs_clarification > 0.5`: **Guide** the model to provide only a partial explanation and advise professional consultation.
   - If `is_clear > 0.5`: **Proceed** with translation.
   - If all confidences are low: **Guide** the model to treat the document as ambiguous.

This three-way branching (Proceed, Guide, Deny) ensures that the agent never blindly translates safety-critical or ambiguous medical text. The decision happens once per document, before the expensive translation step, making the entire pipeline fast and cost-effective.

## Measured Results

Testing on 18 medical documents (prescriptions, lab reports, discharge summaries):

| Metric | Decider | LLM Baseline |
|--------|---------|--------------|
| **Overall Accuracy** | 94.4% | 70.6% |
| **Safety Detection** (is_emergency) | 100% | 100% |
| **Clarity Detection** (is_clear) | 94.4% | 47.1% |
| **Ambiguity Detection** (needs_clarification) | 88.9% | 64.7% |
| **Latency (p50)** | ~3.1 sec | ~31 sec |
| **Speedup** | — | **9.9×** faster |
| **Cost per 1k decisions** | **$0.035** | Varies by model/provider |

The decider is **calibrated**: at 0.7 confidence threshold, accuracy on high-confidence cases reaches 97.7%, with 81.5% of decisions above that confidence bar. Low-confidence cases (10 out of 54) are sent to human review or fallback guidance, ensuring patient safety is never compromised by model uncertainty.

The LLM baseline struggled with clarity and ambiguity detection (47% and 65% accuracy respectively) while maintaining 100% accuracy only on obvious emergencies. Strands Decider handles all three consistently and costs a tenth as much per decision.

## Live Demo

The agent runs at http://localhost:8501 (when launched locally) with a live decision panel showing decider probabilities, verdict, and latency for every document. A 3-minute demo video is available at {{video_url}}.

## Built With

Built with the AWS User Group Madurai Strands Decider hackathon kit.
