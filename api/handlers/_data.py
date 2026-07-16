"""Shared precomputed-data loaders for the API handlers.

Both the mining cache and the roadmap-advisor cache are precomputed once
(mining/co_occurrence.py, advisor/build_data.py) rather than recomputed per
request. In Lambda, they're fetched from S3 (DATA_BUCKET env var, see
infra/template.yaml) at call time rather than bundled into the deployment zip
-- that keeps a stale or missing local file from becoming a silent
deploy-time dependency, and lets the cache be refreshed (infra/deploy.sh)
without a redeploy of code. Local dev/tests don't set DATA_BUCKET, so they
fall through to the on-disk cache (or, for mining, compute it in-process).
"""
from __future__ import annotations

import json
import os

from advisor.build_data import OUT_PATH as ROADMAP_CACHE_PATH
from mining.co_occurrence import DATA_OUTPUT, mine

MINING_CACHE_PATH = DATA_OUTPUT / "recommendation.json"
MINING_S3_KEY = "recommendation.json"
ROADMAP_S3_KEY = "roadmap_advisor.json"


class DataUnavailable(RuntimeError):
    """Raised when a precomputed dataset can't be found anywhere."""


def _load_from_s3(bucket: str, key: str, refresh_hint: str) -> dict:
    import boto3
    from botocore.exceptions import ClientError

    client = boto3.client("s3")
    try:
        obj = client.get_object(Bucket=bucket, Key=key)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("NoSuchKey", "404"):
            raise DataUnavailable(f"s3://{bucket}/{key} not found -- {refresh_hint}") from e
        raise DataUnavailable(f"Could not read s3://{bucket}/{key}: {e}") from e
    return json.loads(obj["Body"].read())


def load_mined_data() -> dict:
    bucket = os.environ.get("DATA_BUCKET")
    if bucket:
        return _load_from_s3(bucket, MINING_S3_KEY, "run infra/deploy.sh or mining/co_occurrence.py then sync it manually.")
    if MINING_CACHE_PATH.exists():
        return json.loads(MINING_CACHE_PATH.read_text())
    return mine()


def load_roadmap_data() -> dict:
    bucket = os.environ.get("DATA_BUCKET")
    if bucket:
        return _load_from_s3(bucket, ROADMAP_S3_KEY, "run infra/deploy.sh or `python -m advisor.build_data` then sync it manually.")
    if ROADMAP_CACHE_PATH.exists():
        return json.loads(ROADMAP_CACHE_PATH.read_text())
    from advisor.build_data import build
    return build()
