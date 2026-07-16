# User Guide: CSUB BSBA Freshman Scheduling Tool

## Purpose

The CSUB BSBA Freshman Scheduling Tool helps department chairs and schedule
builders review real, ready-to-use freshman course schedule blocks for
**first-time BS Business Administration students**, and ask "what if"
questions about failing or swapping a course.

Unlike a purely historical/statistical report, the schedules shown here are
built from the **actual Fall 2026 section catalog** — every course, section,
and meeting time is real and was open at the time the block was generated —
and every block is deterministically checked for time conflicts before it's
ever shown to you.

Use the tool as **decision support**. It is not a student registration
system, does not automatically enroll students, and does not replace final
review by the department, advising team, or registrar.

## What the tool covers

- BS Business Administration freshman planning, across all 10 BSBA
  concentrations (Accounting, Economics, Entrepreneurship, Finance, General
  Business, Health Care Management, Human Resource Management, Management,
  Marketing, Public Administration, Supply Chain Logistics) plus Agricultural
  Business
- Fall 2026 only, currently — there is no term selector because each major's
  data is generated for one term at a time (see `schedule_engine/README.md`
  for how a new term's data gets produced)
- 4–8 candidate schedule blocks per major, each 15–17 units, real
  sections, conflict-checked
- A weekly calendar view of the selected block's actual meeting times
- Side-by-side comparison of every generated block for the major
- A "What-if advisor" that answers questions grounded in the real degree
  roadmap and prerequisite data — not a general chatbot

---

## 1. Pick a major and a block

At the top of the page, two dropdowns:

### Major
Choose the BSBA concentration you're planning for. Unlike an earlier version
of this tool, **this does change what's shown** — each major has its own
independently generated set of real schedule blocks, built from that major's
actual degree roadmap requirements.

### Block
Each major has several generated blocks (labeled, e.g., "Morning core
(10–3)," "TTh-compact commuter," "Fridays-free," "Online-lean flex" — see the
**Compare blocks** section below for the full set). They're sorted by **fit
score** (explained below), with the top-scoring one loaded by default and
marked **★ Top pick**.

The chip next to the pickers shows how many blocks were generated and the
total planned seats across them.

## 2. Check the status ribbon

The banner at the very top tells you where the data came from and whether
the What-if advisor is connected to a live API.

- It always names the section-catalog snapshot the blocks were generated
  from (e.g. "Fall 2026 section snapshot"), since that's what makes these
  real, current sections rather than a historical estimate.
- It says whether the What-if advisor is **live** (connected to the deployed
  API) or in **offline/demo mode**. In demo mode, the major/block picker,
  calendar, and comparison view all still work fully — only the What-if
  advisor is unavailable, and it says so plainly rather than pretending to
  answer.

## 3. Read the Assumptions & methodology panel

Read this before evaluating a block — it states plainly what's real and what
each label means:

- **What this is** — every course/section/time shown was open at the
  snapshot, and each block is deterministically validated conflict-free
  (not just visually non-overlapping — see §5).
- **Fit score** — see §4.
- **Meeting times** — a course with no listed time shows **TBA** (registrar
  hasn't posted a room/time yet) or **Online — async** (asynchronous online
  section, meets by design with no fixed time). Neither is plotted on the
  calendar; both are explicitly listed underneath it instead.
- **Popularity** — shown as "N/D mined freshmen," meaning N of D real
  historical freshmen in this major took that course in their first term.
- **Generator notes** — if present, any caveats the schedule generator
  itself flagged for this major (e.g. a requirement it couldn't fill).

## 4. Review the selected block

The course table for the currently selected block shows:

| Column | How to interpret it |
|---|---|
| **Course** | Course code, title, and section number. A `(waitlist N)` or `(full)` tag means that section had no open seats at generation time — a real seat-availability signal, not a guess. |
| **Requirement** | The specific degree-roadmap requirement this course satisfies |
| **Units** | Real per-section credit units |
| **Freshman popularity** | "N/D mined freshmen" — see above |
| **Requirement type** | A tag: **Major**, **Gen ed**, **GEM** (satisfies both a major and a general-education requirement), or **Elective** |
| **Meeting pattern** | Real days/times, or a TBA/async tag (see §3) |

The header above the table shows the **fit score** — a weighted composite of
four signals: how much of the block's meeting time falls in the preferred
commuter window, how popular its courses were with real historical
freshmen, how healthy its seat counts are, and how compact the resulting
week is (few campus days, small gaps). **It is not a percentage, a
probability, or a number comparable across different majors** — only a
within-major ranking signal for comparing this major's own blocks against
each other. Hover the score for the full definition.

If any section in the block had a seat-availability concern at generation
time, a **seat advisories** banner appears above the table — read it before
approving the block; a full/waitlisted section needs a decision (reserve
seats, swap the block, or accept the risk) before this can be published as
final.

## 5. Review the Week view

A Monday–Sunday calendar of the selected block's real meeting times.

Because every block is deterministically validated conflict-free when it's
generated, the banner above the calendar re-displays that check visibly —
either a confirmation that the shown courses have no time conflicts, or (if
you're looking at a hand-edited or otherwise unusual artifact) an explicit
error naming exactly which two courses overlap and when. That error state is
a real signal that something is wrong with the block; it should not be
published as-is.

Courses with no plottable time (TBA or async-online — see §3) are listed
below the grid instead of being silently dropped or guessed at.

## 6. Read "Why this block"

This short paragraph explains the selected block's shape — total units,
campus days, its most historically popular course, and any advisories or
TBA/async courses to know about.

**This is computed directly from the block's own data, not generated by an
AI** — the page says so explicitly ("computed directly from the artifact —
no AI call"). There's no network dependency and no error state to worry
about here; it's the same deterministic style as the rest of the block data.

## 7. Compare blocks

Lists every other generated block for the current major — course list,
total units, and fit score for each. Expand one to see its full course table
and any seat advisories. Use this when:

- The top pick includes a course that can't actually be offered
- A department has limited section capacity somewhere
- A different time-of-day shape fits better
- You want a backup block on file

Click **View on calendar** on any alternative to swap the week view (§5) to
that block without losing your place.

## 8. Ask the What-if advisor

The **What-if advisor** box at the bottom answers questions like:

- *"What if I fail MATH 2200?"*
- *"What if I take THTR 1009 instead of COMM 1008 — does that set me back?"*

It's grounded in the real degree-roadmap and prerequisite data for the major
currently selected — not the pooled, all-concentration historical stats an
earlier version of this Q&A box used. Where the official catalog data
doesn't list a prerequisite or a requirement equivalency, **the advisor says
so explicitly** rather than guessing — a plain "not confirmed by this data"
is a correct and expected answer for many courses, not a bug. Every answer
carries a reminder that the assistant won't invent something the data
doesn't support.

In offline/demo mode (see §2), this box explains that live answers require a
deployed API rather than pretending to answer.

The tool does not currently provide: recommendations for majors other than
BSBA, student-specific degree audits tied to an individual's real transcript,
login/registration actions, or demand forecasting.

## 9. Uncertainty markers, summarized

| Marker | Meaning |
|---|---|
| `(waitlist N)` | Section had N students waitlisted at generation time |
| `(full)` | Section had zero open seats at generation time |
| `TBA` | No room/time posted yet by the registrar — not an error, just not yet scheduled |
| `Online — async, no fixed meeting time` | Asynchronous online section, correctly has no plotted time by design |
| Seat advisories banner | One or more sections in this block need attention (full/waitlisted) before publishing |
| Calendar conflict error | Something is genuinely wrong with this specific block/artifact — do not publish it as-is |
| Advisor's "not confirmed by this data" | The official catalog doesn't list a prerequisite/equivalency for this course — not the same as "confirmed there is none" |

## 10. Final review before approval

Before turning a block into an official freshman offering:

1. Confirm the courses and sections are still current — this data reflects
   one point-in-time snapshot of the section catalog, not a live feed.
2. Re-check seat counts and waitlist status close to the actual term, since
   they can change after the snapshot.
3. Resolve every seat advisory shown for the block.
4. Confirm placement, transfer-credit, and AP-equivalency exceptions
   separately for any real cohort of students — this tool doesn't have that
   student-specific data.
5. Get sign-off from the department, advising team, and registrar.

The tool supports planning and review. Final scheduling decisions remain the
responsibility of the appropriate university staff.

## Quick reference

1. Check the status ribbon for the data snapshot and advisor status.
2. Pick a **Major**, then a **Block** (or use the default top pick).
3. Read **Assumptions & methodology** once, to know what the labels mean.
4. Review the **Selected block** table, fit score, and any seat advisories.
5. Check the **Week view** — real times, deterministically conflict-checked.
6. Read **"Why this block"** — computed, not AI-generated.
7. Use **Compare blocks** to look at alternatives before committing.
8. Ask the **What-if advisor** about failing or swapping a specific course.
9. Do the final human review (§10) before anything becomes official.
