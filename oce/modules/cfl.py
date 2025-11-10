# oce/modules/cfl.py
from __future__ import annotations
import re
from typing import Dict, Any, List, Tuple

"""
CFL — Critical Falsification Loop (Runner)
Tuotos:
- Falsifiable Claim
- Counterarguments
- Tests / Predictions
- Status
- Uncertainty

Heuristiikka:
- Löytää väitteen user_textistä (esim. lauseet joissa "X causes Y", "A increases B", "If ... then ...").
- Ellei löydy, muodostaa neutraalin hypoteesin sen perusteella, mistä käyttäjä puhuu.
- Luo 2–4 testattavaa ennustetta (mittari, suunta, raja-arvo).
- Luo 2–3 vastaväitettä (vaihtoehtoinen selitys / mittausvirhe / konfounderi).
- Status: {untested | partially supported | contradicted}, jos session_ctx antaa vihjeen.
"""

# yksinkertaisia claim-signaaleja
CLAIM_PATS = [
    r"\b(if .+ then .+)\b",
    r"\b([A-Za-z][\w\s\-]+)\s+causes\s+([A-Za-z][\w\s\-]+)\b",
    r"\b([A-Za-z][\w\s\-]+)\s+increases\s+([A-Za-z][\w\s\-]+)\b",
    r"\b([A-Za-z][\w\s\-]+)\s+reduces\s+([A-Za-z][\w\s\-]+)\b",
]

def _extract_claim(text: str) -> str | None:
    t = text.strip()
    # If-then ensin
    m = re.search(CLAIM_PATS[0], t, re.IGNORECASE)
    if m:
        return m.group(1).strip().rstrip(".")
    # verbilauseet
    for pat in CLAIM_PATS[1:]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            subj = m.group(1).strip()
            obj = m.group(2).strip()
            verb = "→"
            if "increases" in pat:
                verb = "↑→"
            elif "reduces" in pat:
                verb = "↓→"
            return f"{subj} {verb} {obj}"
    return None

def _guess_domain(text: str) -> str:
    tl = text.lower()
    if any(w in tl for w in ("risk", "loss", "probability", "variance", "mitigation")):
        return "risk"
    if any(w in tl for w in ("impact", "cost", "benefit", "utility", "mcda", "option")):
        return "decision"
    if any(w in tl for w in ("simulate", "experiment", "hypothesis", "measurement", "data")):
        return "science"
    return "general"

def _default_claim(domain: str) -> str:
    if domain == "risk":
        return "Mitigation X reduces expected loss (EL) by ≥ 20% compared to baseline."
    if domain == "decision":
        return "Option A yields higher multi-criteria utility U than Option B in ≥ 70% of reasonable weight perturbations."
    if domain == "science":
        return "Variable X has a positive effect on Y (β>0) when controlling for Z."
    return "Intervention X improves outcome Y under clearly stated conditions."

def _predictions_for(domain: str, text: str) -> List[str]:
    preds: List[str] = []
    if domain == "risk":
        preds = [
            "Observed EL_after ≤ 0.8·EL_before over next N periods.",
            "VaR95_after < VaR95_before given independent risk assumption.",
            "ROI(mitigation) ≥ 1.0 when costs are fully loaded."
        ]
    elif domain == "decision":
        preds = [
            "U_A > U_B for weight shifts of +0.10 on any single criterion (renormalized).",
            "Recommendation stable after ±20% noise in measurements.",
            "Sensitivity tornado shows Impact dominates rank order."
        ]
    elif domain == "science":
        preds = [
            "Estimate β̂_X>0 with 95% CI not crossing 0 in preregistered model.",
            "Pre-registered test power ≥ 0.8 with effect size d ≥ 0.3.",
            "Out-of-sample RMSE improves vs. baseline by ≥ 10%."
        ]
    else:
        preds = [
            "A priori success metric improves by ≥ 15% vs. baseline within T.",
            "Effect replicates in independent sample with compatible magnitude.",
            "No single confounder explains >50% of observed effect."
        ]
    return preds

def _counterargs_for(domain: str) -> List[str]:
    if domain == "science":
        return [
            "Konfounderi Z selittää yhteyden X↔Y.",
            "Mallin spesifikaatio väärä (omitted variables / väärä funktiomuoto).",
            "Mitta-asteikko tai instrumentti epästabiili (mittausvirhe).",
        ]
    if domain == "risk":
        return [
            "Riskit korreloivat (riippumattomuusoletus rikkoo).",
            "Mitigoinnin kustannukset aliarvioitu (piilokulut).",
            "Tail-risk dominoi odotusarvon (EL) edun.",
        ]
    if domain == "decision":
        return [
            "Painot eivät heijasta todellista preferenssiä / sidosryhmäpainot.",
            "Attribuuttien min–max vääristää skaalausta (outlierit).",
            "Data-arviot (impact/cost/risk) biasoituneita.",
        ]
    return [
        "Valikoitumisharha: ryhmä ei edusta populaatiota.",
        "Aikasidonnaisuus: vaikutus katoaa T aikayksikössä.",
        "Ympäristötekijä W selittää vaikutuksen.",
    ]

def _status_from_ctx(ctx: Dict[str, Any]) -> str:
    st = ((ctx or {}).get("cfl") or {}).get("status")
    if isinstance(st, str) and st.lower() in {"untested","partially supported","contradicted"}:
        return st.lower()
    return "untested"

def run(user_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
    domain = _guess_domain(user_text)
    claim = _extract_claim(user_text) or _default_claim(domain)
    preds = _predictions_for(domain, user_text)
    counters = _counterargs_for(domain)
    status = _status_from_ctx((context or {}).get("session_ctx") or {})

    md: List[str] = []
    md.append("# CFL")
    md.append("**Falsifiable Claim:**")
    md.append(f"- {claim}")
    md.append("\n**Counterarguments:**")
    for c in counters:
        md.append(f"- {c}")
    md.append("\n**Tests / Predictions:**")
    for p in preds:
        md.append(f"- {p}")
    md.append("\n**Status:**")
    md.append(f"{status}")
    md.append("\n**Uncertainty:**")
    md.append("Pre-register metrics, guard against p-hacking; specify stopping rules; report all outcomes.")

    return {
        "markdown": "\n".join(md),
        "sections_present": ["Falsifiable Claim","Counterarguments","Tests / Predictions","Status","Uncertainty"],
        "sections_missing": []
    }
