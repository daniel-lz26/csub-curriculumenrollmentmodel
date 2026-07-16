"""
Build a likely-freshman dataset from E6 (Student Course Scheduling Pattern).

Freshman rule (validated against the data):
  A student is a "likely freshman start" if, in their EARLIEST recorded term,
  at least 50% of their courses are 1000-level. Transfers and students whose
  history is truncated in the extract tend to show upper-division courses in
  their first recorded term and are excluded.

Outputs (written next to this script):
  - likely_freshmen_roster.csv         one row per likely freshman
  - freshman_first_term_courses.csv    course records for each freshman's first term
  - freshman_all_courses.csv           freshman-YEAR courses only (first academic year:
                                       the starting Fall + that year's Spring/Summer;
                                       sophomore-year and later terms are excluded)
  - freshman_schedules.csv             wide: one row per freshman, first-semester courses
                                       spread across course_1, course_2, ... columns
"""
import os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "dxhub-camp-2026-csub-curriculum-enrollment-model",
                   "data", "E6_Student Course Scheduling Pattern.xlsx")

SEASON_ORDER = {"Winter": 0, "Spring": 1, "Summer": 2, "Fall": 3}
# GE/core subjects we don't treat as a major signal when inferring a major
CORE_SUBJECTS = {"CSUB", "ENGL", "COMM", "MATH", "PHIL", "ART", "HIST",
                 "MUS", "THTR", "SCI", "RS", "PLSI"}


def term_key(term: str) -> int:
    parts = term.split()
    season, year = parts[0], int(parts[-1])
    return year * 10 + SEASON_ORDER.get(parts[0], 0) if season != "Winter" else year * 10
    # (Winter handled by SEASON_ORDER=0 below; kept explicit for clarity)


def term_key_safe(term: str) -> int:
    parts = term.split()
    season = parts[0]
    year = int(parts[-1])
    return year * 10 + SEASON_ORDER[season]


def acad_year(term: str) -> int:
    """Academic year a term belongs to. Fall Y and its following Spring/Summer/Winter
    (Y+1) all belong to academic year Y. So a Fall 2021 start has freshman year =
    Fall 2021 + Spring 2022 + Summer 2022."""
    parts = term.split()
    season, year = parts[0], int(parts[-1])
    return year if season == "Fall" else year - 1


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


def build_schedules(fresh_first: pd.DataFrame) -> pd.DataFrame:
    """One row per freshman: Random ID, first_term, num_courses, course_1, course_2, ...
    Courses are the first-semester courses, sorted alphabetically for a stable layout."""
    rows = []
    for sid, hist in fresh_first.groupby("Random ID"):
        # distinct courses only (source lists lecture/lab or dup rows for the same course)
        courses = sorted(hist["course"].unique().tolist())
        row = {"Random ID": sid, "first_term": hist["Term"].iat[0], "num_courses": len(courses)}
        for i, c in enumerate(courses, start=1):
            row[f"course_{i}"] = c
        rows.append(row)
    sched = pd.DataFrame(rows)
    max_n = int(sched["num_courses"].max())
    ordered = ["Random ID", "first_term", "num_courses"] + [f"course_{i}" for i in range(1, max_n + 1)]
    return sched.reindex(columns=ordered).sort_values("Random ID").reset_index(drop=True)


def main():
    df = pd.read_excel(SRC)
    df["tk"] = df["Term"].map(term_key_safe)
    df["ay"] = df["Term"].map(acad_year)
    df["level"] = (df["Course Number"] // 1000) * 1000
    df["course"] = df["Course Abbrevation"] + " " + df["Course Number"].astype(str)

    # earliest term per student
    df["first_tk"] = df.groupby("Random ID")["tk"].transform("min")
    first_term = df[df["tk"] == df["first_tk"]]

    frac_1000 = first_term.groupby("Random ID")["level"].apply(lambda s: (s == 1000).mean())
    freshman_ids = frac_1000[frac_1000 >= 0.5].index

    fresh = df[df["Random ID"].isin(freshman_ids)].copy()
    fresh_first = first_term[first_term["Random ID"].isin(freshman_ids)].copy()

    # freshman YEAR = the academic year of each student's first term; later years dropped
    fresh["fresh_ay"] = fresh.groupby("Random ID")["ay"].transform("min")
    fresh_year = fresh[fresh["ay"] == fresh["fresh_ay"]].copy()

    # roster (major inference uses each student's FULL history, since upper-division
    # signal only appears in later years)
    rows = []
    for sid, hist in fresh.groupby("Random ID"):
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
    roster.to_csv(os.path.join(HERE, "likely_freshmen_roster.csv"), index=False)
    fresh_first[out_cols].to_csv(os.path.join(HERE, "freshman_first_term_courses.csv"), index=False)
    fresh_year[out_cols].to_csv(os.path.join(HERE, "freshman_all_courses.csv"), index=False)

    # wide first-semester schedules: one row per freshman, courses across columns
    schedules = build_schedules(fresh_first)
    schedules.to_csv(os.path.join(HERE, "freshman_schedules.csv"), index=False)

    print(f"Likely freshmen: {len(freshman_ids)} of {df['Random ID'].nunique()} students")
    print(f"First-term course records: {len(fresh_first)}")
    print(f"Freshman-year course records: {len(fresh_year)}")
    print(f"Schedules (first semester): {len(schedules)} freshmen, "
          f"{sum(c.startswith('course_') for c in schedules.columns)} course slots")
    print("\nInferred-major distribution:")
    print(roster["inferred_major"].value_counts().to_string())


if __name__ == "__main__":
    main()
