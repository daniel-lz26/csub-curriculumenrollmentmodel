# Frontend spec — BSBA Freshman Scheduling Tool

Design notes for `frontend/app.py`, written against the actual API contract
(`api/handlers/recommendation.py`, `api/handlers/ask.py`, and the JSON shape
produced by `mining/co_occurrence.py::mine()`), not a generic dashboard
template. See `README.md` for the audience/scope framing this builds on:
a department-chair-facing decision-support tool, not a chatbot-first UI or
a student-facing planner.

---

## Current state (what already exists)

`frontend/app.py` is a working single-page Streamlit app that:
- Picks a term (Fall/Spring) via a selectbox
- Shows the top candidate schedule as a table (course, units, % of cohort,
  requirement type, typical meeting time) + Bedrock rationale
- Has collapsed expanders for "all candidate schedules" and the "full course
  frequency table"
- Has a free-text Q&A box at the bottom, calling `answer_question`

It calls the handler functions in-process (no HTTP), which is correct for
now — the docstring already flags the swap to real API Gateway calls as a
"one-line change per call site" once `infra/deploy.sh` has been run.

This spec is about what's *missing*, not a rewrite.

---

## Gap: the JSON's `assumptions` block is computed but never shown

`mine()` returns a top-level `assumptions` dict (methodology caveats for
`req_type` and `meeting_patterns` — e.g. "GEM classification pools all 10
BSBA concentrations," "meeting time is informational, not conflict-checked").
`frontend/app.py` never reads `data["assumptions"]`.

This is the highest-priority fix. README lists a "process write-up... so
CSUB can hand it to psychology or another major and reproduce it with their
own data" as a required deliverable, not optional polish — the UI is the
natural place to surface that methodology to the actual user (a department
chair), not just a separate doc. A chair deciding whether to trust a
generated schedule needs to see *why* a course is unlabeled or a meeting
time is missing, in context, not in a README they'll never open.

**Feature: an "Assumptions & methodology" panel**, always visible (not
buried in an expander), rendering `data["assumptions"]["req_type"]` and
`data["assumptions"]["meeting_patterns"]` as plain text near the top of the
page — this is the tool's credibility mechanism, it shouldn't be optional.

---

## Gap: uncertainty is inconsistently surfaced

The data model has three distinct flavors of "this number isn't solid,"
and the UI currently only surfaces one of them well:

| Signal | Meaning | Currently shown? |
|---|---|---|
| `units_estimated=True` | Course missing from the E3E4 offering catalog; units defaulted to 3 | Yes — `"3 (uncertain)"` in the table |
| `req_type=None` | Course not found in the freshman-year roadmap slice at all | Partially — renders as `"—"`, easy to misread as "confirmed non-major" rather than "unknown" |
| `meeting_patterns=[]` | No post-census (post-2025-10-20) snapshot data for this course | Yes — `"no post-census meeting data"` |

Also missing: `ambiguous_units` (a course with a near-even split between two
credit values, e.g. a 3-unit lecture + 1-unit co-req support section) is
computed in `mining/co_occurrence.py::load_unit_catalog` but the flag itself
(distinct from `units_estimated`) isn't passed through to the frontend at
all — only the resolved (higher) value is shown, with no way to tell "this
was a clean single value" from "this was a coin-flip between two real
values." Worth checking whether `describe_course` should thread this through
before this becomes a frontend feature request; right now there's nothing
for the UI to render.

**Feature:** replace the bare `"—"` for unknown `req_type` with an explicit
`"not in freshman roadmap"` label — distinguishing "confirmed elective /
non-major" (which doesn't exist as a state today) from "we don't have
data," matching the existing honesty bar set by the units/meeting-time
caveats.

---

## Gap: no way to compare schedules side-by-side

"All candidate schedules" today is a flat text list (`course, course, course
— N units`) in an expander — useful for confirming alternatives exist, not
for actually comparing them. A chair choosing between the top pick and a
runner-up (which the Bedrock rationale is instructed to mention — see
`generate_recommendation`'s inline system prompt in `bedrock/client.py`,
asking for "one caveat or a runner-up alternative") currently has no way to
see the runner-up's full course-level detail without manually
reading the frequency table below and cross-referencing.

(Note: `bedrock/client.py` builds its system prompt inline in
`generate_recommendation`/`answer_question` — the files under
`bedrock/prompts/` are not actually loaded by the code, so treat them as
reference notes, not the live prompt source, if editing prompt wording.)

**Feature:** render every candidate schedule (not just the top one) using
the *same* per-course table as the top pick, with the top pick pinned/
highlighted and the rest collapsible — so "runner-up" in the rationale text
is something the chair can actually inspect, not just take on faith.

---

## Gap: cohort size and score aren't put in context

Each candidate schedule has a `score` (mean course frequency across its
courses) but it's dropped entirely from the UI (only `total_units` is
shown in the expander). Cohort size is shown once, in the section header,
disconnected from the per-course `pct_of_cohort` figures below it. A chair
skimming the table sees "68% of cohort" without an easy read on whether
that's 68% of 12 students (noisy) or 68% of 120 (solid).

**Feature:** keep cohort size visible alongside every percentage, not just
once at the top — e.g. `"68% (34/50 students)"` instead of `"68%"` — and
show `score` as a plain "support" figure when listing multiple candidate
schedules, since that's the ranking signal a chair would want when judging
whether the top pick is a clear winner or a close call against the
runner-up.

---

## Gap: empty/error states are minimally handled

- A term with `cohort_size == 0` renders one `st.warning` line and nothing
  else (correct, but terse for a chair who may not know why).
- Bedrock unavailability (`RuntimeError`) is caught and rendered inline as
  `"(LLM unavailable: ...)"` — functional, but doesn't distinguish "Bedrock
  access not configured" (a deploy problem) from "no data for this
  term/question" (an expected state) from a transient throttling error. All
  three currently look identical to the chair.

**Feature:** distinguish these at least at the message level — reuse the
existing guardrail language from `bedrock/client.py`'s `GUARDRAIL` constant
("if the question or term can't be answered from this data, say so") so a
genuine "no data" answer from Kiro doesn't read the same as an outage.

---

## Non-goals (explicitly out of scope, per README)

Do **not** build, even as a stretch feature:
- Conflict-checked scheduling (times aren't validated against each other —
  every meeting-time display must keep the existing "informational, not
  conflict-checked" caption)
- Per-concentration views (BSBA's 10 concentrations are pooled for freshman
  year — a concentration picker would misrepresent the data as more granular
  than it is)
- Any student-facing surface, login, or per-student data — this is a single
  staff-facing planning view, not a roster or advising tool
- Multi-major support in this pass (the JSON schema's `major`/`class_year`
  fields suggest it, but the mining layer is hardcoded to
  `TARGET_MAJOR = "business administration"` — a major picker would be
  UI-only theater until the mining layer actually supports it)

---

## Suggested priority order

1. Assumptions/methodology panel (cheapest, highest trust payoff, data
   already computed)
2. Unknown-`req_type` relabeling (one string change)
3. Cohort-size-in-context for percentages (small template change)
4. Multi-schedule comparison view (the biggest lift — reuses the existing
   per-course table renderer across all candidates instead of just the top
   one)
5. Error-state differentiation (depends on `bedrock/client.py` exposing
   distinguishable exception types, not currently the case — everything is
   a bare `RuntimeError` today)
