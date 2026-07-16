# CSUB Freshman Course-Mining Methodology

## Purpose and audience

This document describes the reproducible methodology behind the CSU Bakersfield BS Business Administration freshman scheduling tool. It is intended for CSUB staff, another department, or a future developer who needs to repeat the analysis with a different major and a new set of institutional data.

The tool is **decision support**, not a predictive model, degree audit, registration system, or final conflict-free scheduler. Its governing principle is:

> **Compute first; let the language model explain.**

Course counts, percentages, unit totals, candidate generation, and ranking are deterministic pandas operations. The Bedrock layer receives the computed JSON and explains it or answers questions about it; it does not invent schedules or perform the arithmetic.

## Current scope

The primary pipeline currently analyzes:

- Major: Business Administration
- Student group: freshman-year rows from the BSBA enrollment extract
- Terms displayed: Fall and Spring
- Candidate target: 14–15 units per candidate
- Output: course frequencies, requirement labels, optional unit uncertainty, informational meeting patterns, and ranked candidate combinations

The current pipeline defines a student's freshman-year data as the rows from that student's **earliest `Course Term`** in the enrollment extract. It does not currently assemble every term in a full academic year. That distinction matters when reproducing the process.

A separate E6 builder in `mining/build_freshman_dataset.py` uses a different likely-freshman rule and is not joined to the primary BSBA co-occurrence pipeline. It should not be substituted for the primary pipeline without an explicit population decision.

## Data sources and provenance

The reproducible run uses local, fixed files. The Python code does not live-scrape the public CSUB pages at runtime.

| Input | Role in the current pipeline | Real or derived? |
|---|---|---|
| `Senior spring 2026.xlsx` | Enrollment rows and the major field used to isolate BSBA students | Real institutional extract; student IDs are randomized |
| `BSBAcourse_catalog.xlsx` | Roadmap requirement labels, GEM classification, and GE course lookup | Catalog/roadmap reference data |
| `E3E4_Course Offering and Waitlist_daily snapshot for Fall 2025 and 2026.csv` | Per-section units and post-census meeting-pattern enrichment | Real offering snapshot; it is Fall-focused |
| `E6_Student_Course_Scheduling_Pattern.xlsx` | Separate likely-freshman dataset builder only | Real extract, not joined to the primary pipeline |

The team also identified these public CSUB pages as catalog and roadmap references:

- [CSUB Business Administration course descriptions](https://catalog.csub.edu/course-descriptions/ba/)
- [CSUB Business Administration–Marketing pathway, 2025](https://programmap.csub.edu/pathway/business-administration-marketing-to-bachelor-s-degree/?pt=map&year=2025&t%5B%5D=1&t%5B%5D=2&t%5B%5D=3&t%5B%5D=4&t%5B%5D=5&t%5B%5D=6&t%5B%5D=7&t%5B%5D=8&v=1)

The course-description page provides course names, credit values, typical offering terms, prerequisites, and GE attributes for BA-prefixed courses. The pathway page provides a term-by-term course/task map with course type and units; it also illustrates the distinction between `Major`, `General Education`, and `Major / Gen Ed` requirements. These pages should be captured with an access date or exported into a local catalog workbook when reproducing the analysis. The current scripts expect the workbook and snapshots listed above, not a live website connection.

All student-level data must remain de-identified. Do not attempt to reverse the randomized IDs or join them to an external roster.

## 1. Isolate the freshman-year rows

The primary function is `load_ba_freshman_rows` in `mining/co_occurrence.py`.

### 1.1 Filter the target major

1. Read the enrollment workbook.
2. Normalize the `Major` field by converting it to text, trimming whitespace, and lowercasing it.
3. Keep rows whose normalized value equals `business administration`.

For another major, replace this target with the institution's agreed major value and document whether the field represents a declared major, concentration, or program path.

### 1.2 Use `Course Term`, not `Enroll Term`

`Enroll Term` is the student's most recent enrollment term in the source extract. It is not necessarily the term in which an individual course row was taken. The pipeline therefore uses the row-level `Course Term` field.

For each `Random ID`:

1. Convert `Course Term` to a trimmed string.
2. Find that student's minimum `Course Term` value.
3. Keep every row whose `Course Term` equals that minimum.

This preserves all rows from the student's earliest recorded term. It is intentionally not a student-level deduplication step.

### 1.3 Interpret the term code

The current code maps the final digit of a CSU-style term code as follows:

| Final digit | Term type |
|---:|---|
| `1` | Winter |
| `2` | Spring |
| `3` | Summer |
| `4` | Fall |

The output currently generates separate Fall and Spring sections. Winter and Summer can be parsed by the loader, but the `mine` function does not currently emit recommendation sections for them.

### 1.4 Build a stable course key

The course key is created by trimming and concatenating the subject and course number:

```text
SUBJECT + " " + CATALOG_NBR
```

For example, the two source fields become `MATH 2200`. The replacement dataset must provide equivalent subject and number fields or a documented mapping.

### 1.5 Important definition boundary

This primary pipeline calls the earliest recorded term “freshman year,” but it is operationally an **earliest-term cohort**. It does not prove that the extract begins at a student's actual first college term, and it does not include the following Spring/Summer terms automatically.

The separate E6 script uses a different rule: a student qualifies as a likely freshman start when at least 50% of the courses in their earliest recorded term are 1000-level. That script also has a freshman-academic-year variant in an older implementation. Because E6 has no major field and no overlapping IDs with the primary enrollment extract, it remains a separate, unresolved track.

## 2. Count freshman course frequency

The `course_frequency` function counts course occurrences in the isolated rows.

### 2.1 Count rows, not unique students

The count is `value_counts()` over the course key. It is therefore a **row count**, not a count of distinct students.

Some courses appear twice for one student in the same term under one catalog number. The project identified examples such as MATH 1010, MATH 1050, and GEOL 2010, where paired lecture and co-requisite support sections can share a catalog number. Removing duplicates would hide that source structure, so the current method retains the rows.

### 2.2 Calculate the displayed percentage

For an optional term type, the pipeline first determines the cohort size as:

```text
number of unique Random ID values in the selected rows
```

For each course:

```text
pct_of_cohort = course row count / unique-student cohort size
```

Because the numerator is a row count and the denominator is a unique-student count, this percentage is a **historical course-engagement/support measure**. It is not guaranteed to be the percentage of unique students who took the course, and it is not the percentage of students who took an entire candidate block together.

The calculation is deterministic and reproducible, but its interpretation must be documented whenever duplicate course rows are possible.

## 3. Determine units and identify estimates

The `load_unit_catalog` and `units_for` functions use the E3/E4 offering snapshot.

### 3.1 Real per-section units

The offering file's `CSU_APDB_CMP_UNITS` field is grouped by normalized course key. If at least 90% of the observed values for a course agree, the most common value is used as the course's unit value.

If the observed unit values are not at least 90% consistent, the code selects the highest observed unit value and marks the course as `ambiguous_units`. This handles catalog numbers that combine different section types, such as a credit-bearing lecture and a lower-unit support section, without silently presenting the result as unambiguous.

### 3.2 Missing-course fallback

If a course is absent from the E3/E4 file, the code assigns `DEFAULT_UNITS = 3` and sets `units_estimated = True`.

The reason a course may be absent is important: the current E3/E4 extract is Fall-focused, so absence does not prove that a course is not offered in Spring. The fallback is a planning estimate, not an authoritative catalog value. A department must verify the official catalog or section record before approving a unit total.

### 3.3 Candidate unit target

The current code searches for combinations whose summed units are between 14 and 15 inclusive. It applies that flat target to both Fall and Spring.

This is a tool search target, not a claim that every roadmap term totals 14–15 units. The historical `CHANGES.md` record described an earlier 14–16-unit plan and an earlier period when E3/E4 had not yet arrived. Those statements are historical context; the current implementation is authoritative for the present output: 14–15 units, with E3/E4 now used when available.

## 4. Tag Major, General Education, and GEM courses

The requirement-label function is `load_requirement_types` in `mining/co_occurrence.py`.

### 4.1 Operational definition of GEM

In this project, **GEM** means a course whose roadmap `req_type` is exactly:

```text
Major / Gen Ed
```

It is a course that can satisfy both a major requirement and a General Education requirement according to the roadmap. The label is based on the catalog/roadmap definition, not inferred from frequency or from the course subject.

The public pathway page provides examples of this structure, including a course listed as `Major / Gen Ed`, while the public course-description page supplies course-level descriptions and credit information. The reproducible pipeline uses the corresponding local workbook values.

### 4.2 Roadmap lookup procedure

1. Read the `Program_Roadmaps` sheet.
2. Keep rows whose `major` starts with `BA -`.
3. Keep freshman roadmap rows where `term_num <= 2`.
4. Exclude rows marked `is_ge_placeholder` because entries such as `GE 1A: English Composition` name a GE area rather than a specific course.
5. Split alternatives written with ` or ` into individual course keys.
6. Store each course's `req_type`.
7. Read the `GE_Courses` sheet and add courses not already assigned a label as `General Education`.

The implementation uses `setdefault`, so an existing roadmap-derived label is retained when the GE sheet also contains the course.

### 4.3 Why concentrations are pooled

The current workbook contains ten BSBA concentration roadmaps. The project compared their term 1–2 rows and found them near-identical for freshman planning. The implementation therefore pools all `BA - *` concentrations instead of selecting one concentration's roadmap.

This is a data-backed BSBA decision, not a universal rule. For another major:

- Compare the relevant major or concentration roadmaps first.
- Pool only when the freshman requirements are demonstrably equivalent.
- Otherwise, produce separate requirement maps or explicitly select one pathway.

### 4.4 GEM labels do not change unit arithmetic

The current implementation attaches `req_type` to course-frequency rows and candidate-schedule rows as an informational label. It does **not** maintain separate major-unit and GE-unit buckets, and it does not count a GEM course twice in the unit sum.

Candidate generation sums each course's selected unit value once toward the flat 14–15-unit target. A future requirement-audit feature could track whether a schedule covers each major and GE bucket, but that is not part of this mining method.

## 5. Generate and rank candidate schedules

The `build_candidate_schedules` function performs a bounded, deterministic search:

1. Sort courses by descending frequency.
2. Keep the top 12 courses.
3. Consider combinations of 2 through 6 courses.
4. Keep combinations whose unit sum is 14–15 inclusive.
5. Score each combination as the arithmetic mean of its component courses' `pct` values.
6. Sort by descending score.
7. Return at most the top 5 combinations.

The score is a simple, defensible proxy for historical support:

```text
candidate score = mean(pct_of_cohort for courses in candidate)
```

It is not a probability model, demand forecast, guarantee of student success, or proof that students took those courses together as a block. The search also does not enforce prerequisites, section capacity, student placement, or schedule conflicts.

## 6. Add informational meeting patterns

The `load_meeting_patterns` function enriches course records with commonly observed meeting patterns from E3/E4.

### 6.1 Use post-census records only

The source documentation states that meeting day/time fields were added after the Fall 2025 census, precisely on **2025-10-20**. The code excludes snapshots before that date instead of interpreting their blank fields as asynchronous courses.

For each course, the code:

1. Parses `SNAPSHOT_DATE`.
2. Keeps snapshots on or after 2025-10-20.
3. Keeps the latest row for each course and `CLASS_SECTION`.
4. Counts the observed slots.
5. Returns up to six most common slots.

### 6.2 Caveats and notes

The output may include:

- A clean day/start/end time
- `No Patterns`, meaning asynchronous or no fixed meeting time
- A note that the day/time was not cleanly parseable from the source
- An empty list when no usable post-census pattern was found

Rows with a day pattern combined with facility or date-range text and a `00:00:00` time are not treated as midnight meetings. They receive a caveat instead of an invented time.

These are **informational course-level enrichments**. The process does not select a specific section, reserve a seat, assign an instructor or room, or check conflicts between courses. A department must use the official section schedule or a separate validated scheduling workflow for those decisions.

## 7. Output structure

`mine()` produces a JSON object containing:

- `major`: Business Administration
- `class_year`: Freshman
- `unit_target`: `[14, 15]`
- `assumptions`: explanations for requirement labels and meeting-pattern limitations
- `terms`: Fall and Spring payloads

Each term payload contains:

- `cohort_size`: unique students in that term subset
- `course_frequency`: course, row count, percentage, units, estimate flag, requirement label, and meeting patterns
- `candidate_schedules`: course details, total units, and support score

The output can be saved as a precomputed JSON artifact. The recommendation and Q&A layers should consume this structured output rather than raw student-level records.

## 8. What is real, derived, or assumed?

| Item | Classification | Interpretation |
|---|---|---|
| Enrollment rows | Real input | Historical records from the supplied extract |
| BSBA filter | Deterministic rule | Exact normalized major match |
| Earliest-term freshman isolation | Deterministic rule with a population assumption | Assumes the earliest recorded term represents the student's freshman start |
| Course frequency | Derived statistic | Row counts within the isolated rows |
| Cohort size | Derived statistic | Unique randomized students in the selected term subset |
| Displayed percentage | Derived statistic with a caveat | Row count divided by unique-student cohort size |
| E3/E4 unit value with 90% agreement | Real catalog snapshot value | Per-section credit value observed in the file |
| Fallback unit value | Assumption/estimate | Default of 3 units when the course is missing from E3/E4 |
| Ambiguous unit value | Conservative derived choice | Highest observed value, flagged as ambiguous |
| GEM label | Catalog-derived classification | `Program_Roadmaps.req_type == "Major / Gen Ed"`; roadmap label for a course satisfying both requirement areas |
| Requirement label | Catalog-derived classification | Informational label attached to output; not a separate unit bucket |
| Candidate combination | Deterministic search result | Combination of high-frequency courses within the unit target |
| Candidate score | Derived ranking statistic | Mean of component course percentages |
| Meeting pattern | Real offering snapshot enrichment | Common observed course-level slot after 2025-10-20 |
| Conflict-free schedule | **Not provided by this pipeline** | Requires section selection and a separate conflict validator |
| Current seat availability | **Not guaranteed** | Requires current offering and enrollment review |
| Student-specific fit | **Not provided** | Requires placement, transfer, AP, prerequisite, and degree-audit data |

## 9. Reproduce the process for another major

The following sequence is the recommended handoff procedure. Keep the same order so that population decisions are made before ranking decisions.

### Step 1: Define the population

Document:

- The major/program value used in the enrollment extract
- Whether concentrations are pooled or separated
- The student identifier field and its de-identification method
- What “freshman” means for the new extract
- The terms included in the analysis

Do not assume that the earliest recorded term is a student's true first term. Check coverage and transfer behavior first.

### Step 2: Inventory and freeze the input files

Record the file name, source owner, extract date, row count, student count, and relevant columns for:

- Enrollment history
- Program roadmap and catalog
- Course offerings and units
- Meeting patterns, if available

If public catalog pages are used, save their URLs, access date, and a local snapshot or exported workbook. A future run should be reproducible even if a web page changes.

### Step 3: Validate the row-isolation rule

Run the population filter and inspect:

- Number of students before and after the major filter
- Earliest-term distribution
- Number of students with an isolable earliest term
- Common first-term courses
- Whether duplicated course rows represent legitimate lecture/lab or co-requisite structure

Have an institutional data owner approve the resulting population before generating recommendations.

### Step 4: Build the requirement map

For the new major's roadmap:

1. Identify the rows belonging to the major and the relevant freshman terms.
2. Separate actual course codes from GE-area placeholders.
3. Preserve the roadmap's requirement-type field.
4. Define the local GEM rule. In this project it is the exact `Major / Gen Ed` value.
5. Resolve course alternatives and GE course mappings.
6. Decide whether different concentrations can be pooled.

Do not infer GEM status from a course name, frequency, or subject prefix when the official roadmap provides a requirement type.

### Step 5: Prepare unit and meeting data

Map the offering file's subject and catalog-number fields to the same normalized course key used by the enrollment data. Confirm that unit values are real credit values and record the rule for inconsistent or missing values.

If meeting data is absent, leave meeting patterns empty and state that limitation. Do not fabricate times from course names or typical schedules.

### Step 6: Run deterministic mining

Apply the same sequence:

1. Isolate the selected population's earliest-term rows.
2. Parse term types.
3. Count course rows.
4. Compute unique-student cohort sizes.
5. Attach unit and requirement metadata.
6. Search bounded combinations in the desired unit range.
7. Rank by the documented support score.
8. Add meeting patterns only as an optional enrichment.
9. Write structured JSON with an explicit assumptions block.

For a new major, review whether the top-12-course limit, 2–6-course combination limit, 14–15-unit target, and top-five output limit remain appropriate. These are current BSBA configuration choices, not universal academic rules.

### Step 7: Validate before publication

Compare the output with:

- Official roadmap requirements
- Current catalog units and prerequisites
- Current term offerings and seat counts
- Known first-term enrollment patterns
- Placement and transfer-credit rules
- Section-level conflict checks, if a real block is being built

Publish the result only with a clear distinction between historical support, catalog classification, and actual schedule feasibility.

## 10. Separate the mining output from a final schedule

The output identifies course combinations that are historically supported and fall within the configured unit target. It does not select specific sections.

A final schedule or block requires another process to choose real sections and verify:

- Section identifiers
- Days, start times, and end times
- Prerequisites and placement requirements
- Seat capacity and waitlist status
- Instructor and room constraints
- Conflicts across all selected sections
- Student-specific exceptions

The web calendar and meeting-pattern fields should therefore be described as informational. A separate `schedule_engine` workflow may validate real-section artifacts, but it is not part of the co-occurrence calculation described here.

## 11. Historical decisions and current implementation

The historical `CHANGES.md` decision record explains why the project adopted this approach. It recorded that the BSBA roadmap was needed to resolve requirement labels, that freshman roadmaps across the ten concentrations were nearly identical, and that E3/E4 meeting data was initially a requested dependency rather than an available input.

The current implementation incorporates later decisions and should take precedence when the historical record differs:

- The current candidate target is **14–15 units**, not the earlier 14–16 planning range.
- E3/E4 is now present and supplies unit values plus post-census meeting-pattern enrichment.
- Meeting patterns remain optional and informational; they are not used to reject or rank a candidate for conflicts.
- GEM/requirement labels are attached to output but do not change the flat unit-sum arithmetic.
- The separate E6 likely-freshman builder remains unresolved and is not joined to the primary BSBA data.

When handing this method to another department, record both the implementation version and the input-file versions. A methodology is reproducible only when the population rule, catalog snapshot, thresholds, and caveats are versioned together.

## 12. Minimum handoff checklist

Before another department runs this process, provide:

- [ ] A de-identified enrollment extract with documented column meanings
- [ ] The major/program filter and freshman-population definition
- [ ] A roadmap/catalog export with requirement types and GE mappings
- [ ] A unit source and a documented missing/ambiguous-unit rule
- [ ] Optional meeting-pattern data with its availability date
- [ ] The configured unit target and combination limits
- [ ] The formula for course percentage and candidate score
- [ ] A list of assumptions and known limitations
- [ ] A validation owner from the department or institutional research team
- [ ] The date and URLs for any public catalog sources

## Summary

The method is a transparent sequence: isolate the earliest recorded BSBA term, preserve and count its course rows, divide by a unique-student cohort size, attach catalog-based requirement/GEM labels, resolve units from offering data with explicit fallback flags, search bounded 14–15-unit combinations, rank them by mean historical support, and optionally add common post-census meeting patterns.

The result is useful because each step can be inspected and rerun. It must remain labeled honestly: historical patterns are not forecasts, GEM labels are not double-counted units, estimated units are not catalog facts, meeting patterns are not conflict checks, and a candidate is not an approved student schedule.

*External source pages were reviewed on July 15, 2026. The local input files and implementation used for a production rerun should be versioned and revalidated rather than relying on an unchanged web page.*
