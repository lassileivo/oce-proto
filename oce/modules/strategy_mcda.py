# oce/modules/strategy_mcda.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import re
import math

# ---- Konfiguraatio / aliaset ----
CRITERIA_ALIASES = {
    "Impact": ["impact", "benefit", "value", "utility", "gain", "score"],
    "Cost":   ["cost", "price", "budget", "expense", "capex", "opex", "€", "eur", "euro"],
    "Risk":   ["risk", "p", "prob", "probability", "uncertainty", "chance"],
}

# mikä kriteeri on "benefit" (suurempi parempi) vs "cost" (pienempi parempi)
CRITERIA_KIND = {
    "Impact": "benefit",
    "Cost":   "cost",
    "Risk":   "cost",
}

DEFAULT_WEIGHTS = {"Impact": 0.5, "Cost": 0.3, "Risk": 0.2}
DEFAULT_CRITERIA = ["Impact", "Cost", "Risk"]

# ---- Parsaustyökalut ----

NUM_RE = re.compile(
    r"""
    (?P<sign>[-+])?
    (?P<int>\d{1,3}(?:[.,]\d{3})*|\d+)
    (?:[.,](?P<frac>\d+))?
    (?P<unit>\s*[kKmM%]?)    # k=1e3, M=1e6, %= /100
    """,
    re.VERBOSE,
)

LABEL_RE = r"[A-Za-z][\w\-]*"

# A) "A (impact 8, cost 7k, risk 25%)" -tyyppinen
PAREN_OPT_RE = re.compile(
    rf"\b(?P<label>{LABEL_RE})\s*\((?P<fields>[^)]+)\)"
)

# B) "A: impact 8 cost 7000 risk .25" tai "A impact=8 cost=7000 ..."
INLINE_OPT_RE = re.compile(
    rf"\b(?P<label>{LABEL_RE})\s*[:\-]?\s+(?P<fields>[^.;,\n]+)"
)

WEIGHTS_RE = re.compile(
    r"\bweights?\b\s*[:(]?(?P<fields>[^)\n]+)\)?",
    re.IGNORECASE,
)

def _norm_key(k: str) -> str:
    return k.strip().lower()

def _alias_to_canonical(name: str) -> str | None:
    n = _norm_key(name)
    for canon, aliases in CRITERIA_ALIASES.items():
        if n == _norm_key(canon) or n in (_norm_key(a) for a in aliases):
            return canon
    return None

def _parse_number(raw: str) -> float | None:
    m = NUM_RE.search(raw.strip())
    if not m:
        return None
    sgn = -1.0 if m.group("sign") == "-" else 1.0
    int_part = m.group("int").replace(",", "").replace(".", "")
    frac = m.group("frac")
    if frac:
        # alkuperäisessä "int" me poistimme erotinmerkit; rakennetaan decimal itse
        num = float(int_part) / (10 ** len(frac)) + float("0." + frac)
        # Yllä oleva tuottaa hieman virhettä jos int_part olikin '1234' ja frac '56'.
        # Helpompi: korvataan tuhaterottimet pisteillä, pilkku desimaaliksi jos tarvitsee.
        # Mutta käytännössä: tehdään luotettava re-rakennus:
        pass
    # Järjestä simppelisti: ota vain numeromerkkejä, yksi piste desimaaliksi
    raw_digits = (m.group("int") or "")
    raw_frac = m.group("frac") or ""
    base = raw_digits.replace(",", "").replace(" ", "").replace("\u202f", "")
    base = base.replace(".", "")  # poista mahdolliset tuhannerottimet
    if raw_frac:
        base = base + "." + raw_frac
    try:
        val = float(base)
    except Exception:
        return None

    unit = (m.group("unit") or "").strip()
    if unit.lower() == "k":
        val *= 1_000.0
    elif unit.lower() == "m":
        val *= 1_000_000.0
    elif unit == "%":
        val /= 100.0

    return sgn * val

def _split_fields(s: str) -> List[str]:
    # kentät eroteltu pilkulla tai välilyönnein; sallitaan "impact=8 cost=7000"
    # hajotetaan ensin pilkulla, sen jälkeen jos ei löydy "=", yritetään parittain (key value)
    parts = [x.strip() for x in re.split(r"[;,]", s) if x.strip()]
    if len(parts) == 1 and "=" not in parts[0]:
        # yritä rikkoa tilavälillä; esim "impact 8 cost 7000 risk .25"
        tmp = parts[0].strip()
        return [x.strip() for x in re.split(r"\s{2,}|\s(?=[A-Za-z])", tmp) if x.strip()]
    return parts

def _parse_keyvals(field_str: str) -> Dict[str, float]:
    """
    Palauttaa {CanonicalCriterion: value} jos osuu.
    Hyväksyy muodot:
      - "impact=8"
      - "impact 8"
      - "benefit: 7"
      - "risk=25%"
      - "price=5,500€"
    """
    out: Dict[str, float] = {}
    fields = _split_fields(field_str)

    # tee myös "key val key val" -paritus jos monisanaisia
    tokens = []
    for f in fields:
        # jos "key=val" tai "key:val"
        if "=" in f or ":" in f:
            tokens.append(f)
        else:
            # jätä sellaisenaan, parsitaan myöhemmin parituksena
            tokens.append(f)

    # 1) Käsittele selkeät "key=val"/"key:val"
    for t in list(tokens):
        if "=" in t:
            k, v = t.split("=", 1)
        elif ":" in t:
            k, v = t.split(":", 1)
        else:
            continue
        canon = _alias_to_canonical(k)
        if canon is None:
            continue
        num = _parse_number(v)
        if num is not None:
            out[canon] = num

    # 2) Käsittele "key value" muodot
    #    Etsi "word number" -pareja
    kv_pairs = re.findall(r"([A-Za-z€]+)\s+([+−\-]?\d[\d.,]*(?:\s*[kKmM%])?)", field_str)
    for k, v in kv_pairs:
        canon = _alias_to_canonical(k)
        if canon is None:
            continue
        num = _parse_number(v)
        if num is not None and canon not in out:
            out[canon] = num

    return out

def _parse_options(text: str) -> Dict[str, Dict[str, float]]:
    """
    Yrittää ensin ( ... ) -rakenteet, sitten inline-linjat.
    Palauttaa: {"A":{"Impact":..,"Cost":..,"Risk":..}, ...}
    """
    options: Dict[str, Dict[str, float]] = {}

    # (1) parenteesi-optio
    for m in PAREN_OPT_RE.finditer(text):
        label = m.group("label")
        fields = m.group("fields")
        kv = _parse_keyvals(fields)
        if kv:
            options[label] = kv

    # (2) inline-optio, jos ei löytynyt tarpeeksi
    #     suodatetaan painot pois, ettei se sekoitu A/B-optioihin
    text_wo_weights = WEIGHTS_RE.sub("", text)
    for m in INLINE_OPT_RE.finditer(text_wo_weights):
        label = m.group("label")
        fields = m.group("fields")
        # jos tämä on ilmeinen vertailun intro (e.g. "Compare A vs B"), ohita
        if _norm_key(label) in {"compare", "vs", "versus"}:
            continue
        kv = _parse_keyvals(fields)
        # vaadi vähintään yhtä tunnistettua kriteeriä, ettei se nappaa satunnaisia lauseita
        if kv:
            # älä ylikirjoita jo löydettyä (parens on etusijalla)
            options.setdefault(label, kv)

    return options

def _parse_weights(text: str, crits: List[str]) -> Dict[str, float] | None:
    m = WEIGHTS_RE.search(text)
    if not m:
        return None
    kv = _parse_keyvals(m.group("fields"))
    # palauta vain tunnetut kriteerit
    w = {c: kv[c] for c in crits if c in kv}
    return w or None

def _minmax(x: float, lo: float, hi: float, reverse=False) -> float:
    if hi == lo:
        return 0.0
    v = (x - lo) / (hi - lo)
    return 1.0 - v if reverse else v

# ---- Pääajologiikka ----

def run(user_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    StrategyMCDA v3 – luonnollisen kielen A/B/C-lukija (regex):
      - Parsii vaihtoehdot ja painot tekstistä
      - Yhtenäistää kriteerit aliaksilla
      - Laskee min–max-normalisoinnin (benefit vs cost)
      - Tekee herkkyysanalyysin (+0.10 yksittäiseen painoon)
    """
    text = user_text.strip()

    # 1) Parse options
    options = _parse_options(text)
    diag: List[str] = []
    if not options:
        # fallback: käytä demodataa
        options = {
            "A": {"Impact": 8, "Cost": 7000, "Risk": 0.25},
            "B": {"Impact": 7, "Cost": 5500, "Risk": 0.30},
            "C": {"Impact": 6, "Cost": 4800, "Risk": 0.40},
        }
        diag.append("No structured options found in text → using demo A/B/C.")

    # 2) Kokoa käytetyt kriteerit (union kaikista optioneista, mutta järjestä oletuslista etusijalle)
    crits_found = set()
    for o in options.values():
        for k in o.keys():
            if k in CRITERIA_KIND:
                crits_found.add(k)

    if not crits_found:
        # jos ei mitään tunnistettuja kriteerejä → käytä oletuskolmikkoa
        crits = DEFAULT_CRITERIA[:]
        diag.append("No known criteria detected → using defaults: Impact/Cost/Risk.")
        # jos puuttuu arvo, emme voi laskea; pidä fallback-options
    else:
        # järjestä: ensin oletusjärjestyksessä, sitten loput
        crits = [c for c in DEFAULT_CRITERIA if c in crits_found] + \
                [c for c in sorted(crits_found) if c not in DEFAULT_CRITERIA]

    # 3) Täydennä puuttuvia arvoja (keskiarvo muiden perusteella tai heuristinen oletus)
    #    pidetään yksinkertaisena: jos jostain optionista puuttuu kriteeri, täytetään mediaanilla.
    for c in crits:
        vals = [o[c] for o in options.values() if c in o]
        if not vals:
            # jos kaikilta puuttuu c, tiputetaan tämä kriteeri pois
            for o in options.values():
                if c in o:
                    del o[c]
            continue
        med = sorted(vals)[len(vals)//2]
        for o in options.values():
            o.setdefault(c, med)

    # varmista että jokaisella optionilla on samat kriteerit
    for o in options.values():
        for c in crits:
            if c not in o:
                # jos päädytään tänne, käytä 0.0, mutta lisää diagnostiikka
                o[c] = 0.0
                diag.append(f"Missing value imputed as 0.0 → {c}")

    # 4) Weights
    w = _parse_weights(text, crits) or {}
    if not w:
        # käytä defaultteja tunnetuille; jos uusia kriteerejä, jaa tasan
        base = {c: DEFAULT_WEIGHTS.get(c, 1.0) for c in crits}
        s = sum(base.values()) or 1.0
        w = {c: base[c]/s for c in crits}
        if "No structured options found in text" not in " ".join(diag):
            diag.append("No weights parsed → normalized defaults used.")
    else:
        # normalisoi
        s = sum(max(0.0, float(v)) for v in w.values()) or 1.0
        w = {c: max(0.0, float(w.get(c, 0.0)))/s for c in crits}

    # 5) Normalisoi ja laske hyötyfunktio
    utilities = {name: 0.0 for name in options}
    normalized: Dict[str, Dict[str, float]] = {c: {} for c in crits}

    for c in crits:
        vals = [float(options[o][c]) for o in options]
        lo, hi = min(vals), max(vals)
        reverse = (CRITERIA_KIND.get(c, "benefit").lower() == "cost")
        for o in options:
            s = _minmax(float(options[o][c]), lo, hi, reverse=reverse)
            normalized[c][o] = s
            utilities[o] += w[c] * s

    ranked = sorted(utilities.items(), key=lambda t: t[1], reverse=True)
    best = ranked[0][0]

    # 6) Herkkyysanalyysi: +0.10 yksittäiseen painoon (renormalisointi)
    sens_notes: List[str] = []
    for c in crits:
        tweaked = dict(w)
        tweaked[c] = tweaked.get(c, 0.0) + 0.10
        s2 = sum(tweaked.values()) or 1.0
        tweaked = {k: v/s2 for k, v in tweaked.items()}
        u2 = {o: 0.0 for o in options}
        for cn in crits:
            for o in options:
                u2[o] += tweaked.get(cn,0.0) * normalized[cn][o]
        new_best = max(u2, key=u2.get)
        if new_best != best:
            sens_notes.append(f"If weight({c}) +0.10 → winner flips: {best} → {new_best}.")
    if not sens_notes:
        sens_notes.append("Decision stable for small single-weight increases (+0.10).")

    # 7) Raportointi
    crit_lines = [f"- {c} ({CRITERIA_KIND.get(c,'benefit')})" for c in crits]
    w_lines = [f"- {c}: {w[c]:.3f}" for c in crits]

    # tulosta alkuperäiset (raaka) inputit selkeyden vuoksi
    raw_opt_lines = []
    for o in options:
        vals = ", ".join(f"{c}={options[o][c]}" for c in crits)
        raw_opt_lines.append(f"- {o}: {vals}")

    score_lines = []
    for o, U in ranked:
        parts = [f"{c}:{normalized[c][o]:.3f}" for c in crits]
        score_lines.append(f"- {o}: U={U:.3f}  |  [{', '.join(parts)}]")

    # diagnoosi (valinnainen)
    diag_lines = [f"- {d}" for d in diag] if diag else ["- Parsed successfully from natural language."]

    md = [
        "# StrategyMCDA",
        "**Criteria:**",
        *crit_lines,
        "",
        "**Weights:**",
        *w_lines,
        "",
        "**Options (raw):**",
        *raw_opt_lines,
        "",
        "**Scores (normalized min–max):**",
        *score_lines,
        "",
        "**Recommendation:**",
        f"Choose {best} (highest utility U).",
        "",
        "**Uncertainty / Sensitivity:**",
        *sens_notes,
        "",
        "**Diagnostics:**",
        *diag_lines,
    ]

    return {
        "markdown": "\n".join(md),
        "sections_present": ["Criteria","Weights","Options (raw)","Scores (normalized min–max)","Recommendation","Uncertainty / Sensitivity","Diagnostics"],
        "sections_missing": [],
    }
