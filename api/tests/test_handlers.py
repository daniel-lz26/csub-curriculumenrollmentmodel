"""Contract tests for the API Gateway-shaped Lambda handlers.

Builds the same event shape API Gateway's REST API (v1) Lambda proxy
integration sends (see infra/template.yaml) and asserts on statusCode/body.
generate_recommendation/answer_question are monkeypatched so these run
without network access, an ANTHROPIC_API_KEY, or a precomputed
data/output/recommendation.json on disk.
"""
from __future__ import annotations

import json

import pytest

from api.handlers import ask, recommendation

FAKE_MINED_DATA = {
    "major": "Business Administration",
    "class_year": "Freshman",
    "unit_target": [14, 15],
    "assumptions": {
        "req_type": "GEM classification pools all 10 BSBA concentrations.",
        "meeting_patterns": "Meeting time is informational, not conflict-checked.",
    },
    "terms": {
        "Fall": {
            "cohort_size": 121,
            "course_frequency": [
                {"course": "ENGL 1109", "count": 76, "pct_of_cohort": 0.63, "units": 3, "units_estimated": False}
            ],
            "candidate_schedules": [
                {
                    "courses": [
                        {"course": "ENGL 1109", "units": 3, "units_estimated": False, "pct_of_cohort": 0.63}
                    ],
                    "total_units": 15,
                    "score": 0.63,
                }
            ],
        },
        "Spring": {"cohort_size": 0, "course_frequency": [], "candidate_schedules": []},
    },
}


@pytest.fixture(autouse=True)
def _mock_mined_data(monkeypatch):
    monkeypatch.setattr(recommendation, "load_mined_data", lambda: FAKE_MINED_DATA)
    monkeypatch.setattr(ask, "load_mined_data", lambda: FAKE_MINED_DATA)


class TestRecommendationHandler:
    def test_returns_200_with_rationale_for_known_term(self, monkeypatch):
        monkeypatch.setattr(recommendation, "generate_recommendation", lambda term, data: "Recommend ENGL 1109.")
        resp = recommendation.handler({"queryStringParameters": {"term": "Fall"}})
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["term"] == "Fall"
        assert body["cohort_size"] == 121
        assert body["rationale"] == "Recommend ENGL 1109."
        assert body["rationale_error"] is None
        assert body["assumptions"] == FAKE_MINED_DATA["assumptions"]

    def test_defaults_to_fall_when_no_query_params(self, monkeypatch):
        monkeypatch.setattr(recommendation, "generate_recommendation", lambda term, data: "ok")
        resp = recommendation.handler({})
        assert resp["statusCode"] == 200
        assert json.loads(resp["body"])["term"] == "Fall"

    def test_returns_400_for_unmined_term(self):
        resp = recommendation.handler({"queryStringParameters": {"term": "Winter"}})
        assert resp["statusCode"] == 400
        assert "Winter" in json.loads(resp["body"])["error"]

    def test_returns_200_with_null_rationale_when_llm_unavailable(self, monkeypatch):
        def _raise(term, data):
            raise RuntimeError("ANTHROPIC_API_KEY is not set")

        monkeypatch.setattr(recommendation, "generate_recommendation", _raise)
        resp = recommendation.handler({"queryStringParameters": {"term": "Fall"}})
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["rationale"] is None
        assert body["rationale_error"] == "ANTHROPIC_API_KEY is not set"
        assert body["cohort_size"] == 121
        assert body["candidate_schedules"] == FAKE_MINED_DATA["terms"]["Fall"]["candidate_schedules"]

    def test_skips_llm_call_for_term_with_no_course_frequency(self, monkeypatch):
        called = []
        monkeypatch.setattr(recommendation, "generate_recommendation", lambda term, data: called.append(1))
        resp = recommendation.handler({"queryStringParameters": {"term": "Spring"}})
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["rationale"] is None
        assert not called


class TestAskHandler:
    def test_returns_200_with_answer_for_json_string_body(self, monkeypatch):
        monkeypatch.setattr(ask, "answer_question", lambda q, data: "42 sections.")
        event = {"body": json.dumps({"question": "How many sections?"})}
        resp = ask.handler(event)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["answer"] == "42 sections."

    def test_returns_200_with_already_parsed_dict_body(self, monkeypatch):
        monkeypatch.setattr(ask, "answer_question", lambda q, data: "ok")
        resp = ask.handler({"body": {"question": "What if?"}})
        assert resp["statusCode"] == 200

    def test_returns_400_for_missing_question(self):
        resp = ask.handler({"body": json.dumps({})})
        assert resp["statusCode"] == 400

    def test_returns_400_for_blank_question(self):
        resp = ask.handler({"body": json.dumps({"question": "   "})})
        assert resp["statusCode"] == 400

    def test_returns_503_when_llm_unavailable(self, monkeypatch):
        def _raise(q, data):
            raise RuntimeError("ANTHROPIC_API_KEY is not set")

        monkeypatch.setattr(ask, "answer_question", _raise)
        resp = ask.handler({"body": json.dumps({"question": "Why?"})})
        assert resp["statusCode"] == 503
