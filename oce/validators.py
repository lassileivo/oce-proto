from __future__ import annotations
from typing import Dict, Any, List

def check_headings(outputs: List[Dict[str, str]]) -> Dict[str, Any]:
    present = []
    missing = []
    for out in outputs:
        present.extend(list(out.keys()))
    # naive: no strict missing detection in MVP
    return {"sections_present": sorted(set(present)), "missing_sections": []}

def assemble_markdown(module_results: Dict[str, Dict[str,str]]) -> str:
    parts = []
    for name, res in module_results.items():
        parts.append(f"# {name}")
        for k,v in res.items():
            parts.append(f"**{k}:**\n{v}\n")
    return "\n".join(parts)
