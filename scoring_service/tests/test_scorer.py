import json

import pytest

from scorer import LeadInput, ScoringError, build_user_prompt, parse_model_response


def test_build_user_prompt_includes_all_provided_fields():
    lead = LeadInput(
        name="Jordan Lee",
        company="Northwind Logistics",
        company_size="50-200",
        message="Need a freight-rate calculator built into our WooCommerce store.",
    )

    prompt = build_user_prompt(lead)

    assert "Jordan Lee" in prompt
    assert "Northwind Logistics" in prompt
    assert "50-200" in prompt
    assert "freight-rate calculator" in prompt


def test_build_user_prompt_omits_optional_fields_when_absent():
    lead = LeadInput(name="Sam", message="Just browsing, no project yet.")

    prompt = build_user_prompt(lead)

    assert "Company:" not in prompt
    assert "Company size:" not in prompt


def test_parse_model_response_accepts_well_formed_json():
    raw = json.dumps({
        "score": 82,
        "tier": "hot",
        "summary": "Clear scope and approved budget.",
        "reasons": ["budget approved", "specific requirement"],
    })

    result = parse_model_response(raw)

    assert result.score == 82
    assert result.tier == "hot"
    assert len(result.reasons) == 2


def test_parse_model_response_rejects_invalid_json():
    with pytest.raises(ScoringError, match="not return valid JSON"):
        parse_model_response("not json at all")


def test_parse_model_response_rejects_out_of_range_score():
    raw = json.dumps({
        "score": 150,  # invalid: must be 0-100
        "tier": "hot",
        "summary": "x",
        "reasons": [],
    })

    with pytest.raises(ScoringError, match="expected schema"):
        parse_model_response(raw)


def test_parse_model_response_rejects_unknown_tier():
    raw = json.dumps({
        "score": 50,
        "tier": "lukewarm",  # not a valid tier
        "summary": "x",
        "reasons": [],
    })

    with pytest.raises(ScoringError, match="expected schema"):
        parse_model_response(raw)


def test_parse_model_response_defaults_missing_reasons_to_empty_list():
    raw = json.dumps({"score": 20, "tier": "cold", "summary": "No clear project."})

    result = parse_model_response(raw)

    assert result.reasons == []
