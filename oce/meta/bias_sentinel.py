from __future__ import annotations
from typing import Dict, Any

class BiasSentinel:
    name = "BiasSentinel"
    def assess(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # minimal placeholder
        return {"alerts": [], "exposure": 1, "recursion_depth": context.get("recursions",0)}
