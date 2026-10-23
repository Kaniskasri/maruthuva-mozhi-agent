"""Quick interactive demo of Maruthuva Mozhi — runs 3 cases and prints results."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from agent.agent import HackathonAgent

a = HackathonAgent()

cases = [
    (
        "CASE 1 — CLEAR PRESCRIPTION",
        "Translate this prescription: Amoxicillin 500mg, one tablet three times daily after meals for 7 days. Stop if rash develops.",
    ),
    (
        "CASE 2 — AMBIGUOUS LAB REPORT",
        "Translate this lab report: Hemoglobin 13.5 g/dL. Gender not recorded. Refer to physician for interpretation.",
    ),
    (
        "CASE 3 — EMERGENCY",
        "Translate: Patient has severe chest pain, shortness of breath, and left arm pain. History: hypertension and diabetes. CALL EMERGENCY SERVICES IMMEDIATELY.",
    ),
]

SEP = "=" * 64

for label, msg in cases:
    print(f"\n{SEP}")
    print(f"  {label}")
    print(SEP)
    print(f"  INPUT:\n  {msg}\n")
    r = a.chat(msg, session_id=label)
    print(f"  REPLY:\n{r['reply']}\n")
    for d in r["decisions"]:
        verdict = d.get("verdict", "?").upper()
        ic  = d.get("is_clear", 0)
        nc  = d.get("needs_clarification", 0)
        sc  = d.get("safety_concern", 0)
        ms  = d.get("decider_ms", 0)
        print(f"  DECIDER VERDICT : {verdict}")
        print(f"    is_clear         {ic:.2f}")
        print(f"    needs_clarif.    {nc:.2f}")
        print(f"    safety_concern   {sc:.2f}")
        print(f"    decider latency  {ms} ms")
    print(f"  total latency    {r['latency_ms']} ms")

print(f"\n{SEP}")
print("  Demo complete. Open http://localhost:8501 for the web UI.")
print(SEP)
