# oce/oce_core.py
from __future__ import annotations
from typing import Dict, List, Callable, Optional, Tuple
import importlib
import traceback

from . import router
from .logging.logger import log_event, log_heuristic, log_exception


# -------- Module loading helpers --------

def _try_get_runner(modpath: str) -> Optional[Callable]:
    """
    Try to import a module and return a callable runner in the following preference:
    run -> generate -> execute -> main
    The runner must accept (user_text: str, context: dict) and return a dict with at least:
      {
        "markdown": str,             # formatted content for this module
        "sections_present": list,    # optional
        "sections_missing": list,    # optional
      }
    If none is found, return None.
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
        "Structure": "oce.modules.structure",
        "StrategyMCDA": "oce.modules.strategy_mcda",
        "RiskExpectedLoss": "oce.modules.risk_expected_loss",
        # Add more here if you later include them:
        # "CFL": "oce.meta.cfl_ethics",  # example if a module produces markdown
    }

    runner = None
    if modname in mapping:
        runner = _try_get_runner(mapping[modname])

    if runner is None:
        # graceful fallback – never crash the core
        stub_md = f"# {modname}\n_Module runner not found; produced a minimal placeholder._\n"
        return stub_md, [], []

    try:
        out = runner(user_text, context)
        md = out.get("markdown", "").strip()
        sp = out.get("sections_present", [])
        sm = out.get("sections_missing", [])
        if not md:
            md = f"# {modname}\n_(no output)_\n"
        return md, sp, sm
    except Exception as e:
        log_exception("module_run_error", {"module": modname, "error": str(e), "trace": traceback.format_exc()})
        err_md = f"# {modname}\n_Error while running module: {e}_\n"
        return err_md, [], []


# -------- Heuristic path formatting --------

def _format_heuristic_path(rr: router.RouteResult) -> str:
    # Show: intent, confidence, keywords (for the chosen intent), modules, self_check
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
      3) assemble markdown + json_summary
    Returns:
      {
        "text": final_markdown,
        "json_summary": {...},
        "telemetry": {...}
      }
    """
    log_event("OCE_START", {"project_id": session_ctx.get("project_id", "UNKNOWN")})

    # 1) HEURISTICS
    rr = router.evaluate(user_text)
    log_heuristic(rr)

    # keep the selected modules for downstream
    selected = rr.selected_modules[:]

    # 2) RUN MODULES (safe)
    module_blocks: List[str] = []
    sections_present: List[str] = []
    sections_missing: List[str] = []

    module_context = {
        "session_ctx": session_ctx,
        "heuristics": {
            "intent": rr.intent,
            "confidence": rr.confidence,
            "keyword_hits": rr.keyword_hits,
            "policy_max_modules": rr.policy_max_modules,
            "self_check": rr.self_check,
        }
    }

    for m in selected:
        md, sp, sm = _run_module_safely(m, user_text, module_context)
        module_blocks.append(md)
        if sp:
            sections_present.extend(sp)
        if sm:
            sections_missing.extend(sm)

    # 3) ASSEMBLE MARKDOWN
    header_parts = []
    header_parts.append("# OCE-CORE SUMMARY OUTPUT")
    header_parts.append(f"ACTIVE MODULES: {', '.join(selected) if selected else '-'}")
    header_parts.append(f"CORE TASK: ['{rr.intent}']")
    header_parts.append(f"HEURISTIC PATH: {_format_heuristic_path(rr)}\n")

    final_text = "\n".join(header_parts + module_blocks)

    # 4) JSON SUMMARY
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
        # meta blocks can be added here if your modules return them upstream
    }

    telemetry = {"events": ["start", "router", "modules_run", "validated", "done"]}

    log_event("OCE_END", {"modules": selected, "policy": "allow"})
    return {"text": final_text, "json_summary": json_summary, "telemetry": telemetry}
