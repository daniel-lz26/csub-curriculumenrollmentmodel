# Freshman dataset

Derived dataset of **likely first-time freshmen** mined from E6 (Student Course
Scheduling Pattern), used as the base for per-major freshman block registration.

## How it's built

`mining/build_freshman_dataset.py` filters E6 to likely freshmen and writes three
CSVs to `data/output/`. A student counts as a **likely freshman start** if, in
their earliest recorded term, at least 50% of their courses are 1000-level. This
excludes transfers and truncated histories (which show upper-division courses in
their first recorded term). Of 434 students in E6, **91 qualify**.

```bash
pip install -r requirements.txt
# place E6 at: data/raw/E6_Student Course Scheduling Pattern.xlsx
python mining/build_freshman_dataset.py
```

## Outputs (gitignored — regenerate locally)

| File (`data/output/`) | Rows | Contents |
|---|---|---|
| `likely_freshmen_roster.csv` | 91 | one row per freshman: first term, %-1000-level, inferred major, terms/courses on record |
| `freshman_first_term_courses.csv` | 555 | each freshman's first-term course records (block-building input) |
| `freshman_all_courses.csv` | 4,193 | full histories of those 91 students (prereq-path tracing) |

Student data is intentionally kept out of git (see `.gitignore`). Canonical copies
of these outputs live in S3:

```
s3://dxhub-camp-2026-csub-freshman-blocks/freshman_dataset/
```

## Notes

- **`inferred_major`** = modal subject among a student's 2000+ level courses
  (GE/core subjects excluded), fallback to modal subject. Largest cohorts: PSYC
  (17), KINE (11), BIOL (9), CMPS (9), BA (7), CRJU (7).
- Sub-1000 developmental math (e.g. `MATH 930`) floors to `level = 0` — real
  signal for the placement-driven math bucket, handle explicitly.
- Small per-major counts are fine for descriptive decision support; not enough
  to train a model.
