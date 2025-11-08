from __future__ import annotations
from typing import Dict, Any, List, Protocol

class OCEModule(Protocol):
    name: str
    required_headings: List[str]
    def run(self, user_text: str, context: Dict[str, Any]) -> Dict[str, str]: ...
