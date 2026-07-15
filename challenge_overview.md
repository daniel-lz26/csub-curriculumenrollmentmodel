# Challenge Overview: Curriculum and Enrollment Decision-Support Models — Generative AI for schedule alignment and block-registration optimization

## Project Objectives
- Provide decision-support evidence on enrollment patterns, prerequisite necessity, and course success to inform (not replace) faculty governance
- Enable optimized block-registration schedules for incoming freshmen (e.g., 15-unit blocked schedules combining math, English, and core major courses)
- Improve faculty, advisor, and student experience with better-informed curricular guidance and time-to-degree outcomes
- Target measurable downstream effects on student success and time-to-degree, plus adoption of insights in curriculum review
- Leave room to extend into waitlist demand analysis and section-shopping pattern detection (online vs. in-person, time-of-day, day-of-week)

## Current Workflow
- Enrollment and academic data live in PeopleSoft, Runner Connect, transfer transcripts, and substitution records, managed via IRPA tooling
- Faculty and committees plan section counts and seats each cycle; advisors guide students through degree maps and recommended paths
- Answering questions like prerequisite success or section demand requires manual, time-consuming series of analyses (e.g., cross-referencing waitlists against current enrollment)
- Degree maps, planners, and catalog course-offering data maintained on the side, though not always fully up to date
- Legacy/constrained tooling: EAB Navigate (without predictive add-ons), UAchieve degree planner being added; waitlist data historically incomplete

## Key Pain Points
- No existing tool can answer curricular questions such as prerequisite necessity or student pathway alignment against maps
- Waitlist and section-shopping analysis requires tribal knowledge and manual effort to detect patterns
- Time cost of manually cross-referencing waitlists, enrollment, and scheduling data
- Building blocked freshman schedules and forecasting demand is manual and could be optimized
- Deterministic ML models depend on very high-quality data and are hard to complete in a 6-day camp; block-registration and waitlist patterns are more tractable

## Ideal Solution Vision
- Generative AI approach to schedule alignment and block-registration optimization (pivoting away from data-heavy deterministic ML) — addresses the 6-day feasibility constraint
- Example: given historical class lists and a degree map, generate optimized 15-unit blocked freshman schedules for large majors (e.g., Business Administration, Psychology, Biology, History)
- Index historical freshman enrollment, past scheduling, and degree maps by major, with course-offering timing from the catalog
- Optional surface: concierge that reviews a student's target sections, likelihood of enrollment, and helps prioritize based on availability
- Extension path: grow into waitlist demand modeling and section-shopping pattern detection without a rewrite

## Data Availability
- Primary source of truth: PeopleSoft, Runner Connect, transfer/substitution records, and IRPA institutional research data (enrollment, admissions, yield, courses, grades)
- Supplementary: degree maps, planners, catalog course-offering data, historical freshman class lists by major; partial historical waitlist data
- Human resources: IRPA as essential data owner and methodologist, BPA sponsor as SME, faculty-governance partners; associate deans can update course-offering data
- Known gaps: waitlist data not consistently saved historically; catalog offering data not always up to date; data must be de-identified or synthetic with equity-aware safeguards for an HSI

> **Note:** Sample or synthetic data is available (de-identified, governed by IRPA).