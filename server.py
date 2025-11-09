# server.py
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional
from oce.oce_core import run_oce  # <-- tämä kutsuu sinun olemassa olevaa corea

import os
from datetime import datetime

app = FastAPI(title="OCE API", version="0.3")

API_KEY = os.getenv("API_KEY", "change-me")

class RunRequest(BaseModel):
    user_text: str
    session_ctx: Dict[str, Any] = {}

class RunResponse(BaseModel):
    text: str
    json_summary: Dict[str, Any]
    telemetry: Dict[str, Any]

def check_auth(authorization: Optional[str]):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    if token != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid token")

@app.get("/health")
def health():
    """Simple health check endpoint."""
    return {"status": "ok", "ts": datetime.utcnow().isoformat()}

@app.post("/run_oce", response_model=RunResponse)
def run_oce_endpoint(req: RunRequest, authorization: Optional[str] = Header(None)):
    check_auth(authorization)
    result = run_oce(req.user_text, req.session_ctx)
    return RunResponse(**result)
