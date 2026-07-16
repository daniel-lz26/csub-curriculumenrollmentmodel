# CHANGES — BSBA Freshman Scheduling Tool

**Date:** July 15, 2026
**Trigger:** New file provided — `BSBAcourse_catalog.xlsx` — plus cross-checking it
against the enrollment data already in hand (`Senior_spring_2026.xlsx`,
`E6_Student_Course_Scheduling_Pattern.xlsx`, `AI_Challenge_Data_Request.xlsx`).

## Verdict: yes, doable — with one real gap

The core idea (mine real freshman course-taking patterns, use the roadmap to
validate/label them, generate 14–16 unit blocks) is achievable with the data
on hand. The one piece we don't have yet is section-level meeting day/time,
which exists at CSUB but hasn't been sent to us.

---

## What the new catalog file gives us

`BSBAcourse_catalog.xlsx` has three sheets:

| Sheet | Rows | Contents |
|---|---|---|
| `BA_Courses` | 24 | BA-prefixed course catalog: units, typical offering term, prereqs |
| `GE_Courses` | 68 | Full GE course list by GE area (1A, 1B, 1C, 2, 3A/B, 4, 5A/B/C, 6, AI-History, AI-Government, FYS, JYDR, Capstone) |
| `Program_Roadmaps` | 626 | Term-by-term degree map for **15 majors**, including all 10 BSBA concentrations, with `req_type` distinguishing `Major`, `General Education`, and `Major / Gen Ed` (GEM) requirements, plus `is_choice` and `is_ge_placeholder` flags |

**This directly resolves the GEM/unit-math gap** flagged after the second
call — `req_type == "Major / Gen Ed"` is exactly the "GEM" concept Deborah
described (a course that satisfies both major and GE requirements). The
mining layer can now compute correct 14–16 unit totals instead of
double-counting or under-counting GE-satisfying major courses.

**Confirms Deborah's claim that concentration doesn't matter for freshman
year.** I pulled term 1–2 rows for all 10 BSBA concentrations
(Accounting, Economics, Entrepreneurship, Finance, General Business,
Health Care Management, HR Management, Management, Marketing, Supply Chain
Logistics). They're nearly identical: `BA 1000`, `BA 1028`, `MIS 2000`,
`MATH 2200`, `GE 1A`, `GE 1C` in fall; `ACCT 2200`, `BA 2200`/`ECON 2200`
(choice), `ECON 2018`, `GE 1B`, `GE 3A` in spring. Safe to build one
freshman-block model for BSBA as a whole rather than per-concentration.

---

## Cross-check against real enrollment data

`Senior_spring_2026.xlsx` contains 51,307 enrollment rows across 1,106
students and all majors, including 169 students on the Business
Administration concentration path (7,210 rows) — enough to mine real
co-occurrence patterns, not just theoretical ones from the roadmap.

I isolated each student's **first enrolled term** and looked at the most
common courses in that term for the Fall 2022 freshman cohort (47 students):

| Course | Count / 47 |
|---|---|
| CSUB 1029 (FYS) | 43 |
| ENGL 1109 (GE 1A) | 37 |
| COMM 1008 (GE 1C) | 26 |
| BA 1008 | 26 |
| MATH 2200 | 23 |

This matches the roadmap's stated freshman-fall requirements almost
exactly, which means:
- The mining approach is validated — real student behavior tracks the
  official map closely, so co-occurrence mining will produce sensible,
  defensible blocks, not noise.
- We can compute an honest "% of students who actually took this pattern"
  stat for each generated block, which is a real, non-invented number for
  the UI (not just "this matches the roadmap").

---

## Remaining gap: no section-level day/time data yet

`AI_Challenge_Data_Request.xlsx` (the master data inventory) lists a file
we have **not** been given:

> **E3/E4** — `E3E4_Course Offering and Waitlist_daily snapshot for Fall
> 2025 and 2026.csv` — course offering schedule and waitlist data.
> Note in the source doc: *"The meeting time and day was added to the
> snapshot data after census Fall 2025 (precisely 10/20/2025)."*

Without this file, we can sequence and unit-sum a block ("these 5 courses
belong together"), but we cannot assign real days/times to it — which was
the specific thing Deborah asked for on the second call ("build a schedule
that has days and times... four or five of those blocks").

**Action item:** request `E3E4_Course Offering and Waitlist_daily snapshot
for Fall 2025 and 2026.csv` directly — it's already been identified and
described as available (`Data Availability: Y - Simplified dataset`), it
just hasn't been sent yet.

**Fallback if it doesn't arrive in time:** generate blocks at the
course-sequence level only, and have the tool output a plain-language
rationale ("these 5 courses belong together, no known day/time conflicts
checked") — flagged honestly in the assumptions panel rather than inventing
times. This still satisfies Deborah's "tell us what you'd need and what
you assumed" ask from the second call.

---

## Open question: E6 vs Senior_spring_2026

`E6_Student_Course_Scheduling_Pattern.xlsx` (434 students, 11,835 rows) and
`Senior_spring_2026.xlsx` (1,106 students, 51,307 rows) have **zero
overlapping student IDs** and E6 has no `Major` column. Both are described
in the data inventory similarly ("student progression / course-taking
patterns, all seniors Spring 2026"). Given no overlap, these appear to be
two different populations or extracts, and E6 can't be filtered to BSBA
without a major label.

**Action item:** ask Deborah/IRPA what population E6 represents and whether
it can be joined to a major field, or whether `Senior_spring_2026.xlsx`
alone (which is already major-labeled and matches the roadmap) is
sufficient as the primary enrollment source.

---

## Net effect on architecture

No change to the overall S3 → pandas mining → Bedrock/Claude explain →
Streamlit shape from `tech-stack-options.md`. Two concrete updates to the
mining layer:

1. **Unit-summing logic now uses `Program_Roadmaps.req_type`** to correctly
   handle GEMs, instead of guessing from course lists alone.
2. **Section-level day/time is deferred** until E3/E4 arrives — the mining
   layer should be written so day/time is an optional enrichment step, not
   a hard dependency of block generation, so the demo still works if that
   file doesn't come through before Friday.

Everything else in `README.md` (data layer, mining layer, Bedrock reasoning
layer, API layer, Streamlit frontend) stands as designed.

---

**Date:** July 15, 2026
**Trigger:** Preparing the API Gateway + Lambda layer for deployment ahead
of the mining pipeline being wired to a live data source (S3 → mining
Lambda per the README architecture diagram, not built yet) — so the API
layer is ready to point at that pipeline's output once it exists.

## Verdict: infra was not deployable as committed — two real bugs found and fixed

Confirmed AWS access first: the `myisb_IsbUsersPS-668855907013` profile has
`AdministratorAccess` on account 668855907013, and Bedrock's
`anthropic.claude-3-haiku-20240307-v1:0` model is actually invokable in
`us-west-2` (tested directly via `aws bedrock-runtime invoke-model`, got a
real response) — so the Bedrock reasoning layer isn't just theoretical.

### Bug 1 — `infra/template.yaml` had a stale/unused parameter and a missing permission
`AnthropicApiKey` was wired as a required deploy parameter and passed into
the Lambda environment, but `bedrock/client.py` is fully Bedrock/IAM-based
(confirmed: `ANTHROPIC_API_KEY` isn't referenced anywhere in that file) —
the parameter was dead plumbing from an earlier design, likely predating
the Bedrock switch. Replaced it with a `BedrockModelId` parameter (defaults
to the Haiku model, overridable per-stage) and added an inline
`bedrock:InvokeModel` IAM policy to both functions' execution roles, which
was missing entirely — without it, both Lambdas would have failed at
runtime with an access-denied error on their first real Bedrock call.

### Bug 2 — `.samignore` doesn't do anything, and the build was 521MB/function
`CodeUri` is the repo root (so both Lambdas can import the sibling
`mining`/`bedrock` packages unchanged), and `.samignore` was written to
exclude `data/raw/`, test directories, and `frontend/` from the deployment
package. Checked directly against the installed SAM CLI (1.163.0) and
`aws-lambda-builders` (1.65.0) source: neither package contains the string
"samignore" anywhere. It has never been a real exclude mechanism for
`sam build`'s standard Python/pip build — it only ever applied to a legacy
raw-zip `sam package` flow this project doesn't use. Net effect: `sam
build` was silently bundling the full 130MB+ `data/raw/` (including the
133MB E3E4 snapshot CSV) plus `streamlit`'s entire dependency tree
(`pyarrow`, `pydeck`, `pillow`, `altair` — frontend-only, never imported by
`api/`, `bedrock/`, or `mining/`) into **both** Lambda packages, for a total
of 521MB unzipped each — over Lambda's 250MB limit. This would have failed
at `sam deploy` time, not silently.

**Fix:**
- Split `requirements.txt`: moved `streamlit` to a new `frontend/requirements.txt`
  (which extends the root file via `-r ../requirements.txt`), since it's
  only used by `frontend/app.py`.
- Added `infra/deploy.sh` as the one documented deploy entrypoint: runs
  `sam build`, then prunes `data/raw`, `api/tests`, `mining/tests`,
  `frontend/`, and a few dev-only directories from each function's build
  output, then runs `sam deploy`. Final package size: 128MB/function.
- Left `.samignore` in place but rewrote its header comment so it's
  documentation of the actual (lack of) behavior rather than a landmine for
  the next person who assumes it works.
- Added `/infra/.aws-sam/` to `.gitignore` (build output, wasn't being
  ignored before).

**Not yet done:** the actual `sam deploy` — building/pruning is verified
working locally, but running it requires creating real AWS resources
(API Gateway, 2 Lambda functions, IAM roles) under the profile above, which
needs explicit sign-off before running.

## Also added: `frontend/FRONTEND_SPEC.md`

Design/feature notes for the Streamlit UI, written against the actual JSON
schema `mine()` produces rather than generic dashboard advice. Highest-
priority finding: `mine()` computes a top-level `assumptions` block
(methodology caveats for `req_type` and `meeting_patterns`) that
`frontend/app.py` never renders — directly relevant to the README's
"process write-up" deliverable, which asks for the methodology to be
handed off in a form CSUB can reproduce for another major. Also flagged:
uncertainty signals (`units_estimated`, unknown `req_type`, missing
meeting patterns) are inconsistently surfaced today, candidate schedules
other than the top pick are shown as flat text with no course-level detail,
and cohort size/percentage are shown disconnected from each other. Full
detail and priority order in the spec file itself.
