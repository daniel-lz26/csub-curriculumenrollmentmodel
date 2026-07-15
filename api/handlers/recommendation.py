"""GET /recommendation?term=Fall|Spring

Lambda-shaped handler (event/context) so this ports to API Gateway + Lambda
with no logic change — only the deployment wrapper differs. Returns the
top candidate schedule(s) for the requested term plus Kiro's rationale.
"""
from __future__ import annotations

import json

from bedrock.client import generate_recommendation
from ._data import load_mined_data


def handler(event: dict, context=None) -> dict:
    params = (event or {}).get("queryStringParameters") or {}
    term = params.get("term", "Fall")

    data = load_mined_data()
    term_data = data["terms"].get(term)
    if term_data is None:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"No mined data for term '{term}'"}),
        }

    try:
        rationale = generate_recommendation(term, term_data)
    except RuntimeError as e:
        return {"statusCode": 503, "body": json.dumps({"error": str(e)})}

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "major": data["major"],
                "class_year": data["class_year"],
                "term": term,
                "unit_target": data["unit_target"],
                "cohort_size": term_data["cohort_size"],
                "candidate_schedules": term_data["candidate_schedules"],
                "rationale": rationale,
            }
        ),
    }
