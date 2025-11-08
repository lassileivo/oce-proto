from __future__ import annotations
import json, os
from dataclasses import dataclass, asdict
from typing import List, Dict, Any

STORE_PATH = os.path.join(os.path.dirname(__file__), "memory_store.jsonl")

@dataclass
class Summary:
    project_id: str
    topics: List[str]
    decisions: List[str]
    next_steps: List[str]

def _append(line: dict) -> None:
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
    with open(STORE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")

def load_summary(project_id: str) -> Dict[str, Any]:
    if not os.path.exists(STORE_PATH):
        return {"topics": [], "decisions": [], "next_steps": []}
    topics, decisions, next_steps = set(), set(), set()
    with open(STORE_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
                if rec.get("project_id") == project_id:
                    topics.update(rec.get("topics", []))
                    decisions.update(rec.get("decisions", []))
                    next_steps.update(rec.get("next_steps", []))
            except json.JSONDecodeError:
                continue
    return {"topics": sorted(topics), "decisions": sorted(decisions), "next_steps": sorted(next_steps)}

def update(project_id: str, topics: List[str], decisions: List[str], next_steps: List[str]) -> None:
    payload = Summary(project_id=project_id, topics=sorted(set(topics)), decisions=sorted(set(decisions)), next_steps=sorted(set(next_steps)))
    _append(asdict(payload))
