"""Deterministic course co-occurrence mining for BS Business Administration freshmen.

Compute-first layer: everything here is plain pandas arithmetic. No LLM calls
happen in this module. See bedrock/client.py for the explanation layer that
sits on top of this module's JSON output.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

DATA_RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
DATA_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "output"

SENIOR_FILE = DATA_RAW / "Senior spring 2026.xlsx"
OFFERING_FILE = DATA_RAW / "E3E4_Course Offering and Waitlist_daily snapshot for Fall 2025 and 2026.csv"

TARGET_MAJOR = "business administration"
UNIT_TARGET_LOW = 14
UNIT_TARGET_HIGH = 15
DEFAULT_UNITS = 3  # fallback when a course isn't in the offering catalog

# CSU-style term code: YYYY + single digit. Confirmed convention (see
# kiro-starter-context.md): 1=Winter (rare), 2=Spring, 3=Summer, 4=Fall.
TERM_DIGIT_MAP = {"1": "Winter", "2": "Spring", "3": "Summer", "4": "Fall"}


def _course_key(subject: pd.Series, number: pd.Series) -> pd.Series:
    return subject.astype(str).str.strip() + " " + number.astype(str).str.strip()


def load_ba_freshman_rows(path: Path = SENIOR_FILE) -> pd.DataFrame:
    """Load the senior-cohort file and reduce to freshman-year course rows for
    Business Administration students.

    "Freshman year" is defined as each student's earliest Course Term value
    (per kiro-starter-context.md: Enroll Term is the student's most recent
    term, not the term a given course row was taken in — Course Term must be
    used to find freshman-year courses).
    """
    df = pd.read_excel(path)
    df["Major"] = df["Major"].astype(str).str.strip().str.lower()
    ba = df[df["Major"] == TARGET_MAJOR].copy()

    ba["Course Term"] = ba["Course Term"].astype(str).str.strip()
    earliest = ba.groupby("Random ID")["Course Term"].transform("min")
    freshman = ba[ba["Course Term"] == earliest].copy()

    freshman["term_type"] = freshman["Course Term"].str[-1].map(TERM_DIGIT_MAP)
    freshman["course"] = _course_key(freshman["Course Abbreviation"], freshman["Course Number"])
    return freshman


def course_frequency(freshman: pd.DataFrame, term_type: str | None = None) -> pd.DataFrame:
    """Course frequency among freshman-year rows, optionally scoped to one
    term type (Fall/Spring/Summer/Winter).

    Counted per row, matching the methodology behind the confirmed numbers in
    kiro-starter-context.md, not deduplicated per student — some courses
    (e.g. MATH 1010) appear as two rows per student in the same term, a
    paired lecture + co-requisite support section under one catalog number
    (see the bimodal-units handling in load_unit_catalog). Cohort size (the
    pct denominator) is still unique students, so pct reads as "typical
    engagement with this course" rather than a literal share of individuals.
    """
    subset = freshman if term_type is None else freshman[freshman["term_type"] == term_type]
    cohort_size = subset["Random ID"].nunique()
    if cohort_size == 0:
        return pd.DataFrame(columns=["course", "count", "pct"])

    counts = subset["course"].value_counts().rename_axis("course").reset_index(name="count")
    counts["pct"] = counts["count"] / cohort_size
    return counts


def load_unit_catalog(path: Path = OFFERING_FILE) -> dict[str, dict]:
    """Build a course -> {units, offered_fall} catalog from the E3E4
    course-offering snapshot.

    E3E4 only covers Fall 2025/2026 sections, so `offered_fall` is the only
    offering-term signal available from this file; it says nothing about
    Spring offerings (absence here doesn't mean "not offered in Spring").
    Units (CSU_APDB_CMP_UNITS) are real per-section credit values and are not
    term-dependent, so they're trustworthy regardless of term.
    """
    usecols = ["SUBJECT", "CATALOG_NBR", "CSU_APDB_CMP_UNITS"]
    offering = pd.read_csv(path, usecols=usecols, low_memory=False)
    offering["course"] = _course_key(offering["SUBJECT"], offering["CATALOG_NBR"])

    catalog: dict[str, dict] = {}
    for course, group in offering.groupby("course"):
        value_counts = group["CSU_APDB_CMP_UNITS"].value_counts()
        top_share = value_counts.iloc[0] / value_counts.sum()
        if top_share >= 0.9:
            units = int(value_counts.index[0])
            ambiguous = False
        else:
            # Some catalog numbers are a near-even split between two section
            # types under the same number (e.g. a 3-unit lecture paired with
            # a 1-unit co-requisite support section, seen for MATH
            # 1010/1050, GEOL 2010). We can't tell which section a given
            # student row corresponds to, so take the higher value as the
            # canonical credit-bearing offering and flag it rather than
            # silently picking a mode.
            units = int(value_counts.index.max())
            ambiguous = True
        catalog[course] = {"units": units, "offered_fall": True, "ambiguous_units": ambiguous}
    return catalog


def units_for(course: str, catalog: dict[str, dict]) -> tuple[int, bool]:
    """Return (units, is_estimated) for a course, falling back to a default
    when the course isn't present in the offering catalog (e.g. a Spring-only
    course not captured in the Fall-only E3E4 snapshot)."""
    entry = catalog.get(course)
    if entry is None:
        return DEFAULT_UNITS, True
    return entry["units"], entry["ambiguous_units"]


def build_candidate_schedules(
    freq: pd.DataFrame,
    catalog: dict[str, dict],
    top_n_courses: int = 12,
    max_courses: int = 6,
    max_results: int = 5,
) -> list[dict]:
    """Search combinations of the most frequent courses for ones that sum to
    the 14-15 unit target, ranked by mean course frequency (a simple,
    defensible proxy for "how well-supported by real historical patterns is
    this lineup" — not a probability model).
    """
    top = freq.sort_values("count", ascending=False).head(top_n_courses).reset_index(drop=True)
    if top.empty:
        return []

    courses = top["course"].tolist()
    pct_by_course = dict(zip(top["course"], top["pct"]))
    units_by_course = {}
    estimated_by_course = {}
    for c in courses:
        units_by_course[c], estimated_by_course[c] = units_for(c, catalog)

    results = []
    seen = set()
    for size in range(2, max_courses + 1):
        for combo in itertools.combinations(courses, size):
            total_units = sum(units_by_course[c] for c in combo)
            if not (UNIT_TARGET_LOW <= total_units <= UNIT_TARGET_HIGH):
                continue
            key = frozenset(combo)
            if key in seen:
                continue
            seen.add(key)
            score = sum(pct_by_course[c] for c in combo) / len(combo)
            results.append(
                {
                    "courses": [
                        {
                            "course": c,
                            "units": units_by_course[c],
                            "units_estimated": estimated_by_course[c],
                            "pct_of_cohort": round(pct_by_course[c], 4),
                        }
                        for c in combo
                    ],
                    "total_units": total_units,
                    "score": round(score, 4),
                }
            )

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:max_results]


def mine(senior_path: Path = SENIOR_FILE, offering_path: Path = OFFERING_FILE) -> dict:
    freshman = load_ba_freshman_rows(senior_path)
    catalog = load_unit_catalog(offering_path)

    terms_output = {}
    for term_type in ["Fall", "Spring"]:
        freq = course_frequency(freshman, term_type)
        cohort_size = freshman[freshman["term_type"] == term_type]["Random ID"].nunique()
        if freq.empty:
            terms_output[term_type] = {"cohort_size": 0, "course_frequency": [], "candidate_schedules": []}
            continue

        freq_out = []
        for _, row in freq.iterrows():
            units, estimated = units_for(row["course"], catalog)
            freq_out.append(
                {
                    "course": row["course"],
                    "count": int(row["count"]),
                    "pct_of_cohort": round(float(row["pct"]), 4),
                    "units": units,
                    "units_estimated": estimated,
                }
            )

        terms_output[term_type] = {
            "cohort_size": int(cohort_size),
            "course_frequency": freq_out,
            "candidate_schedules": build_candidate_schedules(freq, catalog),
        }

    return {
        "major": "Business Administration",
        "class_year": "Freshman",
        "unit_target": [UNIT_TARGET_LOW, UNIT_TARGET_HIGH],
        "terms": terms_output,
    }


def main() -> None:
    result = mine()
    DATA_OUTPUT.mkdir(parents=True, exist_ok=True)
    out_path = DATA_OUTPUT / "recommendation.json"
    out_path.write_text(json.dumps(result, indent=2))
    print(f"Wrote {out_path}")
    for term_type, payload in result["terms"].items():
        print(f"\n{term_type}: cohort_size={payload['cohort_size']}")
        for c in payload["course_frequency"][:10]:
            print(f"  {c['course']:12s} count={c['count']:3d} pct={c['pct_of_cohort']:.2%} units={c['units']}{'*' if c['units_estimated'] else ''}")
        print(f"  top candidate schedules: {len(payload['candidate_schedules'])}")


if __name__ == "__main__":
    main()
