## About

**PROTO-OCE** is a research **proof-of-concept** by **Lassi Leivo** that links a Custom GPT to a small FastAPI service on Render.  
It turns free-form questions into a structured pipeline — **Structure → StrategyMCDA → RiskExpectedLoss** — using a lightweight heuristic router and minimal, short-lived session notes.

- **Goal:** demonstrate an integrated GPT+API workflow for strategy, option scoring (MCDA), and risk (expected loss / Monte Carlo).
- **Status:** prototype; **not production**, no warranties, not professional advice.
- **Security & privacy:** limited hardening; do not submit sensitive data. See [Privacy Policy](<your-privacy-link>) and [Disclaimer](<your-disclaimer-link>).

### Highlights
- FastAPI endpoints: `GET /health`, `POST /run_oce` (JSON in → structured text/JSON out)
- Heuristic intent routing + MCDA (weights, A/B parse) + risk EL/mitigation + optional Monte Carlo
- Minimal demo “memory” keyed by `project_id` (ephemeral JSONL)

### Architecture
Custom GPT ↔ API Action (Bearer key) → **Router** → **Modules** (Structure, StrategyMCDA, RiskExpectedLoss, CFL meta) → Consolidated output (text + JSON summary)

