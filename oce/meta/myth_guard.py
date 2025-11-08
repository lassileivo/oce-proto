from __future__ import annotations
import re
from typing import Dict, Any, List

_STRONG_PATTERNS = [
    r"\balways\b", r"\bnever\b", r"\bmust\b", r"\bguarantee(d)?\b",
    r"\bik(i|u)inä\b", r"\baina\b", r"\bei koskaan\b", r"\bpakko\b",
]

class MythGuard:
    """
    Tunnistaa vahvat/absoluuttiset väitteet ja ehdottaa vastaväitteen rungon
    sekä spaced-reinforcement -aikataulun (7 pv, 60 pv).
    """
    name = "MythGuard"

    def analyze(self, assembled_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        findings: List[str] = []
        for pat in _STRONG_PATTERNS:
            if re.search(pat, assembled_text, flags=re.IGNORECASE):
                findings.append(pat)

        if not findings:
            return {"status": "clean", "findings": [], "recommendation": "No strong claims detected."}

        rebuttal = (
            "Vastaväite: etsi poikkeustapauksia ja rajaa väitettä (olosuhteet, aika, yleisö). "
            "Ehdota testattava ehto: 'Väite pätee kun X, mutta rikkoutuu kun Y'."
        )

        reinforcement = {
            "suggested_days": [7, 60],
            "note": "Kertaus 7 pv ja 60 pv kuluttua parantaa pysyvyyttä."
        }

        return {
            "status": "flagged",
            "findings": findings,
            "rebuttal": rebuttal,
            "reinforcement": reinforcement
        }
