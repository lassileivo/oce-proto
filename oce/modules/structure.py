# oce/modules/structure.py
from __future__ import annotations
from typing import Dict

def run(user_text: str, context: Dict) -> Dict:
    """
    Structure v2 — tuottaa selkeän rungon strategiseen aloitukseen.
    Ei riipu muistista; toimii heti 'cold start' -tilassa.
    """
    thesis = "You are exploring a strategic overview."
    key_points = [
        "Clarify long-term goal (2–3 years).",
        "List constraints and resources (time, money, skills).",
        "Define decision timeline and success criteria.",
    ]
    counter = [
        "What if priorities change mid-course?",
        "What if constraints tighten (budget/time)?",
    ]
    actions = [
        "Write 1–3 concrete outcomes.",
        "Pick a planning horizon (e.g., 24–36 months).",
        "List top 3 constraints and 3 resources.",
    ]

    md = [
        "# Structure",
        "**Thesis:**",
        thesis,
        "",
        "**Key Points:**",
        *[f"- {x}" for x in key_points],
        "",
        "**Counterpoints:**",
        *[f"- {x}" for x in counter],
        "",
        "**Actions:**",
        *[f"- {x}" for x in actions],
        "",
        "**Next Step:**",
        "Answer: goal, constraints, timeframe.",
    ]

    return {
        "markdown": "\n".join(md),
        "sections_present": ["Thesis","Key Points","Counterpoints","Actions","Next Step"],
        "sections_missing": [],
    }
