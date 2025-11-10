# oce/modules/risk_expected_loss.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import re
import random
import statistics as stats

"""
RiskExpectedLoss
- Laskee odotetun tappion: EL = Σ p_i * L_i
- Mitigoinnin ROI: ROI = (EL_before - EL_after) / cost; net = (EL_before - EL_after - cost)
- Luonnollisen kielen parseri riskeille (p=, L=) ja mitigoinneille (dp, dL, cost)
- Monte Carlo -simulaatio (deterministinen siemen) kun user_text sisältää 'simulate'
  tai session_ctx["risk"]["simulate"] = True.
- Raportoi VaR95 ja ES95 (Expected Shortfall) tappiojakaumasta.
"""

RISK_PAT = re.compile(
    r"""
    (?P<name>[A-Za-z][\w\s\-]+?)\s*:\s*
    p\s*=\s*(?P<p>\d+(?:\.\d+)?)\s*,\s*
    L\s*=\s*(?P<L>\d+(?:\.\d+)?)
    """, re.VERBOSE | re.IGNORECASE
)

MITI_PAT = re.compile(
    r"""
    (?P<name>[A-Za-z][\w\s\-]+?)\s*:\s*
    (?:dp\s*=\s*(?P<dp>\d+(?:\.\d+)?))?\s*,?\s*
    (?:dL\s*=\s*(?P<dL>\d+(?:\.\d+)?))?\s*,?\s*
    cost\s*=\s*(?P<cost>\d+(?:\.\d+)?)
    """, re.VERBOSE | re.IGNORECASE
)

def _parse_risks(user_text: str) -> List[Dict[str, Any]]:
    risks: List[Dict[str, Any]] = []
    for m in RISK_PAT.finditer(user_text):
        name = m.group("name").strip()
        p = float(m.group("p"))
        L = float(m.group("L"))
        p = max(0.0, min(1.0, p))
        L = max(0.0, L)
        risks.append({"name": name, "p": p, "L": L})
    return risks

def _parse_mitigations(user_text: str) -> Dict[str, Dict[str, float]]:
    outs: Dict[str, Dict[str, float]] = {}
    for m in MITI_PAT.finditer(user_text):
        name = m.group("name").strip()
        dp = m.group("dp")
        dL = m.group("dL")
        cost = m.group("cost")
        outs[name.lower()] = {
            "dp": float(dp) if dp else 0.0,
            "dL": float(dL) if dL else 0.0,
            "cost": float(cost) if cost else 0.0
        }
    return outs

def _default_risks() -> List[Dict[str, Any]]:
    return [
        {"name": "Supply delay", "p": 0.30, "L": 15000.0},
        {"name": "Data loss",    "p": 0.05, "L": 80000.0},
        {"name": "Key hire quits","p":0.15, "L": 22000.0},
    ]

def _default_mitigation() -> Dict[str, Dict[str, float]]:
    return {
        "supply delay": {"dp": 0.08, "dL": 0.02, "cost": 1200.0},
        "data loss":    {"dp": 0.01, "dL": 0.02, "cost": 5000.0},
        "key hire quits":{"dp":0.05, "dL": 0.01, "cost": 3000.0},
    }

def _apply_mitigation(r: Dict[str, Any], miti: Dict[str, float]) -> Tuple[float, float]:
    p = max(0.0, r["p"] - miti.get("dp", 0.0))
    L = max(0.0, r["L"] - r["L"] * miti.get("dL", 0.0))
    return p, L

def _expected_loss(risks: List[Dict[str, Any]]) -> float:
    return sum(r["p"] * r["L"] for r in risks)

def _simulate_losses(risks: List[Dict[str, Any]], trials: int = 20000, seed: int = 42) -> Tuple[float, float]:
    """
    Palauttaa (VaR95, ES95) riippumattomuusoletuksella.
    VaR95 = 95% kvantiili tappioista.
    ES95 = odotusarvo tappioista, jotka ylittävät VaR95:n.
    """
    random.seed(seed)
    losses: List[float] = []
    for _ in range(trials):
        total = 0.0
        for r in risks:
            if random.random() < r["p"]:
                total += r["L"]
        losses.append(total)
    losses.sort()
    idx = int(0.95 * len(losses)) - 1
    idx = max(0, min(idx, len(losses)-1))
    var95 = losses[idx]
    tail = [x for x in losses if x >= var95]
    es95 = sum(tail)/len(tail) if tail else var95
    return var95, es95

def run(user_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
    session_ctx = (context or {}).get("session_ctx") or {}
    user_l = (user_text or "").lower()

    # 1) Hae riskit
    risks = _parse_risks(user_text)
    if not risks:
        ctx_risks = ((context or {}).get("risk") or {}).get("risks") if context else None
        if isinstance(ctx_risks, list) and ctx_risks:
            risks = ctx_risks
        else:
            risks = _default_risks()

    # 2) Hae mitigoinnit
    mitigations = _parse_mitigations(user_text)
    if not mitigations:
        ctx_miti = ((context or {}).get("risk") or {}).get("mitigations") if context else None
        mitigations = ctx_miti if isinstance(ctx_miti, dict) else _default_mitigation()

    # 3) EL ennen
    EL_before = _expected_loss(risks)

    # 4) EL jälkeen (sovella nimien mukaan; case-insensitive)
    after_risks: List[Dict[str, Any]] = []
    details: List[Dict[str, Any]] = []
    for r in risks:
        key = r["name"].lower()
        miti = mitigations.get(key, {"dp": 0.0, "dL": 0.0, "cost": 0.0})
        p2, L2 = _apply_mitigation(r, miti)
        after_risks.append({"name": r["name"], "p": p2, "L": L2})
        EL_b = r["p"] * r["L"]
        EL_a = p2 * L2
        red = EL_b - EL_a
        cost = miti.get("cost", 0.0)
        roi = (red / cost) if cost > 0 else 0.0
        net = (red - cost)
        details.append({
            "name": r["name"], "EL_before": EL_b, "EL_after": EL_a,
            "reduction": red, "cost": cost, "ROI": roi, "net": net
        })

    EL_after = _expected_loss(after_risks)
    reduction = EL_before - EL_after

    # 5) Simulointi (valinnainen)
    do_sim = "simulate" in user_l or (((context or {}).get("risk") or {}).get("simulate") is True)
    seed = int(((context or {}).get("risk") or {}).get("seed", 42))
    var95 = es95 = None
    if do_sim:
        var95, es95 = _simulate_losses(after_risks, trials=20000, seed=seed)

    # Markdown
    md: List[str] = []
    md.append("# RiskExpectedLoss")
    md.append("**Top Risks:**")
    for r in risks:
        md.append(f"- {r['name']}: p={r['p']:.2f}, L={r['L']:,.0f}, EL={r['p']*r['L']:,.0f}")
    md.append("\n**Expected Loss:**")
    md.append(f"EL_total_before = {EL_before:,.0f}")
    md.append(f"EL_total_after  = {EL_after:,.0f}")
    md.append(f"Risk-reduction  = {reduction:,.0f}")

    md.append("\n**Mitigation:**")
    for d in details:
        md.append(
            f"- {d['name']}: EL_before={d['EL_before']:,.0f} → EL_after={d['EL_after']:,.0f} "
            f"(reduction={d['reduction']:,.0f}); cost={d['cost']:,.0f}; "
            f"ROI={d['ROI']:.2f}; net_gain={d['net']:,.0f}"
        )

    if do_sim:
        md.append("\n**Simulation (Monte Carlo, independent risks):**")
        md.append(f"- VaR95 ≈ {var95:,.0f}")
        md.append(f"- ES95  ≈ {es95:,.0f}")
        md.append(f"- Seed  = {seed}")

    md.append("\n**Uncertainty:**")
    md.append("Assume independent risks (in simulation). Δp/ΔL/Cost estimates must be sourced; use ±20% sensitivity.")

    markdown = "\n".join(md)
    sections_present = ["Top Risks", "Expected Loss", "Mitigation", "Uncertainty"]
    if do_sim:
        sections_present.append("Simulation")
    sections_missing: List[str] = []
    return {"markdown": markdown, "sections_present": sections_present, "sections_missing": sections_missing}
