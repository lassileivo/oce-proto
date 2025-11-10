# oce/oce_core.py
from __future__ import annotations
from typing import Dict, List, Callable, Optional, Tuple, Any
import importlib
import traceback
import re

from . import router
from .logging.logger import log_event, log_heuristic, log_exception

# --- Optional validators (graceful fallback) ---
try:
    from .validators import check_sections, check_schema
except Exception:
    check_sections = None
    check_schema = None

# --- Optional memory (graceful fallback) ---
try:
    from .memory.consolidator import load_summary, update as memory_update
except Exception:
    load_summary = None
    memory_update = None

# --- Optional META modules (graceful fallback per module) ---
def _safe_import(path: str, cls_or_fn: str):
    try:
        mod = importlib.import_module(path)
        return getattr(mod, cls_or_fn, None)
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
    try:
        m = importlib.import_module(modpath)
    except Exception:
        return None
    for fn in ("run", "generate", "execute", "main"):
        if hasattr(m, fn) and callable(getattr(m, fn)):
            return getattr(m, fn)
    return None

def _run_module_safely(modname: str, user_text: str, context: dict) -> Tuple[str, List[str], List[str]]:
    mapping = {
        "Structure":        "oce.modules.structure",
        "StrategyMCDA":     "oce.modules.strategy_mcda",
        "RiskExpectedLoss": "oce.modules.risk_expected_loss",
    }
    runner = _try_get_runner(mapping.get(modname, "")) if modname in mapping else None
    if runner is None:
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

# -------- Lightweight extractors for memory --------
_BULLET = re.compile(r"^\s*[-•]\s+(.*)$", re.MULTILINE)
def _extract_actions(md: str) -> List[str]:
    # Hakee kohdan "**Actions:**" tai "**Next Step:**" jälkeiset bulletit
    chunks: List[str] = []
    for header in ("**Actions:**", "**Next Step:**", "**Next Steps:**"):
        if header in md:
            part = md.split(header, 1)[1]
            hits = _BULLET.findall(part)[:6]
            if hits:
                chunks.extend(hits)
    return [c.strip() for c in chunks if c.strip()]

def _extract_topics(md: str) -> List[str]:
    # Poimii **Thesis:**-riviltä pääaiheen 1. lauseen
    if "**Thesis:**" in md:
        th = md.split("**Thesis:**", 1)[1].strip().split("\n", 1)[0]
        return [th.strip()[:120]]
    return []

# -------- Public API --------
def run_oce(user_text: str, session_ctx: dict) -> dict:
    """
    Orchestrates the OCE pipeline:
      1) heuristic routing (+timely hint)
      2) module runs (safe)
      3) validation
      4) META analysis & policy
      5) memory I/O (MVP)
      6) assemble markdown + json_summary
    """
    project_id = session_ctx.get("project_id", "UNKNOWN")
    log_event("OCE_START", {"project_id": project_id})

    # 0) Timely-lippu (auttaa EvidenceEngineä)
    if re.search(r"\b(today|latest|breaking|20(2[4-9]|3[0-9]))\b", user_text.lower()):
        session_ctx["timely"] = True

    # 0b) Lataa lyhyt muistiyhteenveto (MVP)
    short_mem = {"topics": [], "decisions": [], "next_steps": []}
    if load_summary:
        try:
            short_mem = load_summary(project_id) or short_mem
        except Exception:
            pass

    # 1) HEURISTICS
    rr = router.evaluate(user_text)
    log_heuristic(rr)
    selected = rr.selected_modules[:]

    # 2) RUN MODULES
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
        "memory": short_mem,
    }
    for k in ("mcda", "risk"):
        if k in session_ctx:
            module_context[k] = session_ctx[k]

    for m in selected:
        md, sp, sm = _run_module_safely(m, user_text, module_context)
        module_blocks.append(md)
        sections_present.extend(sp or [])
        sections_missing.extend(sm or [])

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

    # 4) META
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

    # 4b) PRO selitekortti
    pro_card_md = ""
    if str(session_ctx.get("mode", "")).lower() in {"pro", "expert"} and ExplainCardRender:
        try:
            pro_card_md = "\n\n" + (ExplainCardRender(meta_summary) or "")
        except Exception:
            pro_card_md = ""

    # 5) MEMORY OUT (poimi teemoja ja seuraavat askeleet)
    did_mem_update = False
    if memory_update:
        try:
            md_all = "\n\n".join(module_blocks)
            topics = _extract_topics(md_all) or [rr.intent]
            next_steps = _extract_actions(md_all)
            decisions: List[str] = []
            if topics or next_steps:
                memory_update(project_id, topics, decisions, next_steps)
                did_mem_update = True
        except Exception:
            pass

    # 6) MARKDOWN + JSON
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
    if did_mem_update:
        meta_lines.append("- Memory: updated")

    final_text = "\n".join(header_parts + module_blocks + [""] + meta_lines) + pro_card_md

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
        # Memory hint
        "memory": {"updated": did_mem_update, "loaded": bool(short_mem.get("topics"))},
    }

    if check_schema:
        try:
            check_schema(json_summary)
        except Exception as e:
            log_exception("schema_check_error", {"error": str(e)})

    telemetry = {"events": ["start", "router", "modules_run", "meta", "validated"] + (["memory_update"] if did_mem_update else []) + ["done"]}
    log_event("OCE_END", {"modules": selected, "policy": meta_summary.get("policy_decision", "allow")})
    return {"text": final_text, "json_summary": json_summary, "telemetry": telemetry}
