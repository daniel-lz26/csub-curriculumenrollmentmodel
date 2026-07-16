# BS Business Administration Freshman Scheduling Tool

A department-chair-facing decision-support tool for CSU Bakersfield: it
turns real historical enrollment, degree-roadmap, and section data into
per-major freshman cohort schedule blocks, and answers "what if" questions
about failing or swapping a course — grounded in real degree-roadmap data,
narrated by AWS Bedrock.

**Live tool:** https://d29yf6skp53yw4.cloudfront.net
*(This URL is tied to the current deployment and will change if the stack is
ever recreated under a new name — see [Deploying](#deploying--redeploying)
for how to look up the current one.)*

Not sure where to start reading? See [`PROJECT_MAP.md`](PROJECT_MAP.md) for
a plain-English tour of this repo if you're not a developer, or
[`USER_GUIDE.md`](USER_GUIDE.md) if you just want to know how to use the
tool itself.

---

## What this is (and isn't)

- **Is:** decision support for department chairs and schedule builders
  planning freshman course offerings for BS Business Administration (all 10
  concentrations, pooled — see [`PROCESS_WRITEUP.md`](PROCESS_WRITEUP.md) for
  why) — real, conflict-checked schedule blocks built from actual Fall 2026
  sections, plus a Q&A assistant for "what if" questions grounded in the
  real degree roadmap.
- **Isn't:** a predictive ML model, a student registration system, a
  general-purpose advisor tool, or scoped to any major beyond BSBA. It never
  auto-enrolls anyone and never invents a fact the underlying data doesn't
  support — see [Guiding principle](#guiding-principle-compute-first-llm-explains) below.

## Guiding principle: compute first, LLM explains

Every number a user sees — course frequency, unit totals, fit scores,
degree-roadmap term positions, prerequisite links — is computed
deterministically in Python (pandas / plain dict lookups), never by an LLM.
The LLM's only job anywhere in this system is to *narrate* an already-computed
result in plain language, and to say "not in the data" when asked something
the computed facts don't cover, rather than guess. This shows up in three
independent places in the codebase:

| Layer | Computes | Explains |
|---|---|---|
| `schedule_engine/` | beam-search schedule generation + a deterministic validator that rejects any invalid AI-proposed edit | Claude (via `schedule_engine/llm.py`), only inside the counselor chat loop |
| `advisor/` (deployed) | `advisor/roadmap.py` — real degree-roadmap position, prerequisite links, GE-area equivalence | Bedrock (via `advisor/llm_bedrock.py`) |
| `mining/` (local tool only) | `mining/co_occurrence.py` — course co-occurrence frequency, candidate 14–15 unit combos | Bedrock/Kiro (via `bedrock/client.py`), local Streamlit tool only |

---

## Architecture (as deployed)

```
                                   ┌──────────────────────────┐
                                   │   CloudFront             │
                                   │   (public HTTPS URL)     │
                                   └────────────┬──────────────┘
                                                │  origin (private, OAC-only)
                                                ▼
                        ┌──────────────────────────────────────┐
                        │   S3 — FrontendBucket                 │
                        │   frontend/web/*  (static HTML/JS)    │
                        │   + schedule_engine's per-major        │
                        │     artifacts (data/artifacts/*.json)  │
                        └──────────────────┬─────────────────────┘
                                           │  browser calls POST /advisor
                                           ▼
                        ┌──────────────────────────────────────┐
                        │   API Gateway  →  AdvisorFunction      │
                        │   (Lambda, Python)                     │
                        │   1. advisor/roadmap.py computes real  │
                        │      degree-roadmap/prerequisite facts │
                        │   2. advisor/llm_bedrock.py has         │
                        │      Bedrock narrate them (IAM auth,    │
                        │      no API key)                       │
                        └──────────────────┬─────────────────────┘
                                           │  reads at call time
                                           ▼
                        ┌──────────────────────────────────────┐
                        │   S3 — DataBucket (private)             │
                        │   roadmap_advisor.json                  │
                        │   (precomputed by advisor/build_data.py │
                        │   from BSBAcourse_catalog.xlsx)          │
                        └──────────────────────────────────────┘
```

Everything above is created by `infra/template.yaml` and deployed with
`infra/deploy.sh` — see [Deploying](#deploying--redeploying).

**Not shown above** because they're separate, local-only tools that don't
touch AWS infrastructure at all:
- `schedule_engine`'s CLI pipeline (`extract` → `generate` → `chat`) that
  *produces* the per-major artifacts the frontend serves — see
  [`schedule_engine/README.md`](schedule_engine/README.md).
- `frontend/app.py` (Streamlit) + `mining/co_occurrence.py` +
  `bedrock/client.py` — an earlier, still-functional local tool covering
  pooled co-occurrence stats instead of real degree-roadmap data. See
  [`PROCESS_WRITEUP.md`](PROCESS_WRITEUP.md) for its methodology.

---

## Components

### 1. `schedule_engine/` — schedule generation (CLI, not deployed)
Turns the real Fall 2026 section catalog + degree roadmaps + historical
freshman course-taking patterns into 4–8 real, conflict-checked JSON
schedule blocks per major (beam search, scored on commuter-friendly time
windows, popularity, seat health, and compactness). A counselor chat loop
lets Claude propose edits in plain English, which a deterministic validator
(`schedule_engine/validator.py`) either accepts or rejects — nothing invalid
is ever saved. Output artifacts are copied into
`frontend/web/data/artifacts/` and uploaded to S3 by `infra/deploy.sh` as
part of the frontend bundle. Full detail: [`schedule_engine/README.md`](schedule_engine/README.md).

### 2. `advisor/` — the deployed what-if advisor
- `advisor/build_data.py` — precomputes `roadmap_advisor.json` from
  `BSBAcourse_catalog.xlsx` (every major's full term-by-term roadmap, GE-area
  equivalence groups, and whatever prerequisite text the catalog has —
  honestly partial; see the module's docstring for exactly what is and isn't
  covered).
- `advisor/roadmap.py` — pure-Python lookups over that precomputed data: what
  term is this course normally taken in, does swapping to another course
  satisfy the same requirement slot, what would be delayed if this course
  isn't completed. No LLM involved.
- `advisor/llm_bedrock.py` — has Bedrock narrate the computed findings in
  plain language. Layered prompt-injection defenses: the question is
  spotlighted in delimiters with an explicit override-refusal rule,
  server-side input validation rejects oversized/malformed input before any
  LLM call, the model is never given tool-use (so a jailbreak can only
  produce bad text, not take an action), and IAM/S3 permissions are scoped to
  exactly what's needed.

### 3. `api/handlers/advisor.py` — the one deployed endpoint
`POST /advisor` — takes `{question, major?, course?}`, runs the compute step
above, has Bedrock narrate it, returns `{question, computed, answer}` (the
raw computed findings are included alongside the narration, so nothing is
hidden behind the LLM's phrasing). Authenticates to Bedrock via IAM
(`bedrock:InvokeModel` on both the inference-profile and foundation-model
ARNs — some newer Bedrock models are only invokable through a cross-region
inference profile, not a bare model ID; see the `BedrockModelId` parameter's
description in `infra/template.yaml` if you change models). No API key to
manage.

Two earlier endpoints were dropped along the way: `GET /recommendation` (no
caller in the current frontend) and `POST /ask` (pooled mining-stats Q&A,
replaced by `/advisor`'s real degree-roadmap grounding). Their supporting
code (`api/handlers/recommendation.py`, `bedrock/client.py`) still exists
for the local Streamlit tool but isn't part of the deployed API.

### 4. Infrastructure — `infra/template.yaml` (SAM/CloudFormation)
- **AdvisorFunction** (Lambda) — see above.
- **DataBucket** (S3, private) — holds `roadmap_advisor.json`; only
  `AdvisorFunction`'s execution role can read it.
- **FrontendBucket** (S3, private) — origin for the static site; the only
  reader is CloudFront, via Origin Access Control. No direct public access.
- **FrontendDistribution** (CloudFront) — the public HTTPS URL, with an
  explicit cache policy and a `PriceClass_100` edge footprint (US/Canada/
  Europe — no reason to pay for global reach for a CSUB-only tool).
- API Gateway is throttled (5 req/s, burst 10) as cheap defense-in-depth
  against automated abuse, since every request bills a Bedrock call.

`sam build`'s Python builder has no path-exclude mechanism (`.samignore`
looks like it should provide one but doesn't — verified against SAM CLI
1.163.0/aws-lambda-builders 1.65.0), so `infra/deploy.sh` prunes
`data/raw/` (130MB+ of gitignored source xlsx/csv, which would otherwise
push the Lambda past its 250MB unzipped limit) and test directories from the
build output before deploying.

### 5. Frontend — `frontend/web/`
Static HTML/CSS/JS, no build step or framework. Loads
`schedule_engine`'s generated artifacts client-side for the major/block
picker, week-view calendar, and comparison view (all real data, computed
client-side rationale, no network dependency); the "What-if advisor" box at
the bottom calls `POST /advisor`. Full detail, including how to run it
locally without any AWS deployment: [`frontend/web/README.md`](frontend/web/README.md).

---

## Deploying / redeploying

```bash
cd infra
./deploy.sh --guided   # first time only -- walks through stack name/region
./deploy.sh            # every time after
```

This builds and deploys the CloudFormation stack, regenerates and uploads
`roadmap_advisor.json`, syncs `frontend/web/` to S3 (patching the live API
URL into `config.js` automatically), and invalidates the CloudFront cache so
changes show up immediately. No manual key setup needed — Bedrock auth is
IAM-based.

To find the **current** live URLs at any time (they're stack outputs, so
they'll change if the stack is ever recreated under a different name):

```bash
aws cloudformation describe-stacks --stack-name csub-scheduling-tool \
  --query "Stacks[0].Outputs" --output table
```

Requires AWS credentials with permission to manage Lambda, API Gateway, S3,
CloudFront, and IAM roles, plus Bedrock model access enabled (console →
Bedrock → Model access) for whatever model `BedrockModelId` points at, in
the deploy region.

---

## Repo structure

```
.
├── README.md                # this file
├── PROJECT_MAP.md            # plain-English repo tour for non-developers
├── USER_GUIDE.md             # how to use the deployed tool (chairs/staff)
├── PROCESS_WRITEUP.md        # mining/co_occurrence methodology + reproduction guide
├── challenge_overview.md     # original hackathon problem statement
├── contextv67/
│   └── claude-starter-context.md   # scoping/decision history from the hackathon
│
├── advisor/                  # DEPLOYED: what-if advisor (roadmap engine + Bedrock)
│   ├── build_data.py          # precomputes roadmap_advisor.json from the catalog xlsx
│   ├── roadmap.py              # deterministic lookups (no LLM)
│   ├── llm_bedrock.py          # Bedrock narration + prompt-injection defenses
│   └── tests/
├── api/handlers/
│   ├── advisor.py             # DEPLOYED: POST /advisor
│   ├── _data.py                # S3-backed precomputed-data loaders
│   └── recommendation.py      # not deployed -- local Streamlit tool only
├── infra/
│   ├── template.yaml           # SAM/CloudFormation: Lambda, API Gateway, S3, CloudFront
│   └── deploy.sh                # build + prune + deploy + publish data/frontend
│
├── schedule_engine/           # CLI pipeline: real sections -> per-major schedule blocks
│   ├── generator.py / validator.py / chat.py / catalog.py
│   └── README.md
├── frontend/
│   ├── web/                    # DEPLOYED: the static site (S3 + CloudFront)
│   │   ├── index.html / app.js / config.js
│   │   ├── data/artifacts/     # bundled copies of schedule_engine's output
│   │   └── README.md
│   └── app.py                  # Streamlit, local-only, not deployed
│
├── mining/                    # local-only: pooled co-occurrence stats (see PROCESS_WRITEUP.md)
│   ├── co_occurrence.py
│   └── FRESHMAN_DATASET.md
├── bedrock/
│   └── client.py               # backs the local Streamlit tool only
│
├── data/
│   ├── raw/                    # gitignored -- source xlsx/csv (not in git)
│   └── output/                 # gitignored -- precomputed JSON caches
└── artifacts/                  # schedule_engine's generated per-major schedules
```

---

## Data handling

CSU Bakersfield is a Hispanic-Serving Institution. All student-level data
used anywhere in this repo uses randomly assigned, non-reversible IDs. Do
not attempt to re-identify students or join against any external roster.
Source data files (`data/raw/*.xlsx`, `*.csv`) are gitignored and never
committed — they exist only on machines that have been given the real
extracts directly.

---

## Origin

Built for a 4-day hackathon (see [`challenge_overview.md`](challenge_overview.md)
for the original problem statement and [`contextv67/claude-starter-context.md`](contextv67/claude-starter-context.md)
for the full scoping/decision history). AWS Bedrock, Kiro, and Claude API
tokens were available for the build.
