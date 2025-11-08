from __future__ import annotations
from typing import Dict, Any, List, Tuple
import random

class RiskExpectedLoss:
    name = "RiskExpectedLoss"
    required_headings = ["Top Risks","Expected Loss","Mitigation","Uncertainty"]

    def _clamp01(self, x: float) -> float:
        return max(0.0, min(1.0, x))

    def _calc_el(self, p: float, loss: float) -> float:
        return float(p) * float(loss)

    def _mc_sim(self, risks: List[Dict[str, Any]], n: int, use_mitigation: bool) -> Tuple[float, float]:
        losses = []
        for _ in range(n):
            tot = 0.0
            for r in risks:
                p = float(r.get("p", 0.0))
                L = float(r.get("loss", 0.0))
                if use_mitigation and r.get("mitigation"):
                    m = r["mitigation"]
                    p = self._clamp01(p - float(m.get("delta_p", 0.0)))
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

    def run(self, user_text: str, context: Dict[str, Any]) -> Dict[str, str]:
        cfg = context.get("risk", {}) or {}
        risks: List[Dict[str, Any]] = cfg.get("risks") or [
            {"name":"Supply delay","p":0.30,"loss":15000,"mitigation":{"delta_p":0.10,"delta_loss":2000,"cost":1200}},
            {"name":"Key hire quits","p":0.15,"loss":22000,"mitigation":{"delta_p":0.05,"delta_loss":0,"cost":3000}},
            {"name":"Data loss","p":0.05,"loss":80000,"mitigation":{"delta_p":0.02,"delta_loss":20000,"cost":5000}},
        ]
        simulate: bool = bool(cfg.get("simulate", False))
        n_sims: int = int(cfg.get("n_sims", 20000))
        apply_mitigation: bool = bool(cfg.get("apply_mitigation", True))

        rows = []
        el_before = 0.0
        el_after = 0.0
        for r in risks:
            name = r.get("name","risk")
            p = self._clamp01(float(r.get("p",0.0)))
            L = max(0.0, float(r.get("loss",0.0)))
            el_b = self._calc_el(p, L)
            el_before += el_b

            m = r.get("mitigation") or {}
            p2 = self._clamp01(p - float(m.get("delta_p", 0.0)))
            L2 = max(0.0, L - float(m.get("delta_loss", 0.0)))
            el_a = self._calc_el(p2, L2) if apply_mitigation else el_b
            el_after += el_a

            reduction = max(0.0, el_b - el_a)
            cost = float(m.get("cost", 0.0)) if m else 0.0
            roi = (reduction / cost) if cost > 0 else None
            net_gain = reduction - cost

            rows.append({
                "name": name, "p": p, "L": L,
                "p_after": p2, "L_after": L2,
                "EL_before": el_b, "EL_after": el_a,
                "reduction": reduction, "mit_cost": cost,
                "ROI": roi, "net_gain": net_gain
            })

        rows_sorted = sorted(rows, key=lambda x: x["EL_before"], reverse=True)

        var_line = ""
        if simulate:
            var_b, es_b = self._mc_sim(risks, n_sims, use_mitigation=False)
            var_a, es_a = self._mc_sim(risks, n_sims, use_mitigation=apply_mitigation)
            var_line = f"Sim (n={n_sims}): VaR95 before={var_b:,.0f}, after={var_a:,.0f}; ES95 before={es_b:,.0f}, after={es_a:,.0f}."

        top_lines = [f"- {r['name']}: p={r['p']:.2f}, L={r['L']:,.0f}, EL={r['EL_before']:,.0f}" for r in rows_sorted]
        mit_lines = []
        for r in rows_sorted:
            roi_txt = "∞" if (r["ROI"] is not None and r["ROI"] > 1e9) else (f"{r['ROI']:.2f}" if r["ROI"] is not None else "—")
            mit_lines.append(
                f"- {r['name']}: EL_before={r['EL_before']:,.0f} → EL_after={r['EL_after']:,.0f} "
                f"(reduction={r['reduction']:,.0f}); cost={r['mit_cost']:,.0f}; ROI={roi_txt}; net_gain={r['net_gain']:,.0f}"
            )

        unc = [
            "Oletus: riskit riippumattomia (simussa).",
            "Δp/ΔL/Cost-arviot lähteistettävä; arvioi haarukat ±20 %.",
        ]
        if var_line:
            unc.append(var_line)

        expected_lines = [
            f"EL_total_before = {el_before:,.0f}",
            f"EL_total_after  = {el_after:,.0f}",
            f"Risk-reduction  = {max(0.0, el_before - el_after):,.0f}",
        ]

        return {
            "Top Risks": "\n".join(top_lines),
            "Expected Loss": "\n".join(expected_lines),
            "Mitigation": "\n".join(mit_lines),
            "Uncertainty": "\n".join(unc),
        }
