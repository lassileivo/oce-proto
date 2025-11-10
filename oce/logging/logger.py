# oce/logging/logger.py
from __future__ import annotations
from datetime import datetime

def _ts() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")

def _fmt(payload) -> str:
    try:
        import json
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return str(payload)

def log_event(event: str, payload: dict | None = None) -> None:
    p = _fmt(payload or {})
    print(f"[{_ts()}] {event} {p}")

def log_exception(event: str, payload: dict | None = None) -> None:
    p = _fmt(payload or {})
    print(f"[{_ts()}] EXCEPTION {event} {p}")

def log_heuristic(rr) -> None:
    # rr is router.RouteResult
    intent = rr.intent
    conf = rr.confidence
    modules = ",".join(rr.selected_modules) if rr.selected_modules else "-"
    hits = rr.keyword_hits.get(rr.intent, [])
    print(f"[{_ts()}] OCE_ROUTER intent={intent} conf={conf} modules={modules} self={rr.self_check} hits={hits}")
