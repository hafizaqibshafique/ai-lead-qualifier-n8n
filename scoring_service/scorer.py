"""
Core lead-scoring logic: builds the prompt, calls the LLM, and strictly
validates the response before it's allowed anywhere near a CRM.

Kept separate from app.py (the HTTP layer) so it can be unit tested without
spinning up FastAPI or hitting a live API.
"""
import json
import os
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

VALID_TIERS = ("hot", "warm", "cold")

SYSTEM_PROMPT = """You are a B2B lead qualification assistant for a freelance software \
development consultancy that builds Laravel/PHP, WooCommerce, and AI/automation \
(n8n) projects.

Given a lead's message, score how qualified they are on a 0-100 scale and assign \
a tier:
- hot (70-100): clear scope, budget signal, or firm timeline
- warm (35-69): interested but vague on scope/budget/timeline
- cold (0-34): no real project signal, likely spam or a mismatch for our services

Respond with ONLY a JSON object matching this schema, no prose, no markdown fences:
{"score": <int 0-100>, "tier": "hot"|"warm"|"cold", "summary": "<one sentence>", \
"reasons": ["<short reason>", ...]}
"""


class LeadInput(BaseModel):
    name: str
    company: str | None = None
    message: str = Field(min_length=1)
    company_size: str | None = None


class ScoreResult(BaseModel):
    score: int = Field(ge=0, le=100)
    tier: Literal["hot", "warm", "cold"]
    summary: str
    reasons: list[str] = Field(default_factory=list)


class ScoringError(Exception):
    """Raised when the model's response can't be trusted."""


def build_user_prompt(lead: LeadInput) -> str:
    parts = [f"Name: {lead.name}"]
    if lead.company:
        parts.append(f"Company: {lead.company}")
    if lead.company_size:
        parts.append(f"Company size: {lead.company_size}")
    parts.append(f"Message: {lead.message}")
    return "\n".join(parts)


def parse_model_response(raw: str) -> ScoreResult:
    """
    Turn the model's raw text into a validated ScoreResult, or raise
    ScoringError. This is the function the tests exercise directly, since
    "what happens when the model returns garbage" is the part worth testing —
    the API call itself is just a network hop.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ScoringError(f"Model did not return valid JSON: {exc}") from exc

    try:
        return ScoreResult.model_validate(data)
    except ValidationError as exc:
        raise ScoringError(f"Model JSON didn't match the expected schema: {exc}") from exc


def score_lead(lead: LeadInput, client=None) -> ScoreResult:
    """
    Scores a lead via the configured LLM. `client` is injectable for testing;
    in production it's an `openai.OpenAI()` instance.
    """
    if client is None:
        from openai import OpenAI

        client = OpenAI()

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(lead)},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    raw = response.choices[0].message.content
    return parse_model_response(raw)
