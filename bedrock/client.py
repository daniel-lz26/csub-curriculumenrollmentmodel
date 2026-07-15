"""Reasoning layer: Kiro explains/ranks the mining layer's precomputed JSON.

Implemented against AWS Bedrock (boto3 bedrock-runtime) so it runs natively
in Lambda with IAM-based auth — no API keys needed in production. For local
development, ensure `aws configure` has valid credentials with
bedrock:InvokeModel permission.

Governing principle (see kiro-starter-context.md): compute first, LLM
explains. Kiro is never asked to invent a schedule, rank combinations, or do
arithmetic — pandas already did that in mining/co_occurrence.py. Kiro only
writes rationale and answers ad hoc questions grounded in that computed JSON.
"""
from __future__ import annotations

import json
import os

import boto3
from dotenv import load_dotenv

load_dotenv()

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

GUARDRAIL = (
    "Only use facts present in the JSON provided below. Do not introduce course "
    "names, counts, percentages, or claims that aren't in it. If the question "
    "or requested term can't be answered from this data (e.g. a major outside "
    "scope, or a term with no mined data), say so plainly rather than "
    "extrapolating or guessing."
)


def _client():
    """Create a Bedrock Runtime client using environment/IAM credentials."""
    return boto3.client(
        service_name="bedrock-runtime",
        region_name=AWS_REGION,
    )


def _invoke(system: str, user_content: str, max_tokens: int = 512) -> str:
    """Invoke the Kiro model via Bedrock Runtime and return the text response."""
    client = _client()
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "system": system,
        "messages": [
            {
                "role": "user",
                "content": user_content,
            }
        ],
    })

    response = client.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body,
    )

    result = json.loads(response["body"].read())
    return next(b["text"] for b in result["content"] if b["type"] == "text")


def generate_recommendation(term_name: str, term_data: dict) -> str:
    """Turn one term's precomputed mining output into staff-readable rationale.

    `term_data` is `mine()["terms"][term_name]` from mining/co_occurrence.py —
    cohort_size, course_frequency, and candidate_schedules for that term only.
    """
    system = (
        f"You write governance-ready rationale for CSU Bakersfield staff planning "
        f"BS Business Administration freshman course offerings for {term_name}. "
        f"{GUARDRAIL}\n\n"
        "Write 2-4 sentences: recommend the top candidate schedule, cite the "
        "frequency/percentage basis for at least one course in it, and mention "
        "one caveat or a runner-up alternative."
    )
    if not term_data.get("course_frequency"):
        return (
            f"No mined historical data is available for {term_name} for BS "
            "Business Administration freshmen, so no recommendation can be "
            "made for this term."
        )

    user_content = (
        f"Precomputed data for {term_name}:\n"
        f"{json.dumps(term_data, indent=2)}\n\n"
        "Write the recommendation rationale."
    )
    return _invoke(system, user_content)


def answer_question(question: str, mined_data: dict) -> str:
    """Answer a staff ad hoc question over the full mined dataset.

    `mined_data` is the full `mine()` output (all terms) — passed whole on
    every call rather than maintained as stateful conversation, since the
    computed dataset is small enough to pass in full each time.
    """
    system = (
        "You answer CSU Bakersfield staff questions about course scheduling "
        "for BS Business Administration freshmen (14-15 unit target per term), "
        f"using only the precomputed JSON provided below. {GUARDRAIL} Keep "
        "answers concise and staff-appropriate."
    )
    user_content = (
        f"Precomputed data (all mined terms):\n"
        f"{json.dumps(mined_data, indent=2)}\n\n"
        f"Staff question: {question}"
    )
    return _invoke(system, user_content)
