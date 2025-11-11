# PROTO-OCE Privacy Policy

**Version:** 1.0  
**Owner:** Lassi Leivo  
**Scope:** This policy applies to the experimental “PROTO-OCE” GPT and its supporting Render-hosted API.

## 1. What this is
PROTO-OCE is a **prototype** for research and demonstration. It connects a ChatGPT custom GPT to a small API that produces structured strategy/MCDA/risk outputs. It is not a commercial service.

## 2. Data you provide
- **Chat messages and prompts** you type into the GPT.
- **Optional context** (e.g., weights, constraints) the GPT includes when calling the API.

Do **not** share sensitive personal data, confidential business information, or anything you would not publish publicly. By using this prototype, you acknowledge that it is experimental and may process text in third-party systems (OpenAI, Render).

## 3. What gets sent to the API
- The GPT may call the Render endpoint `/run_oce` with a compact JSON payload (e.g., user text, session context such as `project_id` and light preferences).
- The API immediately returns computed text/JSON; no persistent storage is required for normal operation.

## 4. Temporary “memory”
For demonstration, the API can keep **short-lived session notes** (e.g., “budget under 5000”) tied to a `project_id`. This is stored in a small JSONL file on the server and may be **cleared at any time**. It is not designed for personal data, and you should not rely on it for anything important.

## 5. Retention & deletion
- Server logs and the demo memory file may be **ephemeral** and purged during redeploys or maintenance.
- You can request deletion of demo artifacts by contacting the owner; however, due to the prototype nature, deletion may be incomplete if data has already been purged or aggregated.

## 6. Security
- The API is hosted on Render with HTTPS.  
- An **API key** is required for calls from the GPT.  
- This is still a **prototype** with limited hardening; do not treat it as production-grade security.

## 7. Third parties
- **OpenAI** processes your chat content to run the GPT.
- **Render** hosts the API that receives limited text inputs.
Each provider has its own privacy terms.

## 8. Your choices
- Do not use the prototype if you are uncomfortable with the above.
- Keep inputs generic and non-identifying.
- You may stop at any time.

## 9. Contact
Questions or requests: **Lassi Leivo** — lassi.leivo@gmail.com

*This document may change as the research evolves.*
