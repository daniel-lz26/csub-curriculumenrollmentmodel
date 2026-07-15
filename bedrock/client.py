"""Reasoning layer: Claude explains/ranks the mining layer's precomputed JSON.

Implemented against the Anthropic API directly (not boto3/Bedrock) so it's
runnable and testable without AWS access during the hackathon build. Porting
to Bedrock later is a client-construction change only (swap `anthropic.Anthropic()`
for `anthropic.AnthropicBedrock()`) — the prompts and call sites below are
otherwise unchanged.

Governing principle (see contextv67/claude-starter-context.md): compute first, LLM
explains. Claude is never asked to invent a schedule, rank combinations, or do
arithmetic — pandas already did that in mining/co_occurrence.py. Claude only
writes rationale and answers ad hoc questions grounded in that computed JSON.
"""
from __future__ import annotations

import json
import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-opus-4-8"

GUARDRAIL = (
    "Only use facts present in the JSON provided below. Do not introduce course "
    "names, counts, percentages, or claims that aren't in it. If the question "
    "or requested term can't be answered from this data (e.g. a major outside "
    "scope, or a term with no mined data), say so plainly rather than "
    "extrapolating or guessing."
)


def _client() -> anthropic.Anthropic:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to a .env file or the "
            "environment before calling the LLM layer."
        )
    return anthropic.Anthropic()


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

    client = _client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=system,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Precomputed data for {term_name}:\n"
                    f"{json.dumps(term_data, indent=2)}\n\n"
                    "Write the recommendation rationale."
                ),
            }
        ],
    )
    return next(b.text for b in response.content if b.type == "text")


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
    client = _client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=system,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Precomputed data (all mined terms):\n"
                    f"{json.dumps(mined_data, indent=2)}\n\n"
                    f"Staff question: {question}"
                ),
            }
        ],
    )
    return next(b.text for b in response.content if b.type == "text")
