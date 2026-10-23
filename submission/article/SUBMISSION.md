# Maruthuva Mozhi: Hackathon Submission

## Metadata

**Title:** Maruthuva Mozhi: Making Medical Translations Safe with Strands Decider 2B

**Description:** An AI agent that translates medical documents into Tamil for non-English-speaking patients, with Strands Decider 2B guardrails to detect ambiguous or emergency cases before translation happens.

**Tags:** #strands-decider-2b #guardrails

## Submission Components

### 1. Article
- **File:** `submission/article/article.md`
- **Word Count:** ~800 words
- **Content:** Problem statement, solution overview, technical explanation of the decision pattern, measured results (94.4% accuracy, 9.9× speedup, $0.035 per 1k decisions), live demo link, and built-with credit.

### 2. Cover Image
- **File:** `submission/bench/bench-accuracy.png`
- **Description:** Accuracy comparison chart showing Strands Decider vs LLM baseline.

### 3. Demo Video
- **File:** `submission/video/demo.mp4`
- **Duration:** Under 3 minutes
- **Content:** Screen recording of the Maruthuva Mozhi agent with live decision panel, showing a prescription translation workflow and decider verdicts.

### 4. Code Repository
- **Location:** Public GitHub repository (to be published)
- **License:** Apache-2.0
- **Contents:**
  - `agent/AGENT.md` - Use case description
  - `agent/decision.py` - Reusable guardrails decision pattern with PATTERN_TAG `#guardrails`, typed questions, and InterventionHandler wiring
  - `agent/tools.py` - Translation and emergency guidance tools
  - `agent/agent.py` - HackathonAgent with Bedrock model integration
  - `agent/eval_cases.jsonl` - 18 labeled medical document cases for benchmarking
  - `decider_kit/` - Reusable Strands Decider library (kit credit maintained)
  - `submission/bench/results.json` - Full benchmark results
  - README with agent overview, setup instructions, and decision pattern documentation

## Measured Performance

From `submission/bench/results.json`:

- **Decider Accuracy:** 94.44% (51 of 54 correct)
- **Per-Question Accuracy:**
  - `is_clear`: 94.44%
  - `needs_clarification`: 88.89%
  - `safety_concern`: 100% (perfect emergency detection)
- **Latency p50:** 3.1 seconds (Decider) vs 31.2 seconds (LLM)
- **Speedup:** 9.9× faster than LLM baseline
- **Cost:** $0.035 per 1,000 decisions
- **Confident Decisions:** 81.48% of decisions above 0.7 confidence threshold
- **Accuracy When Confident:** 97.73% on high-confidence cases

## Pattern Reusability

The decision pattern in `agent/decision.py` is labeled with `PATTERN_TAG = "#guardrails"` and clearly documented with:
- A docstring headed "REUSABLE DECISION PATTERN:" explaining what it does
- Typed questions and their option sets
- The InterventionHandler wiring that integrates with Strands agents
- Clear copy-and-adapt instructions for other domains

The three-question clear/ambiguous/escalate pattern is applicable to any domain where incomplete or dangerous information causes harm.

## Credit

Built with the AWS User Group Madurai Strands Decider hackathon kit.
