# AI Lead Qualifier (n8n + LLM scoring service)

A lead-qualification pipeline I'd actually ship for a client: a form/webhook drops a raw lead into n8n, n8n calls a small scoring service that uses an LLM to rate and summarize the lead, then routes it — hot leads to Slack + CRM, cold ones to a nurture list, junk gets dropped.

This is the pattern behind a lot of the automation work I do: n8n handles orchestration and integrations (webhooks, CRM, Slack, email), and a thin Python service handles the part that actually needs a model — because trying to do prompt logic, retries, and JSON-schema validation entirely inside n8n's expression editor gets unmaintainable fast.

## Architecture

```
Webhook (form/CRM)
      │
      ▼
n8n: normalize payload
      │
      ▼
HTTP Request ──────► scoring_service (FastAPI)
      │                    │
      │                    ├─ builds a structured prompt from the lead
      │                    ├─ calls the LLM, forces JSON output
      │                    └─ returns { score, tier, summary, reasons[] }
      ▼
n8n: Switch on `tier`
      │
      ├─ hot   → Slack alert + CRM update (assign to sales)
      ├─ warm  → add to nurture sequence
      └─ cold  → log and drop
```

## What's in this repo

- `workflow/lead-qualifier.json` — the exported n8n workflow (import via n8n's "Import from File"). Webhook trigger → normalize → call scoring service → route on tier → Slack/CRM/log branches.
- `scoring_service/app.py` — FastAPI service exposing `POST /score`.
- `scoring_service/scorer.py` — the actual scoring logic: prompt construction, LLM call, and strict validation of the model's JSON response (a model that returns malformed JSON should fail loudly, not silently corrupt a CRM record).
- `scoring_service/tests/test_scorer.py` — tests the parsing/validation logic against both well-formed and malformed model output, independent of any live API call.

## Why the scoring service is separate from n8n

- **Testable in isolation.** `scorer.py` has unit tests that don't need n8n running or a live API key.
- **Swappable model.** The prompt/parsing logic is in one file — switching providers or models is a one-file change, not a rewrite of the n8n workflow.
- **Fails safe.** If the LLM returns something that doesn't match the expected schema, the service returns a 422 instead of forwarding garbage into the CRM — n8n's error branch catches that and routes it to a "needs manual review" queue instead of silently mis-scoring a lead.

## Running the scoring service

```bash
cd scoring_service
pip install -r requirements.txt
cp .env.example .env   # set OPENAI_API_KEY (or your provider's key)
uvicorn app:app --reload --port 8001
```

```bash
curl -X POST http://localhost:8001/score \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jordan Lee",
    "company": "Northwind Logistics",
    "message": "We need a custom WooCommerce build with a freight-rate calculator, ready in 6 weeks, budget approved.",
    "company_size": "50-200"
  }'
```

Response:

```json
{
  "score": 88,
  "tier": "hot",
  "summary": "Mid-size logistics company with an approved budget and a concrete, scoped project.",
  "reasons": ["explicit budget approval", "specific technical requirement", "firm timeline"]
}
```

## Importing the n8n workflow

1. In n8n: **Workflows → Import from File** → select `workflow/lead-qualifier.json`.
2. Update the "Call Scoring Service" HTTP Request node's URL to point at your deployed `scoring_service`.
3. Add your Slack and CRM credentials to the corresponding nodes.

## Tests

```bash
cd scoring_service
pytest
```

---
Built by [Aqib Shafique](https://aqib.net) — n8n / AI automation, Python.
