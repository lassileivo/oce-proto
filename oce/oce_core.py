from __future__ import annotations
from typing import Dict, Any, List
from . import router
from .validators import check_headings, assemble_markdown
from .logging.logger import log
from .memory import consolidator
from .meta.cfl_ethics import CFLEthics
from .meta.bias_sentinel import BiasSentinel
from .meta.evidence_engine import EvidenceEngine
from .meta.gps_prioritizer import GPSPrioritizer
from .meta.safety_gate import SafetyGate
from .meta.metacog_calib import MetacogCalib
from .meta.myth_guard import MythGuard
from .meta.explain_card import build_explain_card


def run_oce(user_text: str, session_ctx: Dict[str, Any]) -> Dict[str, Any]:
    log("OCE_START", project_id=session_ctx.get("project_id","default"))
    r = router.evaluate(user_text)
    modules = router.instantiate(r["selected_modules"])
    module_results: Dict[str, Dict[str, str]] = {}
    for m in modules:
        res = m.run(user_text, session_ctx)
        module_results[m.__class__.__name__] = res


    # MetaCore
    md = assemble_markdown(module_results)
    cfl = CFLEthics().assess(md, session_ctx)
    bias = BiasSentinel().assess(session_ctx)
    ev = EvidenceEngine().check(session_ctx)
    gps = GPSPrioritizer().score({"cfl": cfl, "evidence": ev})
    policy = SafetyGate().decide(session_ctx)
    metacog = MetacogCalib().assess(session_ctx)
    myth = MythGuard().analyze(md, session_ctx)

    val = check_headings(list(module_results.values()))

    summary = {
    "triggers_hit": r["triggers_hit"],
    "applied_modules": list(module_results.keys()),
    "sections_present": val["sections_present"],
    "missing_sections": val["missing_sections"],
    "confidence": r["confidence"],
    "cfl": cfl,
    "bias": bias,
    "evidence": ev,
    "priority": gps,
    "policy_decision": policy,
    "metacog": metacog,
    "mythguard": myth
    }


    # Memory update (light): topics/decisions/next from module outputs if present
    topics = [t for t in summary["triggers_hit"]]
    decisions = []
    next_steps = []
    for res in module_results.values():
        if "Recommendation" in res:
            decisions.append(res["Recommendation"])
        if "Next Step" in res:
            next_steps.append(res["Next Step"])
    consolidator.update(session_ctx.get("project_id","default"), topics, decisions, next_steps)
    


    text = "# OCE-CORE SUMMARY OUTPUT\n"
    text += f"ACTIVE MODULES: {', '.join(summary['applied_modules'])}\n"
    text += f"CORE TASK: {r['triggers_hit'] or ['general']}\n"
    text += f"HEURISTIC PATH: confidence={r['confidence']}\n\n"
    text += md
    text += "\n\n## META\n"
    text += f"- CFL: {summary['cfl']}\n- Evidence: {summary['evidence']}\n- GPS: {summary['priority']}\n- Policy: {summary['policy_decision']}\n"
    text += f"- Metacog: {summary['metacog']}\n- MythGuard: {summary['mythguard']}\n"
    if session_ctx.get("mode") == "pro":
        text += build_explain_card(session_ctx)
        
    telemetry = {"events": ["start","modules_run","meta","validated","memory_update","done"]}
    log("OCE_END", modules=summary["applied_modules"], policy=policy.get("status"))
    return {"text": text, "json_summary": summary, "telemetry": telemetry}
