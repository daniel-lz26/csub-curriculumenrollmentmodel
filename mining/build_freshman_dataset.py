"""Build a likely-freshman dataset from E6 (Student Course Scheduling Pattern).

Compute-first layer: plain pandas, no LLM calls. Companion to co_occurrence.py.

Freshman rule (validated against the data): a student is a "likely freshman
start" if, in their EARLIEST recorded term, at least 50% of their courses are
1000-level. Transfers and students whose history is truncated in the extract
tend to show upper-division courses in their first recorded term and are
excluded. Of 434 students in E6, 91 qualify.

Reads:   data/raw/E6_Student Course Scheduling Pattern.xlsx
Writes:  data/output/likely_freshmen_roster.csv        (91 freshmen + inferred major)
         data/output/freshman_first_term_courses.csv   (first-term schedules)
         data/output/freshman_all_courses.csv          (full histories, reference)

Outputs are gitignored (student data stays local / in S3); run this to
regenerate them. Canonical copies live in s3://dxhub-camp-2026-csub-freshman-blocks/
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
DATA_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "output"
E6_FILE = DATA_RAW / "E6_Student Course Scheduling Pattern.xlsx"

SEASON_ORDER = {"Winter": 0, "Spring": 1, "Summer": 2, "Fall": 3}
# GE/core subjects we don't treat as a major signal when inferring a major
CORE_SUBJECTS = {"CSUB", "ENGL", "COMM", "MATH", "PHIL", "ART", "HIST",
                 "MUS", "THTR", "SCI", "RS", "PLSI"}


def term_key(term: str) -> int:
    """Sortable integer for a term string like 'Fall 2022' / 'Winter Session 2023'."""
    parts = term.split()
    return int(parts[-1]) * 10 + SEASON_ORDER[parts[0]]


def infer_major(hist: pd.DataFrame) -> str:
    """Modal subject among a student's 2000+ level courses; fallback to modal subject."""
    upper = hist[hist["Course Number"] >= 2000]
    upper = upper[~upper["Course Abbrevation"].isin(CORE_SUBJECTS)]
    if len(upper):
        return upper["Course Abbrevation"].mode().iat[0]
    non_core = hist[~hist["Course Abbrevation"].isin(CORE_SUBJECTS)]
    if len(non_core):
        return non_core["Course Abbrevation"].mode().iat[0]
    return "UNDECLARED"


def main() -> None:
    df = pd.read_excel(E6_FILE)
    df["tk"] = df["Term"].map(term_key)
    df["level"] = (df["Course Number"] // 1000) * 1000
    df["course"] = df["Course Abbrevation"] + " " + df["Course Number"].astype(str)

    df["first_tk"] = df.groupby("Random ID")["tk"].transform("min")
    first_term = df[df["tk"] == df["first_tk"]]

    frac_1000 = first_term.groupby("Random ID")["level"].apply(lambda s: (s == 1000).mean())
    freshman_ids = frac_1000[frac_1000 >= 0.5].index

    fresh_all = df[df["Random ID"].isin(freshman_ids)].copy()
    fresh_first = first_term[first_term["Random ID"].isin(freshman_ids)].copy()

    rows = []
    for sid, hist in fresh_all.groupby("Random ID"):
        ft = hist.loc[hist["tk"] == hist["tk"].min()]
        rows.append({
            "Random ID": sid,
            "first_term": ft["Term"].iat[0],
            "first_term_num_courses": len(ft),
            "first_term_frac_1000lvl": round((ft["level"] == 1000).mean(), 2),
            "inferred_major": infer_major(hist),
            "terms_on_record": hist["Term"].nunique(),
            "total_courses_on_record": len(hist),
        })
    roster = pd.DataFrame(rows).sort_values("inferred_major").reset_index(drop=True)

    out_cols = ["Random ID", "Term", "Course Abbrevation", "Course Number", "course", "level"]
    DATA_OUTPUT.mkdir(parents=True, exist_ok=True)
    roster.to_csv(DATA_OUTPUT / "likely_freshmen_roster.csv", index=False)
    fresh_first[out_cols].to_csv(DATA_OUTPUT / "freshman_first_term_courses.csv", index=False)
    fresh_all[out_cols].to_csv(DATA_OUTPUT / "freshman_all_courses.csv", index=False)

    print(f"Likely freshmen: {len(freshman_ids)} of {df['Random ID'].nunique()} students")
    print(f"First-term course records: {len(fresh_first)}")
    print(f"All course records (freshmen): {len(fresh_all)}")
    print("\nInferred-major distribution:")
    print(roster["inferred_major"].value_counts().to_string())


if __name__ == "__main__":
    main()
