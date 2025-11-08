from __future__ import annotations
from typing import Dict, Any

class Structure:
    name = "Structure"
    required_headings = ["Thesis","Key Points","Counterpoints","Actions","Next Step"]

    def run(self, user_text: str, context: Dict[str, Any]) -> Dict[str, str]:
        # naive parse for MVP
        thesis = user_text.strip().split("\n")[0][:140] or "Thesis TBD"
        return {
            "Thesis": thesis,
            "Key Points": "- Point 1\n- Point 2",
            "Counterpoints": "- What could be wrong?\n- What if assumptions fail?",
            "Actions": "- Identify criteria\n- Collect one source",
            "Next Step": "Decide Lite/Guided/Pro mode."
        }
