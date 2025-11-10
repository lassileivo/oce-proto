# oce/modules/structure.py
from __future__ import annotations
from typing import Dict, Any, List

def _intent(context: Dict[str, Any]) -> str:
    # Router tallentaa intentin usein context["intent"] tai json_summaryssa.
    # Tässä varma fallback: etsi session_ctx:stä tai contextista.
    intent = (context or {}).get("intent")
    if isinstance(intent, str):
        return intent
    # router saattaa laittaa session_ctx["intent"]
    sess = (context or {}).get("session_ctx") or {}
    if isinstance(sess.get("intent"), str):
        return sess["intent"]
    return "general"

def _scientific_frame(user_text: str) -> str:
    lines: List[str] = []
    lines.append("# Structure")
    lines.append("**Hypothesis:**")
    lines.append("- Formulate a precise, testable statement tied to the question at hand.")
    lines.append("\n**Predictions:**")
    lines.append("- What observable patterns should occur if the hypothesis is true?")
    lines.append("- Define expected direction/magnitude and confidence threshold.")
    lines.append("\n**Variables:**")
    lines.append("- X (independent), Y (dependent), Z (controls).")
    lines.append("- Measurement scales and operational definitions.")
    lines.append("\n**Method:**")
    lines.append("- Design (experiment / quasi / observational), sampling, power.")
    lines.append("- Analysis plan (model, metrics, alpha, corrections).")
    lines.append("\n**Data Needs:**")
    lines.append("- Sources, collection window, quality checks, preregistration pointers.")
    lines.append("\n**Next Step:**")
    lines.append("Collect minimal dataset, run pilot analysis, refine hypothesis or stop.")
    return "\n".join(lines)

def _general_frame(user_text: str) -> str:
    lines: List[str] = []
    lines.append("# Structure")
    lines.append("**Thesis:**")
    lines.append(f"{user_text.strip() or 'You are exploring a strategic overview.'}")
    lines.append("\n**Key Points:**")
    lines.append("- Clarify long-term goal (2–3 years).")
    lines.append("- List constraints and resources (time, money, skills).")
    lines.append("- Define decision timeline and success criteria.")
    lines.append("\n**Counterpoints:**")
    lines.append("- What if priorities change mid-course?")
    lines.append("- What if constraints tighten (budget/time)?")
    lines.append("\n**Actions:**")
    lines.append("- Write 1–3 concrete outcomes.")
    lines.append("- Pick a planning horizon (e.g., 24–36 months).")
    lines.append("- List top 3 constraints and 3 resources.")
    lines.append("\n**Next Step:**")
    lines.append("Answer: goal, constraints, timeframe.")
    return "\n".join(lines)

def run(user_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
    intent = _intent(context).lower()
    if intent in {"scientific","science"}:
        md = _scientific_frame(user_text)
        sections_present = ["Hypothesis","Predictions","Variables","Method","Data Needs","Next Step"]
    else:
        md = _general_frame(user_text)
        sections_present = ["Thesis","Key Points","Counterpoints","Actions","Next Step"]

    return {
        "markdown": md,
        "sections_present": sections_present,
        "sections_missing": []
    }
