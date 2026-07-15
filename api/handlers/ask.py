"""POST /ask  { "question": "..." }

Lambda-shaped handler (event/context) so this ports to API Gateway + Lambda
with no logic change. Passes the full precomputed dataset to Claude on every
call (see bedrock/client.py) rather than maintaining conversation state.
"""
from __future__ import annotations

import json

from bedrock.client import answer_question
from ._data import load_mined_data


def handler(event: dict, context=None) -> dict:
    body = json.loads(event.get("body") or "{}") if isinstance(event.get("body"), str) else (event.get("body") or {})
    question = body.get("question", "").strip()
    if not question:
        return {"statusCode": 400, "body": json.dumps({"error": "Missing 'question'"})}

    data = load_mined_data()
    try:
        answer = answer_question(question, data)
    except RuntimeError as e:
        return {"statusCode": 503, "body": json.dumps({"error": str(e)})}

    return {"statusCode": 200, "body": json.dumps({"question": question, "answer": answer})}
