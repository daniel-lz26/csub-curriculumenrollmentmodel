# BS Business Administration Freshman Scheduling Tool

A staff-facing tool that recommends which courses/sections to set up each
semester for BS Business Administration freshmen at CSU Bakersfield, using
real historical course-taking patterns plus a generative AI layer for
explanation and ad hoc Q&A.

Built for a 4-day hackathon. AWS Bedrock, Kiro, and Kiro API tokens
available. See `kiro-starter-context.md` for the full scoping/decision
history — this file covers the architecture and how the pieces fit together.

---

## What this is (and isn't)

- **Is:** a decision-support tool for admin/staff planning course offerings
  for one major (Business Administration), one class year (freshmen),
  targeting 14–15 unit schedules.
- **Isn't:** a predictive ML model, a student-facing planner, an advisor
  tool, or scoped to any major/class year beyond the above.

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
          │  course co-occurrence by term │
          │  → candidate 14-15 unit combos│
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

### 1. Data layer — S3
Raw source: `Senior_spring_2026.xlsx`, filtered to Business Administration
majors and exported to CSV. 156 students, ~6,700 course-taking rows. Static
for the hackathon — no live sync needed.

### 2. Mining layer — Lambda (Python/pandas)
- Groups students by earliest course term to isolate freshman-year courses
- Counts course co-occurrence within that term
- Rolls counts into candidate combinations that sum to 14–15 units
- Outputs a small structured JSON (course, term, frequency, unit count) —
  this is precomputed once and stored back in S3 rather than recomputed on
  every request, since the dataset doesn't change during the hackathon

### 3. Reasoning layer — Bedrock (Kiro)
Two jobs, both grounded strictly in the precomputed JSON — never given raw
student-level data:
- **Recommendation + rationale:** turns the top-ranked combo into a
  staff-readable explanation with a percentage basis and a runner-up option
- **Ad hoc Q&A:** answers staff follow-up questions ("what if we can't
  offer X?") by re-filtering/re-explaining the same computed dataset

### 4. API layer — API Gateway + Lambda
Thin layer exposing:
- `GET /recommendation?term=` — returns the top combo(s) + rationale
- `POST /ask` — takes a staff question, returns Kiro's answer grounded in
  the computed data

### 5. Frontend — Streamlit
Staff-facing, not a chatbot-first UI: pick a term, see the recommended
lineup and rationale up front, with a Q&A box underneath for follow-ups.

---

## Suggested repo structure

```
.
├── README.md
├── kiro-starter-context.md
├── data/
│   └── (local dev copies of filtered CSVs — not committed if large/sensitive)
├── mining/
│   └── co_occurrence.py          # pandas mining logic, unit tested against
│                                  # known first-term numbers (see context file)
├── bedrock/
│   ├── prompts/
│   │   ├── recommendation.md
│   │   └── qa.md
│   └── client.py
├── api/
│   └── handlers/
│       ├── recommendation.py
│       └── ask.py
├── infra/                        # IaC (SAM/CDK), scaffolded via Kiro
└── frontend/
    └── app.py                    # Streamlit
```

---

## Data handling

CSU Bakersfield is a Hispanic-Serving Institution. All data in this repo
uses randomly assigned, non-reversible student IDs. Do not attempt to
re-identify students or join against any external roster.

---

## Team

4 backend developers. Day-by-day task split and scope traps are documented
in `kiro-starter-context.md`.
