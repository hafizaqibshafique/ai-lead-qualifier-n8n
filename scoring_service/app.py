"""
FastAPI wrapper around scorer.py. This is the endpoint n8n's HTTP Request
node calls.
"""
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from scorer import LeadInput, ScoreResult, ScoringError, score_lead

load_dotenv()

app = FastAPI(title="Lead Scoring Service")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/score", response_model=ScoreResult)
def score(lead: LeadInput):
    try:
        return score_lead(lead)
    except ScoringError as exc:
        # 422 tells n8n's error branch to route this to manual review
        # instead of trusting a malformed score.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
