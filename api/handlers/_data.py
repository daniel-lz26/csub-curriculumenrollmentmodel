"""Shared precomputed-data loader for the API handlers.

Mining is precomputed once and cached to data/output/recommendation.json
(see mining/co_occurrence.py) rather than re-run on every request, since the
dataset is static for the hackathon. Falls back to computing it in-process
if the cache is missing (e.g. a cold Lambda with no prior warm-up run).
"""
from __future__ import annotations

import json
from pathlib import Path

from mining.co_occurrence import DATA_OUTPUT, mine

CACHE_PATH = DATA_OUTPUT / "recommendation.json"


def load_mined_data() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return mine()
