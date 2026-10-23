"""Run kit bench with a 7-second delay between decider calls to stay under ugmdu 10 req/min."""
import json, sys, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# Monkey-patch bench.run to add a delay
import decider_kit.bench as _bench
_orig_run = _bench.run

def _slow_run(cases, questions, llm_model, threshold=0.7, decider=None):
    from decider_kit.client import Decider
    d = decider or Decider()
    rows = []
    for i, c in enumerate(cases):
        qs = {k: v for k, v in questions.items() if k in c["expected"]}
        row = {"i": i, "expected": c["expected"]}
        if i > 0:
            time.sleep(7)  # stay under 10 req/min
        ans = d.ask(c["state"], qs)
        row["decider"] = {k: {"label": a.label, "confidence": round(a.confidence, 4)} for k, a in ans.items()}
        row["decider_ms"] = d.last_latency_ms
        row["decider_server_ms"] = d.last_server_ms
        rows.append(row)
        print(f"[bench] {i+1}/{len(cases)}  verdict: { {k: v['label'] for k,v in row['decider'].items()} }", flush=True)

    from decider_kit.config import settings
    import os
    try:
        h = d.health()
        model = h.get("checkpoint") or (h.get("data") or [{}])[0].get("id")
    except Exception:
        model = None
    return {
        "decider_model": model, "rows": rows,
        "summary": _bench.summarise(rows, questions, None, threshold),
        "threshold": threshold, "llm_model": None, "llm_provider": None, "llm_where": None,
        "decider_url": d.url, "decider_mode": settings().decider_mode,
        "ran_at": time.time(),
    }

_bench.run = _slow_run

# Now run both splits
from decider_kit.bench import load_questions, markdown, charts
import os

cases_path = Path("agent/eval_cases.jsonl")
all_cases  = [json.loads(x) for x in cases_path.read_text(encoding="utf-8").splitlines() if x.strip()]
questions  = load_questions("agent.decision:QUESTIONS")
out        = Path("submission/bench")
out.mkdir(parents=True, exist_ok=True)

for split in ("tune", "test"):
    cases = [c for c in all_cases if c.get("split", "test") == split]
    print(f"\n=== {split.upper()} split ({len(cases)} cases) ===", flush=True)
    res = _slow_run(cases, questions, llm_model=None)
    res["split"] = split
    (out / f"results_{split}.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    md = markdown(res)
    (out / f"results_{split}.md").write_text(md + "\n", encoding="utf-8")
    print(f"\n--- {split} results ---\n{md}", flush=True)
    if split == "tune":
        print("\nWaiting 90s before test split to reset rate limit...", flush=True)
        time.sleep(90)

print("\nGenerating charts from test split...", flush=True)
test_res = json.loads((out / "results_test.json").read_text(encoding="utf-8"))
# Reload rows with proper structure for charts
charts(test_res, out)
print("Done. Charts saved to submission/bench/", flush=True)
