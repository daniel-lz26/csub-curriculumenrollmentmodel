# CSUB BSBA Freshman Scheduling — Starter Context

## 0. What this document is

The full scoping/decision history for this tool, referenced throughout the
codebase (`README.md`, `bedrock/client.py`, `mining/co_occurrence.py`,
`mining/tests/test_co_occurrence.py`) as `claude-starter-context.md` — but
never actually committed. This is a from-scratch reconstruction, sourced
from `CHANGES.md`, the inline comments/citations already in the code, and
the original challenge brief (`challenge_overview.md`). Where the source
material doesn't say something (e.g. exact call dates, who on the team did
what), this doc says so explicitly rather than inventing it — if you have
that context, add it here rather than trusting this file for it.

`contextv67` in the folder name just marks this as the pass that finally
wrote the file down; there's no `contextv1..66` in this repo.

---

## 1. Why generative AI, not a predictive model

From `challenge_overview.md`: deterministic ML depends on high-quality data
and is hard to complete in a 6-day camp; block-registration and
waitlist-pattern problems are more tractable with a generative approach.
The project pivoted to: given historical class lists and a degree map,
generate optimized freshman block schedules for large majors, starting
with Business Administration.

**Governing principle carried through the whole build:** *compute first,
LLM explains.* Frequency counting, ranking, and unit-sum filtering are
deterministic pandas (`mining/co_occurrence.py`). Claude
(`bedrock/client.py`) is never asked to invent a schedule, rank
combinations, or do arithmetic — it only writes rationale and answers ad
hoc questions grounded in the JSON pandas already produced.

---

## 2. Scope

BS Business Administration, **Freshman class year only**. Not a predictive
model, not student-facing, not scoped beyond this one major/class year for
this pass (extension path: other large majors — Psychology, Biology,
History — reusing the same methodology; see `challenge_overview.md`).

**Unit target note:** the mining layer searches for course combinations
summing to a flat **14–15 units**, applied identically to Fall and Spring
(`UNIT_TARGET_LOW`/`UNIT_TARGET_HIGH` in `mining/co_occurrence.py`). This is
narrower than the roadmap's own per-term totals in
`BSBAcourse_catalog.xlsx` (`Program_Roadmaps.term_total_units`, which run
16–17 units in Fall and 15–16 in Spring across *all* requirement types for
that term). The two numbers aren't reconciled: 14–15 is "the tool's search
target over the most frequently co-occurring courses," not a literal
reproduction of the degree roadmap's term total. Flagged as an open item in
§11 rather than silently treated as consistent.

---

## 3. Data sources

| File | Status | Size | Used by |
|---|---|---|---|
| `Senior_spring_2026.xlsx` | Have | 1,106 students / 51,307 rows (169 students / 7,210 rows on the Business Administration concentration path) | `mining/co_occurrence.py` — primary enrollment source |
| `BSBAcourse_catalog.xlsx` | Have (arrived during the build — see CHANGES.md) | `BA_Courses` (24 rows), `GE_Courses` (68 rows), `Program_Roadmaps` (626 rows / 15 majors incl. all 10 BSBA concentrations) | `mining/co_occurrence.py` — GEM/req_type tagging (§7) |
| `E3E4_Course Offering and Waitlist_daily snapshot...csv` | Have | ~595k rows, snapshots from 2025-03-31 through 2026-07-05 | `mining/co_occurrence.py` — per-section units (all snapshots) + meeting day/time (snapshots on/after 2025-10-20 only, §8) |
| `E6_Student_Course_Scheduling_Pattern.xlsx` | Have, not joined to the main pipeline | 434 students / 11,835 rows | `mining/build_freshman_dataset.py` only — separate track, §9 |

All data is static for the build — no live sync. CSU Bakersfield is a
Hispanic-Serving Institution; all student IDs are randomly assigned and
non-reversible. Do not attempt to re-identify students or join against any
external roster.

---

## 4. Term & date conventions

- **CSU-style term code:** `Course Term` values are `YYYY` + a single
  trailing digit — `1`=Winter (rare), `2`=Spring, `3`=Summer, `4`=Fall
  (`TERM_DIGIT_MAP` in `mining/co_occurrence.py`).
- **`Enroll Term` vs `Course Term`:** in `Senior_spring_2026.xlsx`,
  `Enroll Term` is the student's most recent term overall — it is *not*
  the term a given course row was taken in. `Course Term` is the per-row
  term and is what must be used to isolate freshman-year courses.
  Freshman year = each student's earliest `Course Term` value
  (`load_ba_freshman_rows` in `mining/co_occurrence.py`).

---

## 5. Course-frequency counting methodology

- Courses are counted **per row** within freshman-year rows — not
  deduplicated per student.
- Some courses appear twice per student in the same term under one catalog
  number. This is not a data error: it's a paired lecture + co-requisite
  support section under a single course number (confirmed for MATH 1010,
  MATH 1050, GEOL 2010). See `units_for`'s `ambiguous_units` handling.
- The cohort-size denominator behind `pct_of_cohort` is still unique
  students, so `pct` reads as "typical engagement with this course," not a
  literal share of individuals who took it.

---

## 6. Confirmed baseline: freshman-year course frequency (Business Administration, all term types combined)

Among the 156 BA students whose freshman year could be isolated from
`Senior_spring_2026.xlsx` (of 169 total BA students in the file — the
remaining 13 didn't yield an isolable freshman-year row under the
methodology in §4):

| Course | Count / 156 |
|---|---|
| ENGL 1109 | 77 |
| CSUB 1029 | 71 |
| COMM 1008 | 53 |
| MATH 2200 | 41 |
| MATH 1010 | 40 |
| BA 1008 | 35 |
| PHIL 1019 | 27 |
| BA 1000 | 24 |
| MATH 1050 | 22 |
| BA 1028 | 22 |
| ACCT 2200 | 21 |

Locked in as `CONFIRMED_FIRST_TERM_COUNTS` in
`mining/tests/test_co_occurrence.py` so a refactor that silently drifts
from these numbers fails a test instead of shipping unnoticed.

(A related, narrower cut — Fall 2022 first-term cohort only, 47 students —
is documented in `CHANGES.md`'s cross-check against the roadmap; it's a
subset check, not this table.)

---

## 7. GEM / requirement-type handling

- `BSBAcourse_catalog.xlsx` arriving mid-build resolved what "GEM" means
  operationally: `Program_Roadmaps.req_type == "Major / Gen Ed"` is exactly
  the GEM concept (a course that satisfies both a major and a GE
  requirement at once).
- **`req_type` lookup** (`load_requirement_types` in
  `mining/co_occurrence.py`): pools freshman-year (`term_num <= 2`) rows
  across all 10 `BA - *` concentrations in `Program_Roadmaps`, since a
  spot-check confirmed they're near-identical in freshman year (same
  courses, same term placement — see `CHANGES.md`). Pure-GE placeholder
  rows (e.g. "GE 1A: English Composition") don't name a course, so the
  actual GE courses that satisfy them (e.g. ENGL 1109) are tagged
  `"General Education"` from the `GE_Courses` sheet instead.
- **Current implementation status: informational tag only.** `req_type` is
  attached to every course in `course_frequency` and `candidate_schedules`
  so staff and Claude can see "this satisfies both a major and a GE
  requirement" — but it does **not** change the unit-summing arithmetic.
  Candidate schedules are still found by summing each course's raw
  per-section credit units toward the flat 14–15 target (§2). There was
  never a double-counting bug to fix in that arithmetic, because it never
  organized courses into separate major/GE requirement buckets in the
  first place — it just sums real per-course units.
- **Open item, not built:** true requirement-bucket accounting (e.g. "this
  schedule still needs N more Major units and M more GE units, and this
  GEM course covers one of each") would be a real feature addition on top
  of today's flat credit-sum search. See §11.

---

## 8. Section-level day/time (E3/E4)

- Per the source data-request doc (quoted in `CHANGES.md`): *"The meeting
  time and day was added to the snapshot data after census Fall 2025
  (precisely 10/20/2025)."* Snapshots before that date have blank
  `MEETING_DAY`/`MEETING_TIME_START`/`MEETING_TIME_END` columns.
- **Status correction:** `CHANGES.md` (written when `BSBAcourse_catalog.xlsx`
  first arrived) describes E3/E4 as "requested, not yet received." That's
  now stale — the file is present at
  `data/raw/E3E4_Course Offering and Waitlist_daily snapshot for Fall 2025 and 2026.csv`.
  Verified during the 2026-07-15 review pass: snapshots on/after
  2025-10-20 have 100% populated day/time for the Fall 2025 BA freshman
  courses checked.
- **Implemented as an informational enrichment**
  (`load_meeting_patterns` in `mining/co_occurrence.py`): up to 6 most
  common current meeting slots per course (day pattern, start/end time,
  section count using that slot), attached to both `course_frequency` and
  `candidate_schedules`. A few source rows pack a multi-day pattern plus
  facility/date-range text into `MEETING_DAY` with the time columns left
  at `"00:00:00"` (not a real midnight meeting), and `"No Patterns"` means
  an async/online section with no fixed meeting time — both are flagged
  via a `note` field instead of showing a fabricated time.
- **Still open, not built:** this does not resolve which specific section
  a schedule block would use, and does not check for time conflicts
  between courses within the same candidate schedule. If a chair needs an
  actual conflict-free block (Deborah's "build a schedule that has days
  and times" ask), that's the next layer on top of this enrichment, not
  something the current output guarantees.

---

## 9. E6 vs Senior_spring_2026 — the freshman dataset builder is a separate track

- `E6_Student_Course_Scheduling_Pattern.xlsx` (434 students, 11,835 rows)
  has **zero overlapping student IDs** with `Senior_spring_2026.xlsx`
  (1,106 students, 51,307 rows) and no `Major` column, so it can't be
  filtered to BSBA directly. Both files are described similarly in the
  data inventory ("student progression / course-taking patterns, all
  seniors Spring 2026"), so they may be two different extracts of
  overlapping populations, or genuinely different populations — unresolved.
- `mining/build_freshman_dataset.py` uses E6 **independently**: a student
  counts as a "likely freshman start" if ≥50% of their courses in their
  earliest recorded term are 1000-level (excludes transfers and truncated
  histories). 91 of 434 E6 students qualify. Major is inferred (modal
  subject among 2000+ level courses, GE/core subjects excluded) since E6
  has no major label. See `mining/FRESHMAN_DATASET.md`.
- Outputs are gitignored — regenerate with
  `python mining/build_freshman_dataset.py`. Canonical copies:
  `s3://dxhub-camp-2026-csub-freshman-blocks/freshman_dataset/`.
- **This roster is not currently joined into `mining/co_occurrence.py`.**
  It's a parallel, unresolved track pending an answer from Deborah/IRPA on
  what population E6 represents and whether it can be tied to a major
  field.

---

## 10. Decision log

- **BSBAcourse_catalog.xlsx arrives** (dated 2026-07-15 in `CHANGES.md`) —
  confirms concentration doesn't matter for freshman year (all 10 BSBA
  concentration term-1/2 roadmaps are nearly identical) and resolves the
  GEM definition (§7).
- **Second call with Deborah** (exact date not recorded in this repo) —
  asked for (a) a schedule with real days/times, several blocks, and (b)
  clarity on how GEM/unit math is handled. As of this pass: (a) is
  addressed as an informational enrichment only (§8) — a true
  multi-block, conflict-free day/time assignment is still open; (b) is
  addressed as an informational tag only (§7) — true requirement-bucket
  unit accounting is still open.
- **2026-07-15 review pass** — wired `req_type` and meeting-time
  enrichment into `mining/co_occurrence.py` (previously described in
  `CHANGES.md`'s "Net effect on architecture" section as a plan, but never
  implemented); corrected the README's claim that E3/E4 hadn't arrived —
  it has, and its post-census snapshots already carry usable day/time
  data. Unit targets were **not** changed to be term-specific and GEM
  tagging was **not** wired into the arithmetic — kept as informational
  only, by explicit choice, to avoid changing tested mining behavior
  without a deliberate follow-up decision (see §11).

---

## 11. Open items / not yet done

- Requirement-bucket-aware unit accounting (real GEM dedup against Major
  vs. GE totals), vs. today's flat per-course credit sum.
- Term-specific unit targets (roadmap totals run 16–17 Fall / 15–16
  Spring) vs. today's flat 14–15 search target used for both terms.
- Conflict-checking across courses in a candidate schedule using E3/E4
  meeting patterns, and resolving a specific section rather than "most
  common current slot."
- E6 population identity / whether it can be joined to a major field —
  action item is to ask Deborah/IRPA directly (§9).
- Day-by-day team task split and scope traps — not recorded anywhere in
  this repo; if that history exists, it lives outside this codebase.

---

## 12. Team

4 backend developers. This repo does not record who worked on what by day
— that history isn't reconstructable from the code or `CHANGES.md`, so
it's intentionally left out rather than invented.
