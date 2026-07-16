# BS Business Administration Freshman Scheduling Tool

A department-chair-facing tool that recommends which courses/sections to
set up each semester for BS Business Administration freshmen at CSU
Bakersfield, using real historical course-taking patterns plus a
generative AI layer for explanation and ad hoc Q&A.

Built for a 4-day hackathon. AWS Bedrock, Kiro, and Claude API tokens
available. See `contextv67/claude-starter-context.md` for the full
scoping/decision history — this file covers the architecture and how the
pieces fit together.

---

## What this is (and isn't)

- **Is:** a decision-support tool for department chairs and schedule
  builders planning course offerings for one major (Business
  Administration), one class year (freshmen), targeting 14–15 unit
  schedules per term. Built for a sophisticated, schedule-literate user,
  not a general staff dashboard.
- **Isn't:** a predictive ML model, a student-facing planner, an advisor
  tool, or scoped to any major/class year beyond the above.

## Deliverables

Three things ship at the end of the hackathon, not just the tool:

1. **The tool** — dataset + working demo (architecture below)
2. **A short user guide** — how a chair actually uses it
3. **A process write-up** — the methodology we used (mining approach, how
   GEM courses — ones that satisfy both a major and GE requirement — are
   identified and tagged, what's assumed vs. real), so CSUB can hand it to
   psychology or another major and reproduce it with their own data.
   Deborah asked for this explicitly — it's not optional polish.

---

## Architecture

```
                 ┌────────────────────┐
                 │   S3 (raw data)    │
                 │  BA freshmen, CSV  │
                 └─────────┬──────────┘
                           │
                           ▼
          ┌───────────────────────────────┐
          │   Lambda — pandas mining      │
          │  course co-occurrence by term, │
          │  candidate 14-15 unit combos,  │
          │  each course tagged Major/GE/  │
          │  GEM from the roadmap (labels  │
          │  only, not the unit math) +    │
          │  informational day/time from   │
          │  E3/E4 post-census snapshots   │
          └─────────────┬─────────────────┘
                         │  (precomputed JSON)
                         ▼
          ┌───────────────────────────────┐
          │   Bedrock — Kiro              │
          │  explains/ranks combos,        │
          │  answers staff "what-if" Q&A   │
          └─────────────┬─────────────────┘
                         │
                         ▼
          ┌───────────────────────────────┐
          │   API Gateway + Lambda         │
          │  serves recommendation + Q&A   │
          │  as JSON                       │
          └─────────────┬─────────────────┘
                         │
                         ▼
          ┌───────────────────────────────┐
          │   Streamlit frontend           │
          │  pick a term → see lineup +    │
          │  rationale → ask follow-ups    │
          └───────────────────────────────┘
```

**Guiding principle:** *compute first, LLM explains.* Frequency counting,
ranking, and unit-sum filtering are deterministic (pandas). Kiro never
invents a schedule or does arithmetic — it explains, writes rationale, and
answers ad hoc questions over data that's already been computed.

---

## Components

### 1. Data layer — S3 / `data/raw`
- `Senior spring 2026.xlsx` — 1,106 students / 51,307 rows across all
  majors; 169 on the Business Administration concentration path (7,210
  rows). Primary enrollment source; freshman-year rows (each student's
  earliest `Course Term`) are isolable for 156 of those 169 students, and
  match the roadmap closely in spot-checks (see `CHANGES.md` and
  `contextv67/claude-starter-context.md`).
- `BSBAcourse_catalog.xlsx` — `Program_Roadmaps` (term-by-term degree map
  for all 10 BSBA concentrations, 626 rows, with `req_type` flagging GEM
  courses), plus `BA_Courses` and `GE_Courses`. Used to tag each freshman
  course as Major / General Education / Major-Gen-Ed (GEM) — an
  informational label attached to the mining output, not currently used to
  change the unit-summing arithmetic (which stays a flat 14–15 target for
  both Fall and Spring; see `contextv67/claude-starter-context.md` §7 for
  why).
- `E3E4_Course Offering and Waitlist_daily snapshot for Fall 2025 and
  2026.csv` — received. Real per-section credit units are used for
  unit-summing (a course missing from this file falls back to a flagged
  estimate). Meeting day/time is only populated in snapshots taken on or
  after 2025-10-20 (the post-Fall-2025-census fix date); where present,
  it's surfaced as an informational enrichment — the most common current
  meeting slot(s) per course — not a conflict-checked schedule assignment.
- `E6_Student_Course_Scheduling_Pattern.xlsx` — used separately by
  `mining/build_freshman_dataset.py` to build a likely-freshman roster (91
  of 434 students, via a "≥50% of first-term courses are 1000-level"
  rule). Not joined into the main co-occurrence pipeline: it shares no
  student IDs with `Senior spring 2026.xlsx` and has no `Major` column.
  Open question with Deborah/IRPA on what population it represents.

Static for the hackathon — no live sync needed.

### 2. Mining layer — Lambda (Python/pandas)
- Groups students by earliest `Course Term` to isolate freshman-year
  courses (not `Enroll Term` — see term conventions in
  `contextv67/claude-starter-context.md`)
- Counts course co-occurrence per row within a term type (Fall/Spring)
- Searches combinations of the most frequent courses for ones summing to
  14–15 units — the same target for both terms
- Tags each course with its `req_type` (Major / General Education /
  Major-Gen-Ed) from the roadmap and its most common current meeting
  slot(s) from E3/E4 — both informational, neither affects ranking or the
  unit-sum search
- Outputs a small structured JSON (course, term, frequency, unit count,
  req_type, meeting patterns) — precomputed once to
  `data/output/recommendation.json` rather than recomputed on every
  request, since the dataset doesn't change during the hackathon

### 3. Reasoning layer — Bedrock (Kiro), local Streamlit tool only
Two jobs, both grounded strictly in the precomputed JSON — never given raw
student-level data: recommendation + rationale, and ad hoc Q&A
("what if we can't offer X?") by re-filtering/re-explaining the same
computed dataset. `bedrock/client.py` backs `frontend/app.py` (Streamlit)
in-process, no Lambda involved. Not part of the deployed API — see below.

### 4. API layer — API Gateway + Lambda + S3
One endpoint: `POST /advisor` — a schedule "what-if" advisor. Takes a
question (plus optional `major`/`course` context from whatever's on screen),
computes real degree-roadmap/prerequisite facts deterministically
(`advisor/roadmap.py`, precomputed from `BSBAcourse_catalog.xlsx` by
`advisor/build_data.py`), and has OpenAI (`advisor/llm_openai.py`) narrate
them — same compute-first/LLM-explains split as the Bedrock/Kiro layer
above, different provider. This replaced an earlier `POST /ask` (pooled
mining-stats Q&A over Bedrock) and `GET /recommendation` — neither was
specific to the major/block on screen, and `/recommendation` had no caller
in the current frontend at all.

Prompt-injection posture (see `advisor/llm_openai.py`'s docstring for
detail): the student's question is spotlighted in delimiters with an
explicit refusal rule for override/reveal-prompt attempts, server-side input
validation rejects oversized/malformed input before any LLM call, the model
is never given tool-use (so a jailbreak can only produce bad text, not take
an action), and both its Secrets Manager and S3 permissions are scoped to
exactly the one secret/bucket it needs.

Two S3 buckets, both created by `infra/template.yaml`:
- **DataBucket** — private. Holds the precomputed roadmap-advisor cache
  (`roadmap_advisor.json`) and, for the local Streamlit tool's benefit, the
  mining cache (`recommendation.json`). `AdvisorFunction` reads the former
  from S3 at call time (see `api/handlers/_data.py`) rather than bundling it
  into the Lambda zip, so a stale/missing local file can't silently break a
  deploy.
- **FrontendBucket** — private. Serves `frontend/web/` (the
  schedule_engine-driven UI — see below) through a CloudFront distribution
  (`FrontendDistribution`) for a clean HTTPS URL; the bucket itself has no
  public access at all, only readable via Origin Access Control from that
  one distribution.

The OpenAI API key lives in Secrets Manager (`OpenAIApiKeySecret`), created
with a placeholder value by `template.yaml` — the real key is never a
CloudFormation parameter (which would persist it in stack history). Run
`infra/set_openai_key.sh` once after the first deploy to store it (prompts
for the key, never echoes it or puts it in shell history).

Deploy with `infra/deploy.sh` (wraps `sam build`/`sam deploy`, then uploads
`roadmap_advisor.json` to DataBucket, syncs `frontend/web/` to
FrontendBucket, and invalidates the CloudFront cache so the sync is visible
immediately) rather than calling `sam`/`aws s3`/`aws cloudfront` directly.
`CodeUri` is the
repo root so the Lambda can import the sibling `advisor`/`mining` packages,
but `sam build`'s Python builder has no path-exclude mechanism —
`.samignore` looks like it should provide one but doesn't (verified against
SAM CLI 1.163.0 / aws-lambda-builders 1.65.0: neither references
"samignore"; it only ever applied to a legacy zip-packaging flow this
project doesn't use). Without pruning, the build pulls in the full
`data/raw/` (130MB+ of source xlsx/csv) and test directories, which alone
pushes the function past Lambda's 250MB unzipped limit — `deploy.sh` strips
those paths from the build output before deploying. The Lambda's execution
role has inline `secretsmanager:GetSecretValue` and DataBucket-read policies
(see `infra/template.yaml`), each scoped to exactly the one resource it needs.

### 5. Frontend
Two frontends exist:
- **`frontend/web/`** (current, deployed to FrontendBucket) — a static
  HTML/JS site driven by `schedule_engine`'s generated per-major schedule
  blocks (see `schedule_engine/README.md` and `frontend/web/README.md`),
  with the `/advisor` what-if box wired to the API above.
- **`frontend/app.py`** (Streamlit, local-only, not deployed) — the original
  chair-facing tool: pick a term, see the recommended lineup and rationale
  up front, with a Q&A box underneath. Calls `bedrock/client.py` and
  `mining/co_occurrence.py` in-process, no API Gateway involved.

---

## Repo structure

```
.
├── README.md
├── CHANGES.md                      # data feasibility findings, open questions
├── contextv67/
│   └── claude-starter-context.md   # full scoping/decision history
├── data/
│   ├── raw/                        # gitignored — source xlsx/csv files
│   └── output/                     # gitignored — precomputed mining JSON + freshman dataset CSVs
├── mining/
│   ├── co_occurrence.py            # pandas mining logic, unit tested against
│   │                                # known first-term numbers (see contextv67)
│   ├── build_freshman_dataset.py   # separate E6-based freshman roster builder
│   ├── FRESHMAN_DATASET.md
│   └── tests/
├── bedrock/
│   ├── prompts/
│   │   ├── recommendation.md
│   │   └── qa.md
│   └── client.py
├── api/
│   ├── handlers/
│   │   ├── recommendation.py
│   │   └── ask.py
│   └── tests/
├── infra/
│   ├── template.yaml                # SAM template (API Gateway + Lambda)
│   └── deploy.sh                    # build + prune + deploy — see note below
└── frontend/
    ├── app.py                       # Streamlit
    ├── requirements.txt             # frontend-only deps (streamlit); not
    │                                 # bundled into the Lambda package
    └── FRONTEND_SPEC.md             # feature/design notes for the UI
```

---

## Data handling

CSU Bakersfield is a Hispanic-Serving Institution. All data in this repo
uses randomly assigned, non-reversible student IDs. Do not attempt to
re-identify students or join against any external roster.

---

## Team

4 backend developers. See `contextv67/claude-starter-context.md` for the
scoping/decision history; day-by-day task assignments aren't tracked in
this repo.
