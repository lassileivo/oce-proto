# oce/modules/strategy_mcda.py
from __future__ import annotations
import re
from typing import Dict, Any, List, Tuple

"""
StrategyMCDA
- Lukee A/B/C-vaihtoehdot luonnollisesta kielestä (regex).
- Tukee painoja session_ctx["mcda"]["weights"] tai oletuksia (Impact 0.5, Cost 0.3, Risk 0.2).
- Normalisointi: min–max; hyödyt (+) ja kustannukset (–) käsitellään oikein.
- Hyötyfunktio: U(j) = Σ_i w_i * s_ij.
- Vakavuus-tsekki: +0.10 yhden painon korotus (clamp 0..1) ja katsotaan muuttuuko suositus.
- Palauttaa markdownin + sections_present/missing.
"""

BENEFIT_KEYS = {"impact", "benefit", "value", "score"}
COST_KEYS    = {"cost", "risk", "time", "effort", "price", "budget"}

# --- apu: parsitaan "A (impact 8, cost 7000, risk 0.25)" ja variaatiot
ALT_PATTERNS = [
    r"""
    (?P<label>[A-Z])              # A/B/C
    \s*[:(]\s*
    (?P<body>[^)|;]+)             # impact 8, cost 7000, risk 0.25
    [);]?
    """,
    r"""
    (?<!\w)option\s*(?P<label>[A-Z])\s*[:\-]\s*(?P<body>[^;]+)
    """,
]

KV_PAT = re.compile(
    r"""
    (?P<key>[a-zA-Z_]+)\s*[:=]\s*
    (?P<val>-?\d+(?:\.\d+)?)
    """,
    re.VERBOSE | re.IGNORECASE,
)

def _parse_options(user_text: str) -> Dict[str, Dict[str, float]]:
    text = user_text.strip()
    options: Dict[str, Dict[str, float]] = {}
    for pat in ALT_PATTERNS:
        for m in re.finditer(pat, text, re.VERBOSE | re.IGNORECASE):
            label = m.group("label").upper()
            body = m.group("body")
            kvs = {}
            for km in KV_PAT.finditer(body):
                k = km.group("key").lower().strip()
                v = float(km.group("val"))
                kvs[k] = v
            if kvs:
                options[label] = kvs
    # fallback: "Compare A vs B" → generoi mallit
    if not options and re.search(r"\bcompare\s+([A-Z])\s+vs\s+([A-Z])\b", text, re.I):
        options = {
            "A": {"impact": 8, "cost": 7000, "risk": 0.25},
            "B": {"impact": 7, "cost": 5500, "risk": 0.30},
            "C": {"impact": 6, "cost": 4800, "risk": 0.40},
        }
    return options

def _decide_attribute_polarity(keys: List[str]) -> Dict[str, str]:
    pol: Dict[str, str] = {}
    for k in keys:
        lk = k.lower()
        if lk in BENEFIT_KEYS:
            pol[k] = "benefit"
        elif lk in COST_KEYS:
            pol[k] = "cost"
        else:
            # Heuristiikka: jos nimi näyttää risk/price tyyppiseltä → cost, muuten benefit
            if any(x in lk for x in ("risk", "cost", "price", "loss")):
                pol[k] = "cost"
            else:
                pol[k] = "benefit"
    return pol

def _min_max(values: List[float]) -> Tuple[float, float]:
    lo = min(values)
    hi = max(values)
    return lo, hi

def _normalize_matrix(options: Dict[str, Dict[str, float]], polarity: Dict[str, str]) -> Tuple[Dict[str, Dict[str, float]], Dict[str, Tuple[float, float]]]:
    # tee avainlista vakaassa järjestyksessä
    all_keys = sorted({k for d in options.values() for k in d.keys()})
    # domainit
    domains: Dict[str, Tuple[float, float]] = {}
    for k in all_keys:
        vs = [options[o].get(k) for o in options if k in options[o]]
        if not vs:
            continue
        lo, hi = _min_max(vs)
        domains[k] = (lo, hi)
    # normalisointi
    S: Dict[str, Dict[str, float]] = {o: {} for o in options}
    for k in all_keys:
        if k not in domains:
            continue
        lo, hi = domains[k]
        rng = max(hi - lo, 1e-12)
        for o in options:
            if k not in options[o]:
                continue
            raw = options[o][k]
            # benefit: isompi parempi, cost: pienempi parempi
            if polarity.get(k, "benefit") == "benefit":
                s = (raw - lo) / rng
            else:
                s = (hi - raw) / rng
            S[o][k] = max(0.0, min(1.0, s))
    return S, domains

def _weights_from_ctx(session_ctx: Dict[str, Any], keys: List[str]) -> Dict[str, float]:
    # oletukset
    default = {"impact": 0.5, "cost": 0.3, "risk": 0.2}
    w: Dict[str, float] = {}
    # ctx override
    ctxw = ((session_ctx or {}).get("mcda") or {}).get("weights") if session_ctx else None
    for k in keys:
        lk = k.lower()
        if isinstance(ctxw, dict) and lk in ctxw:
            w[k] = float(ctxw[lk])
        else:
            # perusheuristiikka
            if lk in default:
                w[k] = default[lk]
            else:
                # tasajako uusille
                w[k] = 0.0
    # jos tasajako-osuus jäi 0, jaa muiden ulkopuolinen massa tasan
    s = sum(w.values())
    if s <= 0.0:
        # täysin tuntemattomat → tasapainotus kaikkiin
        n = len(keys) if keys else 1
        w = {k: 1.0 / n for k in keys}
        return w
    if s < 1.0 and keys:
        missing = 1.0 - s
        # Jaa missing tasan niille, joilla paino 0
        zeros = [k for k in keys if w.get(k, 0.0) == 0.0]
        if zeros:
            extra = missing / len(zeros)
            for k in zeros:
                w[k] += extra
        else:
            # skaalataan suhteessa
            factor = 1.0 / s
            for k in keys:
                w[k] *= factor
    elif s > 1.0:
        factor = 1.0 / s
        for k in keys:
            w[k] *= factor
    return w

def _utility(S: Dict[str, Dict[str, float]], weights: Dict[str, float]) -> Dict[str, float]:
    U: Dict[str, float] = {}
    for o, row in S.items():
        u = 0.0
        for k, s in row.items():
            u += weights.get(k, 0.0) * s
        U[o] = u
    return U

def _stability_check(U: Dict[str, float], weights: Dict[str, float], S: Dict[str, Dict[str, float]]) -> Tuple[bool, str]:
    # korota kutakin painoa +0.10 (clamp 0..1) yksitellen ja katso muuttuuko paras
    import math
    if not U:
        return False, "No options."
    base_best = max(U, key=U.get)
    keys = list(weights.keys())
    changed = False
    notes = []
    for k in keys:
        w2 = weights.copy()
        w2[k] = min(1.0, w2.get(k, 0.0) + 0.10)
        # renormalisoi
        s = sum(w2.values())
        if s <= 0:
            continue
        for kk in w2:
            w2[kk] /= s
        U2 = _utility(S, w2)
        best2 = max(U2, key=U2.get)
        if best2 != base_best:
            changed = True
            notes.append(f"Switch if {k}+0.10 → {best2}")
    return (not changed), ("; ".join(notes) if notes else "Stable to +0.10 single-weight tweaks.")

def run(user_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
    session_ctx = (context or {}).get("session_ctx") or {}
    # 1) Parsitaan vaihtoehdot
    options = _parse_options(user_text)
    if not options:
        # fallback: jos kontekstissa olisi options
        ctx_opts = ((context or {}).get("mcda") or {}).get("options") if context else None
        if isinstance(ctx_opts, dict) and ctx_opts:
            options = ctx_opts
        else:
            options = {
                "A": {"impact": 8, "cost": 7000, "risk": 0.25},
                "B": {"impact": 7, "cost": 5500, "risk": 0.30},
                "C": {"impact": 6, "cost": 4800, "risk": 0.40},
            }
    # 2) Määritä attribuuttien polariteetti
    all_keys = sorted({k for d in options.values() for k in d.keys()})
    polarity = _decide_attribute_polarity(all_keys)
    # 3) Normalisointi
    S, domains = _normalize_matrix(options, polarity)
    # 4) Painot
    weights = _weights_from_ctx(session_ctx, all_keys)
    # 5) Hyöty
    U = _utility(S, weights)
    # 6) Suositus
    rec = max(U, key=U.get) if U else None
    # 7) Vakavuus
    stable, note = _stability_check(U, weights, S)

    # Markdown
    md_lines: List[str] = []
    md_lines.append("# StrategyMCDA")
    md_lines.append("**Criteria:**")
    for k in all_keys:
        tag = "benefit" if polarity.get(k) == "benefit" else "cost"
        md_lines.append(f"- {k.capitalize()} ({tag})")
    md_lines.append("\n**Weights:**")
    for k in all_keys:
        md_lines.append(f"- {k.capitalize()}: {weights.get(k,0.0):.3f}")
    md_lines.append("\n**Options:**")
    for o, kv in options.items():
        parts = [f"{k.capitalize()}={kv[k]}" for k in all_keys if k in kv]
        md_lines.append(f"- {o}: " + ", ".join(parts))
    md_lines.append("\n**Scores:**")
    for o in sorted(S.keys()):
        # selite: [k1:0.XXX, k2:0.XXX,...]
        parts = [f"{k.capitalize()}:{S[o].get(k, 0.0):.3f}" for k in all_keys if k in S[o]]
        md_lines.append(f"- {o}: U={U.get(o,0.0):.3f}  |  [{', '.join(parts)}]")

    md_lines.append("\n**Recommendation:**")
    if rec:
        md_lines.append(f"Choose {rec} (highest utility U).")
    else:
        md_lines.append("Insufficient data.")

    md_lines.append("\n**Uncertainty:**")
    md_lines.append(note)

    markdown = "\n".join(md_lines)

    sections_present = ["Criteria", "Weights", "Options", "Scores", "Recommendation", "Uncertainty"]
    sections_missing: List[str] = []
    return {"markdown": markdown, "sections_present": sections_present, "sections_missing": sections_missing}
