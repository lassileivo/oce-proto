from __future__ import annotations
from typing import Dict, Any

class SafetyGate:
    name = "SafetyGate"
    def decide(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # MVP: always allow
        return {"status": "allow", "reasons": []}
