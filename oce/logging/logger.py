from datetime import datetime
from typing import Any

def log(event: str, **kwargs: Any) -> None:
    ts = datetime.utcnow().isoformat()
    kv = " ".join(f"{k}={v!r}" for k,v in kwargs.items())
    print(f"[{ts}] {event} {kv}")
