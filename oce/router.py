# oce/router.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple
import re
import yaml
from pathlib import Path

_HEUR_PATH = Path(__file__).parent / "heuristics.yaml"

@dataclass
class RouteResult:
    selected_modules: List[str]
    triggers_hit: List[str]
    confidence: float
    intent: str
    intents_ranked: List[Tuple[str, float]]
    keyword_hits: Dict[str, List[str]]
    self_check: str  # "ok" or message
    policy_max_modules: int

def _load_heuristics() -> dict:
    with open(_HEUR_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def _tokenize(text: str) -> List[str]:
    # kevyt tokenisaatio ja pienennys
    return re.findall(r"[a-zA-ZåäöÅÄÖ0-9\-]+", text.lower())

def evaluate(user_text: str) -> RouteResult:
    cfg = _load_heuristics()
    tokens = _tokenize(user_text)

    intents_cfg: Dict[str, dict] = cfg.get("intents", {})
    policies = cfg.get("policies", {})
    max_modules = int(policies.get("max_modules", 3))
    auto_detect = bool(policies.get("auto_detect_intent", True))

    # 1) pisteytä intentit: osumat / avainsanojen määrä
    intent_scores: Dict[str, float] = {}
    keyword_hits: Dict[str, List[str]] = {}
    for intent, spec in intents_cfg.items():
        kws: List[str] = [k.lower() for k in spec.get("keywords", [])]
        hits = [k for k in kws if k in tokens]
        keyword_hits[intent] = hits
        # yksinkertainen pistemalli: osumia + pehmeä bonus pidemmille kyselyille
        score = len(hits) + 0.05 * max(0, len(tokens) - 12)
        intent_scores[intent] = score

    ranked = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)
    top_intent, top_score = (ranked[0] if ranked else ("strategic", 0.0))
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    denom = top_score + second if (top_score + second) > 0 else 1.0
    confidence = round(top_score / denom, 2)

    # 2) valitse moduulit top-intentin mukaan
    if auto_detect and top_intent in intents_cfg:
        modules = intents_cfg[top_intent].get("modules", [])[:max_modules]
    else:
        modules = policies.get("default_modules", ["Structure"])[:max_modules]

    # 3) self-check: jos varmuus heikko, ehdota tarkennusta
    if confidence < 0.55:
        self_check = "low-confidence: ask clarifiers (goal/constraints/timeframe)"
    else:
        self_check = "ok"

    # triggers_hit = kaikki intentit joilla oli vähintään 1 osuma
    triggers = [i for i, hits in keyword_hits.items() if len(hits) > 0]

    return RouteResult(
        selected_modules=modules,
        triggers_hit=triggers,
        confidence=confidence,
        intent=top_intent,
        intents_ranked=ranked,
        keyword_hits=keyword_hits,
        self_check=self_check,
        policy_max_modules=max_modules,
    )
