# oce/oce_core.py
from __future__ import annotations
from typing import Dict, List, Callable, Optional, Tuple, Any
import importlib
import traceback

from . import router
from .logging.logger import log_event, log_heuristic, log_exception

# --- Optional validators (graceful fallback) ---
try:
    from .validators import check_sections, check_schema
except Exception:
    check_sections = None
    check_schema = None

# --- Optional META modules (graceful fallback per module) ---
def _safe_import(path: str, cls_or_fn: str) -> Optional[Any]:
    try:
        mod = importlib.import_module(path)
        obj = getattr(mod, cls_or_fn, None)
        return obj
    except Exception:
        return None

CFLEthics      = _safe_import("oce.meta.cfl_ethics", "CFLEthics")
EvidenceEngine = _safe_import("oce.meta.evidence_engine", "EvidenceEngine")
GPSPrioritizer = _safe_import("oce.meta.gps_prioritizer", "GPSPrioritizer")
MetacogCalib   = _safe_import("oce.meta.metacog_calib", "MetacogCalib")
MythGuard      = _safe_import("oce.meta.myth_guard", "MythGuard")
BiasSentinel   = _safe_import("oce.meta.bias_sentinel", "BiasSentinel")
SafetyGate     = _safe_import("oce.meta.safety_gate", "SafetyGate")
# Pro-selitekortti (valinnainen)
ExplainCardRender = None
for cand in ("render_card", "render", "pro_explain"):
    fn = _safe_import("oce.meta.explain_card", cand)
    if callable(fn):
        ExplainCardRender = fn
        break


# -------- Module loading helpers --------

def _try_get_runner(modpath: str) -> Optional[Callable]:
    """
    Try to import a module and return a callable runner in the following preference:
    run -> generate -> execute -> main
    The runner must accept (user_text: str, context: dict) and return a dict with at least:
      {
        "markdown": str,
        "sections_present": list,   # optional
        "sections_missing": list,   # optional
      }
    """
    try:
        m = importlib.import_module(modpath)
    except Exception:
        return None

    for fn in ("run", "generate", "execute", "main"):
        if hasattr(m, fn) and callable(getattr(m, fn)):
            return getattr(m, fn)
    return None


def _run_module_safely(modname: str, user_text: str, context: dict) -> Tuple[str, List[str], List[str]]:
    """
    Execute a module by name (e.g., "Structure", "StrategyMCDA", "RiskExpectedLoss")
    falling back to a minimal stub if the module or runner is missing.
    Returns: (markdown, sections_present, sections_missing)
    """
    mapping = {
        "Structure":        "oce.modules.structure",
        "StrategyMCDA":     "oce.modules.strategy_mcda",
        "RiskExpectedLoss": "oce.modules.risk_expected_loss",
        # Add more here if later included:
        # "Framing": "oce.modules.framing",
    }

    runner = None
    if modname in mapping:
        runner = _try_get_runner(mapping[modname])

    if runner is None:
        # graceful fallback – never crash the core
        stub_md = f"# {modname}\n_Module runner not found; produced a minimal placeholder._\n"
        return stub_md, [], []

    try:
        out = runner(user_text, context) or {}
        md = (out.get("markdown") or "").strip()
        sp = out.get("sections_present", []) or []
        sm = out.get("sections_missing", []) or []
        if not md:
            md = f"# {modname}\n_(no output)_\n"
        return md, sp, sm
    except Exception as e:
        log_exception("module_run_error", {"module": modname, "error": str(e), "trace": traceback.format_exc()})
        err_md = f"# {modname}\n_Error while running module: {e}_\n"
        return err_md, [], []


# -------- Heuristic path formatting --------

def _format_heuristic_path(rr: router.RouteResult) -> str:
    hits = rr.keyword_hits.get(rr.intent, [])
    hits_s = ",".join(hits) if hits else "-"
    mods_s = ", ".join(rr.selected_modules) if rr.selected_modules else "-"
    return f"intent={rr.intent} ({rr.confidence}) | keywords=[{hits_s}] | modules=[{mods_s}] | self_check={rr.self_check}"


# -------- Public API --------

def run_oce(user_text: str, session_ctx: dict) -> dict:
    """
    Orchestrates the OCE pipeline:
      1) heuristic routing
      2) run selected modules (safe)
      3) (optional) validation self-check
      4) META analysis & policy
      5) assemble markdown + json_summary
    Returns:
      {
        "text": final_markdown,
        "json_summary": {...},
        "telemetry": {...}
      }
    """
    project_id = session_ctx.get("project_id", "UNKNOWN")
    log_event("OCE_START", {"project_id": project_id})

    # 1) HEURISTICS
    rr = router.evaluate(user_text)
    log_heuristic(rr)

    selected = rr.selected_modules[:]  # keep for downstream

    # 2) RUN MODULES (safe)
    module_blocks: List[str] = []
    sections_present: List[str] = []
    sections_missing: List[str] = []

    module_context: Dict[str, Any] = {
        "session_ctx": session_ctx,
        "heuristics": {
            "intent": rr.intent,
            "confidence": rr.confidence,
            "keyword_hits": rr.keyword_hits,
            "policy_max_modules": rr.policy_max_modules,
            "self_check": rr.self_check,
        },
    }
    # pass-through user-provided structured data (MCDA/Risk) to modules
    for k in ("mcda", "risk"):
        if k in session_ctx:
            module_context[k] = session_ctx[k]

    for m in selected:
        md, sp, sm = _run_module_safely(m, user_text, module_context)
        module_blocks.append(md)
        if sp:
            sections_present.extend(sp)
        if sm:
            sections_missing.extend(sm)

    # 3) VALIDATION (best-effort)
    validation_notes: List[str] = []
    if check_sections:
        try:
            missing = check_sections(selected, sections_present) or []
            if missing:
                validation_notes.append(f"Auto-check: missing sections: {missing}")
                sections_missing.extend(missing)
        except Exception as e:
            validation_notes.append(f"Section check error: {e}")

    if check_schema:
        try:
            # We'll build summary first and run schema check later; placeholder here
            pass
        except Exception as e:
            validation_notes.append(f"Schema check error: {e}")

    # 4) META ANALYSIS (graceful fallback per module)
    meta_summary: Dict[str, Any] = {}

    try:
        cfl = CFLEthics().assess("\n\n".join(module_blocks), session_ctx) if CFLEthics else {"status":"na"}
    except Exception as e:
        cfl = {"status":"error", "message": str(e)}
    meta_summary["cfl"] = cfl

    try:
        evidence = EvidenceEngine().check(session_ctx) if EvidenceEngine else {"status":"na"}
    except Exception as e:
        evidence = {"status":"error", "message": str(e)}
    meta_summary["evidence"] = evidence

    try:
        gps = GPSPrioritizer().score({"cfl": cfl, "evidence": evidence}) if GPSPrioritizer else {"status":"na"}
    except Exception as e:
        gps = {"status":"error", "message": str(e)}
    meta_summary["priority"] = gps

    try:
        metacog = MetacogCalib().assess(session_ctx) if MetacogCalib else {"status":"na"}
    except Exception as e:
        metacog = {"status":"error", "message": str(e)}
    meta_summary["metacog"] = metacog

    try:
        myth = MythGuard().analyze("\n\n".join(module_blocks), session_ctx) if MythGuard else {"status":"na"}
    except Exception as e:
        myth = {"status":"error", "message": str(e)}
    meta_summary["mythguard"] = myth

    try:
        bias = BiasSentinel().assess({"recursions": session_ctx.get("recursions", 0)}) if BiasSentinel else {"status":"na"}
    except Exception as e:
        bias = {"status":"error", "message": str(e)}
    meta_summary["bias"] = bias

    try:
        policy = SafetyGate().decide(session_ctx) if SafetyGate else {"status":"allow"}
    except Exception as e:
        policy = {"status":"error", "message": str(e)}
    meta_summary["policy_decision"] = policy

    # 4b) PRO mode explain-card (optional)
    pro_card_md = ""
    if str(session_ctx.get("mode", "")).lower() in {"pro", "expert"} and ExplainCardRender:
        try:
            pro_card_md = "\n\n" + (ExplainCardRender(meta_summary) or "")
        except Exception:
            pro_card_md = ""  # ignore errors silently in MVP

    # 5) ASSEMBLE MARKDOWN
    header_parts = [
        "# OCE-CORE SUMMARY OUTPUT",
        f"ACTIVE MODULES: {', '.join(selected) if selected else '-'}",
        f"CORE TASK: ['{rr.intent}']",
        f"HEURISTIC PATH: {_format_heuristic_path(rr)}\n",
    ]

    meta_lines = [
        "## META",
        f"- CFL: {meta_summary.get('cfl')}",
        f"- Evidence: {meta_summary.get('evidence')}",
        f"- GPS: {meta_summary.get('priority')}",
        f"- Policy: {meta_summary.get('policy_decision')}",
        f"- Metacog: {meta_summary.get('metacog')}",
        f"- MythGuard: {meta_summary.get('mythguard')}",
        f"- Bias: {meta_summary.get('bias')}",
    ]
    if validation_notes:
        meta_lines.append(f"- Validation: {validation_notes}")

    final_text = "\n".join(header_parts + module_blocks + [""] + meta_lines) + pro_card_md

    # 6) JSON SUMMARY
    json_summary = {
        "triggers_hit": rr.triggers_hit,
        "applied_modules": selected,
        "sections_present": sections_present,
        "missing_sections": sections_missing,
        "confidence": rr.confidence,
        "intent": rr.intent,
        "intents_ranked": rr.intents_ranked[:5],
        "keyword_hits": rr.keyword_hits,
        "heuristic_self_check": rr.self_check,
        "policy_max_modules": rr.policy_max_modules,
        # META mirrors
        "cfl": meta_summary.get("cfl"),
        "evidence": meta_summary.get("evidence"),
        "priority": meta_summary.get("priority"),
        "metacog": meta_summary.get("metacog"),
        "mythguard": meta_summary.get("mythguard"),
        "bias": meta_summary.get("bias"),
        "policy_decision": meta_summary.get("policy_decision"),
    }

    # Run schema check late, if available
    if check_schema:
        try:
            check_schema(json_summary)
        except Exception as e:
            # only log; do not fail
            log_exception("schema_check_error", {"error": str(e)})

    telemetry = {"events": ["start", "router", "modules_run", "meta", "validated", "done"]}

    log_event("OCE_END", {"modules": selected, "policy": meta_summary.get("policy_decision", "allow")})
    return {"text": final_text, "json_summary": json_summary, "telemetry": telemetry}
