"""POST /advisor  { "question": "...", "major": "...", "course": "..." }

Replaces the old /ask endpoint (pooled mining-stats Q&A over
mining/co_occurrence.py output) with a schedule "what-if" advisor:
advisor/roadmap.py computes the real degree-roadmap/prerequisite facts
deterministically, advisor/llm_bedrock.py only narrates them in plain
language -- same compute-first/LLM-explains split bedrock/client.py used for
the old endpoint (see advisor/roadmap.py's docstring for what this data can
and can't confirm).
"""
from __future__ import annotations

import json
import os
import re

from advisor.llm_bedrock import answer_question
from advisor.roadmap import RoadmapAdvisor
from ._data import load_roadmap_data

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
    "Content-Type": "application/json",
}

MAX_QUESTION_LENGTH = 500
MAX_CONTEXT_FIELD_LENGTH = 100
# Rejected outright before anything reaches the LLM -- not a normal part of a
# scheduling question, and a cheap first layer against malformed/probing
# input. Newline/tab/carriage-return are still allowed for readability.
_DISALLOWED_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

DEFAULT_MODEL = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-haiku-4-5-20251001-v1:0")


def _validate_question(question: str) -> str | None:
    """Returns an error message, or None if the question is OK to process."""
    if not question:
        return "Missing 'question'"
    if len(question) > MAX_QUESTION_LENGTH:
        return f"'question' is too long (max {MAX_QUESTION_LENGTH} characters)"
    if _DISALLOWED_CONTROL_CHARS.search(question):
        return "'question' contains disallowed control characters"
    return None


def _clean_context_field(value) -> str | None:
    """major/course are optional hints from whatever the frontend has
    selected. Never trust them further than a bounded, plain string --
    unknown/oversized/non-string values are dropped rather than erroring,
    since RoadmapAdvisor.compute_impact treats a missing major/course as
    'search everything' anyway."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > MAX_CONTEXT_FIELD_LENGTH:
        return None
    return value


def handler(event: dict, context=None) -> dict:
    body = json.loads(event.get("body") or "{}") if isinstance(event.get("body"), str) else (event.get("body") or {})
    question = str(body.get("question", "")).strip()
    major = _clean_context_field(body.get("major"))
    course = _clean_context_field(body.get("course"))

    error = _validate_question(question)
    if error:
        return {"statusCode": 400, "headers": CORS_HEADERS, "body": json.dumps({"error": error})}

    try:
        roadmap = RoadmapAdvisor(load_roadmap_data())
        computed = roadmap.compute_impact(question, major=major, course=course)
        answer = answer_question(question, computed, DEFAULT_MODEL)
    except RuntimeError as e:
        return {"statusCode": 503, "headers": CORS_HEADERS, "body": json.dumps({"error": str(e)})}

    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps({"question": question, "computed": computed, "answer": answer}),
    }
