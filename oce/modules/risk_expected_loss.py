# oce/modules/risk_expected_loss.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import random

def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

def _mc_sim(risks: List[Dict[str, Any]], n: int, use_mitigation: bool) -> Tuple[float, float]:
    losses = []
    for _ in range(n):
        tot = 0.0
        for r in risks:
            p = float(r.get("p", 0.0))
            L = float(r.get("loss", 0.0))
            if use_mitigation and r.get("mitigation"):
                m = r["mitigation"]
                p = _clamp01(p - float(m.get("delta_p", 0.0)))
                L = max(0.0, L - float(m.get("delta_loss", 0.0)))
            if random.random() < p:
                tot += L
        losses.append(tot)
    losses.sort()
    idx = int(0.95 * (n - 1))
    var95 = losses[idx]
    tail = losses[idx:]
    es95 = sum(tail) / max(1, len(tail))
    return var95, es95

def run(user_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    RiskExpectedLoss v2 — deterministinen EL + (valinnainen) Monte Carlo VaR/ES.
    Hyödyntää context['risk'] jos annettu; muuten käyttää demodataa.
    """
    cfg = context.get("risk", {}) or {}
    risks: List[Dict[str, Any]] = cfg.get("risks") or [
        {"name":"Supply delay","p":0.30,"loss":15000,"mitigation":{"delta_p":0.08,"delta_loss":2000,"cost":1200}},
        {"name":"Data loss","p":0.05,"loss":80000,"mitigation":{"delta_p":0.02,"delta_loss":20000,"cost":5000}},
        {"name":"Key hire quits","p":0.15,"loss":22000,"mitigation":{"delta_p":0.04,"delta_loss":5000,"cost":3000}},
    ]
    simulate: bool = bool(cfg.get("simulate", False))
    n_sims: int = int(cfg.get("n_sims", 20000))
    apply_mitigation: bool = bool(cfg.get("apply_mitigation", True))

    rows = []
    el_before = 0.0
    el_after = 0.0

    for r in risks:
        name = r.get("name","risk")
        p = _clamp01(float(r.get("p",0.0)))
        L = max(0.0, float(r.get("loss",0.0)))
        EL_b = p * L
        el_before += EL_b

        m = r.get("mitigation") or {}
        p2 = _clamp01(p - float(m.get("delta_p", 0.0)))
        L2 = max(0.0, L - float(m.get("delta_loss", 0.0)))
        EL_a = (p2 * L2) if apply_mitigation else EL_b
        el_after += EL_a

        reduction = max(0.0, EL_b - EL_a)
        cost = float(m.get("cost", 0.0)) if m else 0.0
        ROI = (reduction / cost) if cost > 0 else None
        net_gain = reduction - cost

        rows.append({
            "name": name, "p": p, "L": L,
            "p_after": p2, "L_after": L2,
            "EL_before": EL_b, "EL_after": EL_a,
            "reduction": reduction, "mit_cost": cost,
            "ROI": ROI, "net_gain": net_gain
        })

    rows_sorted = sorted(rows, key=lambda x: x["EL_before"], reverse=True)

    var_line = ""
    if simulate:
        var_b, es_b = _mc_sim(risks, n_sims, use_mitigation=False)
        var_a, es_a = _mc_sim(risks, n_sims, use_mitigation=apply_mitigation)
        var_line = f"Sim (n={n_sims}): VaR95 before={var_b:,.0f}, after={var_a:,.0f}; ES95 before={es_b:,.0f}, after={es_a:,.0f}."

    top_lines = [f"- {r['name']}: p={r['p']:.2f}, L={r['L']:,.0f}, EL={r['EL_before']:,.0f}" for r in rows_sorted]

    mit_lines = []
    for r in rows_sorted:
        roi_txt = "∞" if (r["ROI"] is not None and r["ROI"] > 1e9) else (f"{r['ROI']:.2f}" if r["ROI"] is not None else "—")
        mit_lines.append(
            f"- {r['name']}: EL_before={r['EL_before']:,.0f} → EL_after={r['EL_after']:,.0f} "
            f"(reduction={r['reduction']:,.0f}); cost={r['mit_cost']:,.0f}; ROI={roi_txt}; net_gain={r['net_gain']:,.0f}"
        )

    expected_lines = [
        f"EL_total_before = {el_before:,.0f}",
        f"EL_total_after  = {el_after:,.0f}",
        f"Risk-reduction  = {max(0.0, el_before - el_after):,.0f}",
    ]

    unc = [
        "Assume independent risks (in simulation).",
        "Δp/ΔL/Cost estimates must be sourced; use ±20% sensitivity.",
    ]
    if var_line:
        unc.append(var_line)

    md = [
        "# RiskExpectedLoss",
        "**Top Risks:**",
        *top_lines,
        "",
        "**Expected Loss:**",
        *expected_lines,
        "",
        "**Mitigation:**",
        *mit_lines,
        "",
        "**Uncertainty:**",
        *unc,
    ]

    return {
        "markdown": "\n".join(md),
        "sections_present": ["Top Risks","Expected Loss","Mitigation","Uncertainty"],
        "sections_missing": [],
    }
