from __future__ import annotations
from .oce_core import run_oce

if __name__ == "__main__":
    # Lauseessa "always" → MythGuard liputtaa
    user_text = "I need strategy and risk analysis for project prioritization. This will always work."

    ctx = {
        "project_id": "OCE_DEMO",
        "timely": False,
        "citations": [],   # tyhjä lista ok
        "self_prob": 0.8,  # MetacogCalib-demoon käyttäjän oma arvio
        # "model_prob": 0.65,  # (valinnainen) jos haluat ohittaa oletuksen 0.60
        # "outcome": 1,        # (valinnainen) jos lopputulos tiedossa → Brier-score lasketaan
        "mode": "pro",
        "risk": {
            "simulate": False,
            "apply_mitigation": True,
            "risks": [
                {"name":"Supply delay","p":0.30,"loss":15000,
                 "mitigation":{"delta_p":0.10,"delta_loss":2000,"cost":1200}},
                {"name":"Key hire quits","p":0.15,"loss":22000,
                 "mitigation":{"delta_p":0.05,"delta_loss":0,"cost":3000}},
                {"name":"Data loss","p":0.05,"loss":80000,
                 "mitigation":{"delta_p":0.02,"delta_loss":20000,"cost":5000}}
  ]
}

    }

    out = run_oce(user_text, ctx)
    print(out["text"])

