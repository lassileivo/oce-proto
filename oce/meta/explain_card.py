from __future__ import annotations
from typing import Dict, Any

def build_explain_card(session_ctx: Dict[str, Any]) -> str:
    lines = []
    lines.append("## EXPLAIN (Pro)")
    lines.append("**MCDA**: U(j) = Σ_i w_i · s_ij; min–max-normalisointi; AHP Consistency Ratio < 0.10 suositus.")
    lines.append("**Risk**: EL = Σ p_i · L_i; Lievennys: p_i' = max(0, p_i − Δp_i), L_i' = max(0, L_i − ΔL_i).")
    lines.append("**Mitigation ROI**: ROI = (EL_before − EL_after) / cost; Net hyöty = (EL_before − EL_after − cost).")
    lines.append("**Sim (optio)**: VaR95/ES95 Monte Carlo (riippumattomuusoletus).")
    return "\n".join(lines) + "\n"
