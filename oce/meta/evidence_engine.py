from __future__ import annotations
from typing import Dict, Any

class EvidenceEngine:
    name = "EvidenceEngine"
    def check(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # MVP: if claim seems timely but no sources, warn (placeholder)
        timely = context.get("timely", False)
        citations = context.get("citations", [])
        warn = timely and not citations
        return {"evidence_score": 6.0 if not warn else 3.0, "missing_sources": warn}
