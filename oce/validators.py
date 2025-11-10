from __future__ import annotations
from typing import Dict, Any, List

# MVP-yhteensopiva validatori: ei ulkoisia kirjastoja

_REQUIRED_KEYS = [
    "triggers_hit",
    "applied_modules",
    "sections_present",
    "missing_sections",
    "confidence",
]

def check_sections(selected_modules: List[str], sections_present: List[str]) -> List[str]:
    """
    Palauta mahdolliset puuttuvat osiot valittujen moduulien minimi-odotusten perusteella.
    MVP: vain kevyt sääntöjoukko, ettei rikota putkea.
    """
    required_by_module = {
        "Structure":        {"Thesis", "Key Points", "Actions", "Next Step"},
        "StrategyMCDA":     {"Criteria", "Weights", "Options", "Scores", "Recommendation"},
        "RiskExpectedLoss": {"Top Risks", "Expected Loss", "Mitigation"},
    }
    missing: List[str] = []
    present = set(sections_present or [])
    for m in selected_modules or []:
        req = required_by_module.get(m, set())
        for sec in req:
            if sec not in present:
                missing.append(sec)
    return sorted(set(missing))

def check_schema(summary: Dict[str, Any]) -> None:
    """
    Kevyt skeemantarkistus, joka vastaa oce_output_schema.json perusvaatimuksia.
    Heittää ValueError jos olennainen puuttuu.
    """
    for k in _REQUIRED_KEYS:
        if k not in summary:
            raise ValueError(f"schema: missing key '{k}'")
    if not isinstance(summary["triggers_hit"], list):
        raise ValueError("schema: 'triggers_hit' must be a list")
    if not isinstance(summary["applied_modules"], list):
        raise ValueError("schema: 'applied_modules' must be a list")
    if not isinstance(summary["sections_present"], list):
        raise ValueError("schema: 'sections_present' must be a list")
    if not isinstance(summary["missing_sections"], list):
        raise ValueError("schema: 'missing_sections' must be a list")
    if not isinstance(summary["confidence"], (int, float)):
        raise ValueError("schema: 'confidence' must be a number")
