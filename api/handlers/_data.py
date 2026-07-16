"""Shared precomputed-data loader for the API handlers.

Mining is precomputed once (see mining/co_occurrence.py) rather than re-run on
every request, since the dataset is static for the hackathon. In Lambda, the
result is fetched from S3 (DATA_BUCKET env var, see infra/template.yaml) at
call time rather than bundled into the deployment zip -- that keeps a stale
or missing local file from becoming a silent deploy-time dependency, and lets
the cache be refreshed (infra/deploy.sh) without a redeploy of code. Local
dev/tests don't set DATA_BUCKET, so they fall through to the on-disk cache or
compute it in-process.
"""
from __future__ import annotations

import json
import os

from mining.co_occurrence import DATA_OUTPUT, mine

CACHE_PATH = DATA_OUTPUT / "recommendation.json"
S3_KEY = "recommendation.json"


class MinedDataUnavailable(RuntimeError):
    """Raised when no precomputed mining data can be found anywhere."""


def _load_from_s3(bucket: str) -> dict:
    import boto3
    from botocore.exceptions import ClientError

    client = boto3.client("s3")
    try:
        obj = client.get_object(Bucket=bucket, Key=S3_KEY)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("NoSuchKey", "404"):
            raise MinedDataUnavailable(
                f"s3://{bucket}/{S3_KEY} not found -- run infra/deploy.sh (which "
                "uploads the mining cache) or mining/co_occurrence.py then sync "
                "it manually."
            ) from e
        raise MinedDataUnavailable(f"Could not read s3://{bucket}/{S3_KEY}: {e}") from e
    return json.loads(obj["Body"].read())


def load_mined_data() -> dict:
    bucket = os.environ.get("DATA_BUCKET")
    if bucket:
        return _load_from_s3(bucket)
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return mine()
