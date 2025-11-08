from __future__ import annotations
from typing import Dict, Any, List, Tuple
import math

# Random Index (Saaty) AHP: n=1..10
RI = {1: 0.00, 2: 0.00, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}

def _normalize_weights(w: Dict[str, float]) -> Dict[str, float]:
    s = sum(max(0.0, v) for v in w.values())
    if s == 0:
        n = len(w) or 1
        return {k: 1.0 / n for k in w}
    return {k: max(0.0, v) / s for k, v in w.items()}

def _weights_from_pairwise(A: List[List[float]], labels: List[str]) -> Tuple[Dict[str, float], float]:
    """Geometrisen keskiarvon menetelmä + CR (Consistency Ratio)."""
    n = len(A)
    # painot
    gm = [math.prod(max(1e-12, A[i][j]) for j in range(n)) ** (1.0 / n) for i in range(n)]
    s = sum(gm)
    w = [g / s for g in gm]
    # lambda_max approksimaatio
    Aw = [sum(A[i][j] * w[j] for j in range(n)) for i in range(n)]
    lam = sum((Aw[i] / max(1e-12, w[i])) for i in range(n)) / n
    CI = (lam - n) / (n - 1) if n > 2 else 0.0
    RI_n = RI.get(n, 1.49)
    CR = CI / RI_n if RI_n > 0 else 0.0
    weights = {labels[i]: w[i] for i in range(n)}
    return weights, CR

def _min_max_normalize(values: List[float], benefit: bool = True) -> List[float]:
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return [1.0 for _ in values]  # kaikki samat → neutraali
    norm = [(v - lo) / (hi - lo) for v in values]
    return norm if benefit else [1.0 - x for x in norm]

def _score_options(criteria: List[Dict[str, Any]], weights: Dict[str, float], options: Dict[str, Dict[str, float]]) -> Tuple[Dict[str, float], Dict[str, Dict[str, float]]]:
    # rakenna kriteerikohtaiset listat
    crit_names = [c["name"] for c in criteria]
    crit_types = {c["name"]: (c.get("type", "benefit").lower() != "cost") for c in criteria}  # True=benefit, False=cost
    # normalisointi
    normalized_per_crit: Dict[str, Dict[str, float]] = {}
    for cname in crit_names:
        vals = [options[o][cname] for o in options]
        norm_vals = _min_max_normalize(vals, benefit=crit_types[cname])
        normalized_per_crit[cname] = {opt: norm_vals[i] for i, opt in enumerate(options.keys())}

    # pisteytys
    utilities: Dict[str, float] = {opt: 0.0 for opt in options}
    for cname in crit_names:
        w = weights.get(cname, 0.0)
        for opt in options:
            utilities[opt] += w * normalized_per_crit[cname][opt]
    return utilities, normalized_per_crit

def _sensitivity_flip(criteria: List[Dict[str, Any]], weights: Dict[str, float], options: Dict[str, Dict[str, float]], utilities: Dict[str, float]) -> List[str]:
    """Karkeat herkkyyshavainnot: nostetaan yhtä painoa +0.10 ja renormalisoidaan."""
    best = max(utilities, key=utilities.get)
    notes = []
    for cname in [c["name"] for c in criteria]:
        tweaked = dict(weights)
        tweaked[cname] = tweaked.get(cname, 0.0) + 0.10
        tweaked = _normalize_weights(tweaked)
        new_u, _ = _score_options(criteria, tweaked, options)
        new_best = max(new_u, key=new_u.get)
        if new_best != best:
            notes.append(f"Jos {cname}-painoa kasvatetaan +0.10 (ja muut skaalataan), voittaja vaihtuu: {best} → {new_best}.")
    if not notes:
        notes.append("Päätös vakaa pienille painomuutoksille (+0.10 yhdessä kriteerissä).")
    return notes

class StrategyMCDA:
    """
    MCDA-mallin kaksi käyttöä:
    1) session_ctx['mcda'] sisältää 'criteria', 'weights' TAI 'pairwise', ja 'options' (raaka-arvot).
    2) ellei dataa ole, ajetaan pieni esimerkkitapaus.
    """
    name = "StrategyMCDA"
    required_headings = ["Criteria","Weights","Options","Scores","Recommendation","Uncertainty"]

    def run(self, user_text: str, context: Dict[str, Any]) -> Dict[str, str]:
        mcda = context.get("mcda", {})

        # -------------- 1) Data --------------
        if mcda:
            criteria: List[Dict[str, Any]] = mcda["criteria"]
            options: Dict[str, Dict[str, float]] = mcda["options"]  # {opt: {crit: value}}
            labels = [c["name"] for c in criteria]

            if "pairwise" in mcda:
                A: List[List[float]] = mcda["pairwise"]
                if len(A) != len(labels):
                    raise ValueError("pairwise-matriisin koko ei täsmää kriteerien määrään.")
                weights, cr = _weights_from_pairwise(A, labels)
            else:
                weights = _normalize_weights(mcda.get("weights", {name: 1.0 for name in labels}))
                cr = None
        else:
            # Esimerkkitapaus: Impact (benefit), Cost (cost), Risk (cost)
            criteria = [
                {"name": "Impact", "type": "benefit"},
                {"name": "Cost", "type": "cost"},
                {"name": "Risk", "type": "cost"},
            ]
            options = {
                "A": {"Impact": 8, "Cost": 7_000, "Risk": 0.25},
                "B": {"Impact": 7, "Cost": 5_500, "Risk": 0.30},
                "C": {"Impact": 6, "Cost": 4_800, "Risk": 0.40},
            }
            weights = {"Impact": 0.5, "Cost": 0.3, "Risk": 0.2}
            cr = None  # ei AHP:tä esimerkissä

        weights = _normalize_weights(weights)

        # -------------- 2) Laskenta --------------
        utilities, normalized = _score_options(criteria, weights, options)
        best = max(utilities, key=utilities.get)
        sensi = _sensitivity_flip(criteria, weights, options, utilities)

        # -------------- 3) Raportointi --------------
        crit_lines = []
        for c in criteria:
            t = c.get("type", "benefit").lower()
            crit_lines.append(f"- {c['name']} ({'benefit' if t!='cost' else 'cost'})")

        w_lines = [f"- {k}: {weights[k]:.3f}" for k in [c["name"] for c in criteria]]
        opt_lines = []
        for o, vals in options.items():
            raw = ", ".join(f"{k}={v}" for k, v in vals.items())
            opt_lines.append(f"- {o}: {raw}")

        score_lines = []
        for o in options:
            parts = []
            for c in criteria:
                cname = c["name"]
                parts.append(f"{cname}:{normalized[cname][o]:.3f}")
            score_lines.append(f"- {o}: U={utilities[o]:.3f}  |  [{', '.join(parts)}]")

        uncertainty_lines = []
        if cr is not None:
            status = "OK" if cr < 0.10 else "HEIKKO"
            uncertainty_lines.append(f"AHP Consistency Ratio (CR) = {cr:.3f} → {status} (raja < 0.10).")
        uncertainty_lines.extend(sensi)

        return {
            "Criteria": "\n".join(crit_lines),
            "Weights": "\n".join(w_lines),
            "Options": "\n".join(opt_lines),
            "Scores": "\n".join(score_lines),
            "Recommendation": f"Valitse {best} (korkein hyöty U).",
            "Uncertainty": "\n".join(uncertainty_lines),
        }
