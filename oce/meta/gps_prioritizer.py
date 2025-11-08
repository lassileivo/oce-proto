from __future__ import annotations
from typing import Dict, Any

class GPSPrioritizer:
    name = "GPS-Prioritizer"
    def score(self, partial: Dict[str, Any]) -> Dict[str, Any]:
        # naive combine
        gps = 6.5
        reco = "prototype" if gps < 7.5 else "publish"
        return {"gps_score": gps, "recommendation": reco}
