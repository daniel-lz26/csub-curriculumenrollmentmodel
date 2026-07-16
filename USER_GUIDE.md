# User Guide: CSUB BSBA Freshman Scheduling Tool

## Purpose

The CSUB BSBA Freshman Scheduling Tool helps department chairs and schedule builders review possible freshman course blocks for **first-time BS Business Administration students**.

The web application combines historical freshman course-taking patterns with course requirement labels and informational meeting patterns. It presents candidate schedules in a format that a chair can review, compare, adjust, and approve.

Use the tool as **decision support**. It is not a student registration system, does not automatically enroll students, and does not replace final review by the department, advising team, or registrar.

## What the web application covers

The web application currently supports:

- BS Business Administration freshman planning
- Fall and Spring term views
- Candidate schedules in the 14–15 unit target range
- Historical course-support percentages
- Major, General Education, and GEM requirement labels
- A weekly informational calendar
- Comparison of alternative candidate schedules
- An optional AI-generated rationale and follow-up Q&A when the live API is available

The web application does not calculate separate freshman recommendations for each concentration. The concentration selector changes the page label only; the freshman-year data is pooled across the BSBA concentrations because their early course-taking patterns are nearly identical in the current data.

## 1. Select a concentration and term

At the top of the page, use the two selectors:

### Concentration

Choose the concentration you want displayed in the page label, such as:

- General Business
- Accounting
- Economics
- Entrepreneurship
- Finance
- Health Care Management
- Human Resource Management
- Management
- Marketing
- Supply Chain Logistics

Because the underlying freshman data is pooled, changing this selector does **not** change the courses, percentages, rationale, or candidate schedules shown. It identifies the concentration context for the person reviewing the page.

### Term

Choose either:

- **Fall**
- **Spring**

The cohort chip shows how many incoming BSBA freshmen are represented in the selected historical term data.

If a term does not have enough historical data to generate a recommendation, the application displays an informational message instead of a candidate schedule. This means the current dataset is insufficient for that term; it does not mean that the university offers no courses in that term.

## 2. Check the status ribbon

The status ribbon tells you where the displayed information came from.

### Demo mode

**Demo mode** uses the bundled local data snapshot. The course tables, candidate schedules, assumptions, and calendar can be reviewed, but live AI rationale and Q&A are unavailable.

Use demo mode to review the scheduling logic and historical data without an AWS deployment.

### Live mode

**Live mode** means the application is connected to the deployed API. In this mode, the application can request a current rationale and answer follow-up questions through the API and Bedrock.

### API fallback

If the application cannot reach the live API, it automatically shows the bundled local snapshot and displays an error banner. In this situation:

- The displayed course data may be stale
- The live AI rationale is unavailable
- Live Q&A is unavailable

Do not treat fallback mode as confirmation that the API data is current.

## 3. Read the Assumptions & Methodology panel

The **Assumptions & methodology** panel appears near the top of the page. Read it before evaluating a candidate schedule because it explains how the recommendation was created and what the data does not prove.

### Requirement labels

The application uses the BSBA roadmap and GE course catalog to label courses as:

- **Major** — associated with a Business Administration major requirement
- **Gen ed** — associated with a General Education requirement
- **GEM** — a Major / General Education course that can satisfy both types of requirement
- **Not in freshman roadmap** — the course was not matched to the freshman-year roadmap data used by the application

Freshman-year roadmap rows are pooled across the BSBA concentrations because the early requirements are nearly identical in the current catalog data.

### Meeting patterns

Meeting patterns come from course-offering snapshots. They show common current or recent day/time patterns when usable data is available.

These patterns are **informational only**. The web recommendation view does not:

- Choose a specific section or class number
- Guarantee that a section will be offered at that time
- Assign an instructor or room
- Verify current seat availability
- Check all courses for conflicts
- Guarantee that the candidate satisfies an individual student's placement or credit history

Always verify the official schedule, section availability, prerequisites, and student exceptions before approving a block.

### Concentration selector limitation

The panel also explains that the concentration selector changes labels only. Do not interpret a Marketing, Finance, or Management selection as a concentration-specific freshman analysis.

## 4. Review the Top candidate schedule

The **Top candidate schedule** is the highest-ranked candidate for the selected term. It is generated from historically frequent freshman courses and a target load of approximately 14–15 units.

The table includes:

| Column | How to interpret it |
|---|---|
| **Course** | A course included in the candidate block |
| **Units** | The credit value used in the candidate's unit calculation |
| **% of cohort** | A historical course-engagement measure based on course-row counts and the selected cohort size |
| **Requirement** | The catalog-based requirement label |
| **Typical meeting pattern** | A common day/time pattern from the available offering data |

The top candidate also displays a **support score**. This is a ranking signal based on the average historical course frequency of the courses in the candidate. It is not a probability of student success, a predicted enrollment count, or a guarantee that students took the entire block together.

### Interpreting the percentage

The percentage is calculated from course-row counts divided by the number of unique students in the selected cohort. Some source records can contain more than one related row for a student, such as a lecture and co-requisite support record. Therefore, the percentage is best interpreted as a historical support or engagement measure—not an exact percentage of unique students who completed the entire candidate schedule.

The web interface may display a percentage with a count, such as:

```text
68% (34/50)
```

Use the count and cohort size as context, but do not interpret the course percentage as proof that 34 students took every course in the candidate block together.

## 5. Review the Week view

The **Week view** displays a Monday–Sunday calendar using the most common clean meeting slots available for the active candidate.

The calendar helps you visually review:

- The general time window of the candidate
- The number of campus days suggested by the meeting patterns
- Long gaps between classes
- Apparent overlaps
- Courses whose meeting information could not be plotted

The calendar is explicitly **not conflict-checked**. An overlap, missing block, or unusually long gap should trigger verification against the official section schedule rather than an assumption that the candidate is valid or invalid.

The calendar may list courses below the grid when they have:

- No post-census meeting data
- No cleanly parseable meeting time
- An asynchronous or otherwise unplottable meeting pattern

## 6. Review Bedrock rationale

When the application is connected to the live API, the **Bedrock rationale** provides a short explanation of why the candidate was recommended. It should be grounded in the computed course data and may mention a caveat or alternative.

In demo or offline mode, the application explains that live AI rationale is unavailable. The course table remains available for review; only the generated explanation is missing.

If the rationale fails because of credentials, access, throttling, or another temporary issue, the course table is still the primary data display. Do not treat the absence of a rationale as evidence that the course recommendation is invalid.

## 7. Compare candidate schedules

The **Compare candidate schedules** section lists alternatives considered by the application. Each alternative includes:

- Its course list
- Total units
- Support score
- Course-level details
- Typical meeting patterns

Use the comparison view when:

- The top candidate includes a course that cannot be offered
- A department has limited section capacity
- A different course mix better fits placement needs
- You want a backup block
- You want to inspect the runner-up mentioned by the rationale

Select **View on calendar** for an alternative to replace the active calendar with that candidate's informational meeting patterns.

## 8. Ask a follow-up question

The **Ask a question** area is available for questions about the mined BSBA freshman data when the application is connected to the live API.

Examples include:

- `What if we can only run one section of ACCT 2200?`
- `Which courses are most common for BSBA freshmen?`
- `What changes if I need a fourth major course instead of a General Education course?`
- `What is the runner-up schedule if one course is unavailable?`

The assistant is intended to explain or re-filter the computed data. It should not invent course names, counts, percentages, meeting times, prerequisites, or requirements that are not in the source data.

In demo or offline mode, Q&A is disabled because no live Bedrock request is available.

Questions outside the current scope may receive a response saying that the information is unavailable. The web application does not currently provide:

- Psychology or other-major recommendations
- Student-specific degree audits
- Login or registration actions
- A guaranteed demand forecast
- Final section conflict checking
- Automatic registration

## 9. Understand uncertainty markers

The application intentionally exposes uncertainty instead of presenting every value as exact.

### `(uncertain)` beside units

This marker indicates that the course was not found in the available E3/E4 offering catalog and the unit value was defaulted for the calculation. Confirm the official catalog and section record before relying on the total unit count.

The underlying data pipeline can also encounter ambiguous unit patterns, such as different section types associated with one course number. When the displayed value affects a planning decision, verify the official course and section record.

### `Not in freshman roadmap`

This means the course was not matched to the freshman-year roadmap slice used by the application. It does not prove that the course is a non-major elective or that it should be excluded.

### `no post-census meeting data`

This means the application could not find usable recent meeting-pattern information for that course. It does not mean that the course is unavailable or has no meeting time.

### A meeting-time caveat

A note instead of a clean time means the source contained meeting information that could not be reliably converted into a start and end time. The application displays the caveat instead of inventing a time.

## 10. Distinguish the web view from validated schedule artifacts

The web application described above is a **historical recommendation view**. It identifies frequently occurring course combinations and shows informational meeting patterns.

The repository also contains a separate `schedule_engine` workflow for generating and validating schedule artifacts from real sections. That workflow is not the same as the web page and is not controlled by the concentration and term selectors described above.

When a validated schedule-engine artifact is provided by the scheduling team, it may include:

- Real section identifiers and meeting times
- A block for each freshman cohort
- Roadmap requirement coverage
- Deterministic conflict validation
- Unit checks
- Seat-health warnings or reservation advisories
- A change history for counselor-approved edits
- Optional student-specific schedules derived from a cohort block

Treat a schedule-engine artifact as a separate deliverable with its own validation status. The web page's historical recommendation and calendar must not be treated as proof that an artifact or final registration schedule is conflict-free.

## 11. Final review before approval

Before turning a candidate or validated artifact into an official freshman block, confirm:

1. The courses are approved for the intended term.
2. Actual sections exist with sufficient seats.
3. Meeting days and times are verified from the official schedule.
4. Course conflicts have been checked using the appropriate schedule-validation workflow.
5. Catalog prerequisites and placement requirements are satisfied.
6. The unit total matches the intended freshman pathway.
7. Math and writing placement differences are handled separately.
8. AP, dual-enrollment, transfer-credit, and completed-course exceptions are reviewed.
9. Any seat warnings or advisories are resolved or explicitly accepted.
10. The department, advising team, and registrar agree on the final block.

The tool supports planning and review. Final scheduling decisions remain the responsibility of the appropriate university staff.

## Quick reference

1. Check the status ribbon.
2. Select a concentration for the page label and select **Fall** or **Spring**.
3. Read **Assumptions & methodology**.
4. Review the **Top candidate schedule**, units, support score, percentages, and requirement labels.
5. Inspect the **Week view**, remembering that it is informational and not conflict-checked.
6. Read the live **Bedrock rationale** when available.
7. Compare alternatives and use **View on calendar** when useful.
8. Ask a follow-up question when the live API is available.
9. Verify sections, seats, prerequisites, placements, and conflicts before approval.
