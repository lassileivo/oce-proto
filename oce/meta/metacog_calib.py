from __future__ import annotations
from typing import Dict, Any, Optional

class MetacogCalib:
    """
    Laskee metakognitiikan kalibraatioindikaattorin.

    session_ctx odottaa (valinnaisesti):
      - self_prob:   käyttäjän oma todennäköisyysarvio (0..1)
      - model_prob:  mallin arvio (0..1) — jos puuttuu, käytetään varovaista oletusta (0.60) MVP:ssä
      - outcome:     0/1 jos lopputulos jo tiedossa → Brier-score lasketaan

    Palauttaa:
      - state: 'overconfident' / 'underconfident' / 'aligned'
      - delta: model_prob - self_prob
      - brier_user / brier_model: jos outcome annettu
    """
    name = "MetacogCalib"

    def assess(self, context: Dict[str, Any]) -> Dict[str, Any]:
        sp: Optional[float] = context.get("self_prob")
        mp: Optional[float] = context.get("model_prob")
        outcome = context.get("outcome")  # 0 tai 1

        result = {"status": "insufficient-data"}
        if sp is None or not (0.0 <= sp <= 1.0):
            result["message"] = "Anna 'self_prob' väliltä 0..1."
            return result

        if mp is None:
            mp = 0.60  # MVP-varovaisuus, voidaan myöhemmin korvata mallin todellisella arviolla

        diff = mp - sp
        if diff > 0.10:
            state = "underconfident"
        elif diff < -0.10:
            state = "overconfident"
        else:
            state = "aligned"

        payload = {
            "status": "ok",
            "self_prob": round(sp, 3),
            "model_prob": round(mp, 3),
            "delta": round(diff, 3),
            "state": state,
        }

        if outcome in (0, 1):
            from math import pow
            payload["brier_user"] = round(pow(sp - outcome, 2), 4)
            payload["brier_model"] = round(pow(mp - outcome, 2), 4)

        if state == "overconfident":
            payload["advice"] = "Yliluottamus: laske varmuutta ~10–20 %-yks tai kokoa lisää evidenssiä."
        elif state == "underconfident":
            payload["advice"] = "Aliluottamus: perustelut vahvat — varmuutta voi lisätä maltillisesti."
        else:
            payload["advice"] = "Kalibraatio linjassa. Jatka samalla kurilla."

        return payload
