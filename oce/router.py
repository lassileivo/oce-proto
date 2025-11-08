from __future__ import annotations
from typing import Dict, Any, List
import yaml, os, re

from .modules.structure import Structure
from .modules.strategy_mcda import StrategyMCDA
from .modules.risk_expected_loss import RiskExpectedLoss

MODULES = {
    "Structure": Structure,
    "StrategyMCDA": StrategyMCDA,
    "RiskExpectedLoss": RiskExpectedLoss,
}

def load_rules() -> Dict[str, Any]:
    path = os.path.join(os.path.dirname(__file__), "heuristics.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def evaluate(user_text: str) -> Dict[str, Any]:
    rules = load_rules()
    text = user_text.lower()
    hits = []
    selected: List[str] = []
    for intent, cfg in rules.get("intents", {}).items():
        if any(re.search(r"\b"+re.escape(k)+"\b", text) for k in cfg.get("keywords", [])):
            hits.append(intent)
            for m in cfg.get("modules", []):
                if m not in selected:
                    selected.append(m)
    if not selected:
        selected = rules["policies"]["default_modules"]
    selected = selected[: rules["policies"]["max_modules"]]
    return {"selected_modules": selected, "triggers_hit": hits, "confidence": 0.7 if hits else 0.5}

def instantiate(names: List[str]) -> List[Any]:
    instances = []
    for n in names:
        cls = MODULES.get(n)
        if cls:
            instances.append(cls())
    return instances
