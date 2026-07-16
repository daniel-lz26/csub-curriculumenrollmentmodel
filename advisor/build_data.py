"""Precompute a compact roadmap/prerequisite lookup from
data/raw/BSBAcourse_catalog.xlsx for the schedule "what-if" advisor
(see advisor/roadmap.py).

Written once, like mining/co_occurrence.py -> data/output/recommendation.json,
because the raw .xlsx is gitignored and pruned from the Lambda bundle (see
infra/deploy.sh) -- advisor.roadmap never reads the xlsx directly, only this
derived JSON (uploaded to DataBucket by infra/deploy.sh).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
CATALOG_XLSX = REPO / "data" / "raw" / "BSBAcourse_catalog.xlsx"
DATA_OUTPUT = REPO / "data" / "output"
OUT_PATH = DATA_OUTPUT / "roadmap_advisor.json"

COURSE_CODE_RE = re.compile(r"\b([A-Z]{2,4})\s?(\d{3,4})\b")
UNIT_THRESHOLD_RE = re.compile(r"[Aa]t least (\d+)\s+units")

# Program_Roadmaps' term-1 rows spell GE slots as "GE 1A: English
# Composition", which schedule_engine/catalog.py's GE_AREA_RE already
# handles -- but that module is only ever called at term_num=1. Later terms
# (which this advisor is the first thing to read) use shorthand labels for
# the same GE areas instead, so those need their own patterns here.
GE_LABEL_PATTERNS = [
    (re.compile(r"^GE\s+([0-9][A-C]?):"), lambda m: m.group(1)),
    (re.compile(r"^AIGV\b"), lambda m: "AI-Government"),
    (re.compile(r"^AIAH\b"), lambda m: "AI-History"),
    (re.compile(r"^FYS\b", re.IGNORECASE), lambda m: "FYS"),
    (re.compile(r"\bJYDR\b"), lambda m: "JYDR"),
    (re.compile(r"[Cc]apstone"), lambda m: "Capstone"),
]


def _course_key(subject, num) -> str:
    return f"{str(subject).strip()} {str(num).strip()}"


def _units(value):
    """Most units are plain numbers; a few catalog rows use a variable range
    like "1-3" (e.g. Individual Study) -- keep those as the original string
    rather than crashing or silently guessing a number."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value).strip()


def _ge_area_of(requirement_text: str, known_areas: set) -> str | None:
    for pattern, extract in GE_LABEL_PATTERNS:
        m = pattern.search(requirement_text)
        if m:
            area = extract(m)
            if area in known_areas:
                return area
    return None


def _parse_prerequisites(raw) -> dict | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    codes = sorted({f"{sub} {num}" for sub, num in COURSE_CODE_RE.findall(raw)})
    m = UNIT_THRESHOLD_RE.search(raw)
    threshold = int(m.group(1)) if m else None
    return {"raw_text": raw.strip(), "course_codes": codes, "unit_threshold": threshold}


def build() -> dict:
    ge = pd.read_excel(CATALOG_XLSX, "GE_Courses")
    ba = pd.read_excel(CATALOG_XLSX, "BA_Courses")
    rm = pd.read_excel(CATALOG_XLSX, "Program_Roadmaps")

    ge_areas: dict[str, list[str]] = {}
    course_to_ge_area: dict[str, str] = {}
    course_titles: dict[str, dict] = {}
    for r in ge.itertuples():
        code = _course_key(r.subject, r.course_num)
        area = str(r.ge_area)
        ge_areas.setdefault(area, []).append(code)
        course_to_ge_area[code] = area
        course_titles[code] = {"title": r.title, "units": _units(r.units)}
    known_areas = set(ge_areas)

    prerequisites: dict[str, dict] = {}
    for r in ba.itertuples():
        code = _course_key(r.subject, r.course_num)
        course_titles[code] = {"title": r.title, "units": _units(r.units)}
        parsed = _parse_prerequisites(r.prerequisites)
        if parsed:
            prerequisites[code] = parsed

    majors: dict[str, list[dict]] = {}
    term_units: dict[str, dict[int, float]] = {}
    for r in rm.to_dict("records"):
        major = str(r["major"]).strip()
        req_text = str(r["requirement"]).strip()
        row = {
            "term_num": int(r["term_num"]),
            "term_season": str(r["term_season"]),
            "requirement": req_text,
            "req_type": str(r["req_type"]),
            "units": _units(r["units"]),
            "is_choice": bool(r["is_choice"]),
            "is_ge_placeholder": bool(r["is_ge_placeholder"]),
        }
        area = _ge_area_of(req_text, known_areas)
        if area:
            row["ge_area"] = area
            row["course_options"] = ge_areas.get(area, [])
        elif " or " in req_text:
            row["course_options"] = [c.strip() for c in req_text.split(" or ")]
        elif COURSE_CODE_RE.fullmatch(req_text):
            row["course_options"] = [req_text]
        else:
            row["course_options"] = []  # open elective / unresolvable label
        majors.setdefault(major, []).append(row)
        term_units.setdefault(major, {})[row["term_num"]] = float(r["term_total_units"])

    cumulative_units: dict[str, dict[str, float]] = {}
    for major, by_term in term_units.items():
        running = 0.0
        cum = {}
        for term_num in sorted(by_term):
            running += by_term[term_num]
            cum[str(term_num)] = running
        cumulative_units[major] = cum

    return {
        "majors": majors,
        "ge_areas": ge_areas,
        "course_to_ge_area": course_to_ge_area,
        "course_titles": course_titles,
        "prerequisites": prerequisites,
        "cumulative_units": cumulative_units,
    }


def main() -> None:
    result = build()
    DATA_OUTPUT.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, indent=2))
    unresolved = sum(
        1 for rows in result["majors"].values() for row in rows if not row["course_options"]
    )
    print(f"Wrote {OUT_PATH}")
    print(f"{len(result['majors'])} majors, {len(result['prerequisites'])} parsed prerequisites, "
          f"{len(result['ge_areas'])} GE areas, {unresolved} roadmap rows with no resolvable course_options")


if __name__ == "__main__":
    main()
