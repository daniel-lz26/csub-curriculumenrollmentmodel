# Requirements Document

## Introduction

The Freshman Schedule Optimizer is a faculty-facing backend feature that generates optimized course schedules for incoming freshmen at CSUB across all available majors. It generalizes the existing Business Administration co-occurrence mining to support any major, loads historical first-term course data and likely freshmen rosters from CSV files, generates candidate 4-5 course schedule combinations targeting 14-15 units, scores them by historical co-occurrence frequency, and returns up to 10 ranked schedule options with natural language explanations via the existing Bedrock/Kiro layer.

## Glossary

- **Schedule_Optimizer**: The backend module that loads data, computes co-occurrence scores, generates candidate schedules, and returns ranked results for a given major.
- **Co_Occurrence_Score**: A numeric score representing how frequently a set of courses appeared together in historical freshman first-term enrollments. Higher score indicates courses freshmen historically take together more often.
- **Candidate_Schedule**: A combination of 4-5 courses totaling 14-15 units, drawn from courses historically taken by freshmen in the selected major.
- **Freshman_Course_Data**: The CSV file (`freshman_first_term_courses.csv`) containing historical records of courses taken by freshmen in their first term, with columns: Random ID, Term, Course Abbreviation, Course Number, course, level.
- **Freshmen_Roster**: The CSV file (`likely_freshmen_roster.csv`) containing incoming freshman records with columns: Random ID, first_term, first_term_num_courses, first_term_frac_1000lvl, inferred_major, terms_on_record, total_courses_on_record.
- **Major**: A CSUB undergraduate major identifier (e.g., "CMPS", "PSYC", "BA", "BIOL", "KINE") used to filter the freshmen roster and course data.
- **Explanation_Service**: The existing Bedrock/Kiro integration layer that generates natural language rationale grounded in precomputed schedule data.
- **Schedules_Endpoint**: The `POST /schedules` API endpoint that accepts a major and returns ranked schedule options with explanations.

## Requirements

### Requirement 1: Major Selection and Validation

**User Story:** As a faculty member, I want to select a major from all available CSUB freshman majors, so that I can generate schedule recommendations specific to that program.

#### Acceptance Criteria

1. WHEN a valid major identifier is provided in the request body, THE Schedules_Endpoint SHALL accept the major and proceed with schedule generation.
2. IF an unrecognized major identifier is provided, THEN THE Schedules_Endpoint SHALL return an HTTP 400 response with an error message listing the valid major identifiers.
3. THE Schedule_Optimizer SHALL derive the list of valid majors dynamically from the distinct non-null, non-empty values of the `inferred_major` column of the Freshmen_Roster data.
4. THE Schedule_Optimizer SHALL perform case-insensitive comparison when matching the provided major identifier against the list of valid majors.
5. IF the `major` field in the request body is null or an empty string, THEN THE Schedules_Endpoint SHALL return an HTTP 400 response with an error message indicating that a non-empty major identifier is required.

### Requirement 2: Data Loading and Filtering

**User Story:** As a faculty member, I want the system to load the correct historical data for the selected major, so that recommendations are based on actual freshman enrollment patterns.

#### Acceptance Criteria

1. WHEN a major is selected, THE Schedule_Optimizer SHALL load the Freshmen_Roster and filter to students whose `inferred_major` matches the selected major using case-insensitive exact matching with leading and trailing whitespace trimmed.
2. WHEN the roster is filtered, THE Schedule_Optimizer SHALL extract the Random IDs of freshmen in that major and use them to filter the Freshman_Course_Data to only courses taken by those students in their first term, defined as each student's earliest Course Term value.
3. IF the Freshman_Course_Data file is missing or unreadable, THEN THE Schedule_Optimizer SHALL return an HTTP 500 response with an error message indicating the data source is unavailable.
4. IF the Freshmen_Roster file is missing or unreadable, THEN THE Schedule_Optimizer SHALL return an HTTP 500 response with an error message indicating the data source is unavailable.
5. IF no students match the selected major in the Freshmen_Roster, THEN THE Schedule_Optimizer SHALL return an HTTP 200 response with an empty schedules list and a message indicating no historical data exists for that major.
6. IF the major parameter is missing, empty, or contains only whitespace, THEN THE Schedule_Optimizer SHALL return an HTTP 400 response with an error message indicating that a valid major must be provided.
7. WHEN loading completes successfully, THE Schedule_Optimizer SHALL return the filtered course data within 5 seconds of receiving the request.

### Requirement 3: Co-Occurrence Computation

**User Story:** As a faculty member, I want the system to identify which courses freshmen in a given major historically take together, so that schedule combinations reflect real enrollment patterns.

#### Acceptance Criteria

1. WHEN first-term course data is filtered for a major, THE Schedule_Optimizer SHALL compute the enrollment count for each course appearing in that cohort's first term, where "first term" is defined as the earliest Course Term value recorded for each student.
2. THE Schedule_Optimizer SHALL normalize each course count by the number of unique students in the filtered cohort, producing a frequency value between 0.0 and 1.0 (inclusive), rounded to 4 decimal places.
3. IF a cohort contains fewer than 5 students for the requested major, THEN THE Schedule_Optimizer SHALL return an HTTP 200 response with an empty schedules list and a warning message indicating that the sample size is insufficient for reliable recommendations.
4. IF a cohort contains 0 students for the requested major, THEN THE Schedule_Optimizer SHALL return an HTTP 200 response with an empty course frequency list, an empty schedules list, and a cohort size of 0.

### Requirement 4: Candidate Schedule Generation

**User Story:** As a faculty member, I want the system to generate course combinations that meet unit requirements, so that recommended schedules are viable full-time loads.

#### Acceptance Criteria

1. THE Schedule_Optimizer SHALL generate candidate schedules containing between 2 and 6 courses inclusive.
2. THE Schedule_Optimizer SHALL include only candidate schedules whose total units sum to between 14 and 15 inclusive.
3. THE Schedule_Optimizer SHALL assign unit values to courses using the existing unit catalog from the course offering data, falling back to 3 units when a course is not present in the catalog.
4. WHEN generating candidates, THE Schedule_Optimizer SHALL consider the top 12 courses by individual frequency in the filtered cohort to limit the combinatorial search space.
5. THE Schedule_Optimizer SHALL rank candidate schedules by descending mean cohort-frequency score and return no more than 5 top-ranked results.
6. IF fewer than 1 candidate schedule meets the unit-sum constraint, THEN THE Schedule_Optimizer SHALL return an empty candidate list.

### Requirement 5: Schedule Scoring and Ranking

**User Story:** As a faculty member, I want schedules ranked by how commonly those courses appear together, so that top recommendations reflect proven freshman enrollment patterns.

#### Acceptance Criteria

1. THE Schedule_Optimizer SHALL score each candidate schedule by computing the arithmetic mean of the individual course co-occurrence frequencies (pct_of_cohort values) for all courses in the schedule, expressed as a decimal rounded to four decimal places.
2. THE Schedule_Optimizer SHALL rank candidate schedules in descending order by their Co_Occurrence_Score.
3. THE Schedule_Optimizer SHALL return at most 10 ranked candidate schedules.
4. WHEN two candidate schedules have equal Co_Occurrence_Scores, THE Schedule_Optimizer SHALL rank them by total unit count in descending order as a tiebreaker.
5. IF two candidate schedules have equal Co_Occurrence_Scores and equal total unit counts, THEN THE Schedule_Optimizer SHALL maintain a stable ordering among those tied schedules such that repeated invocations with the same input produce the same ranked output.

### Requirement 6: API Endpoint

**User Story:** As a faculty member, I want a single API endpoint to request schedule recommendations, so that I can integrate this into existing workflows.

#### Acceptance Criteria

1. THE Schedules_Endpoint SHALL accept HTTP POST requests with a JSON body containing a `major` field of type string, with a length between 1 and 100 characters after trimming whitespace.
2. WHEN a successful schedule generation completes, THE Schedules_Endpoint SHALL return an HTTP 200 response containing: the major, cohort size, unit target range, the list of ranked candidate schedules with courses and scores, and a natural language explanation.
3. THE Schedules_Endpoint SHALL follow the existing Lambda-shaped handler pattern (event/context signature) used by the recommendation and ask handlers.
4. IF the request body is missing the `major` field or the `major` field is empty after trimming whitespace, THEN THE Schedules_Endpoint SHALL return an HTTP 400 response with an error message indicating the field is required.
5. IF no mined data exists for the provided major value, THEN THE Schedules_Endpoint SHALL return an HTTP 400 response with an error message indicating that the major is not recognized.
6. IF the request body is not valid JSON, THEN THE Schedules_Endpoint SHALL return an HTTP 400 response with an error message indicating the body must be valid JSON.
7. IF the natural language explanation generation fails, THEN THE Schedules_Endpoint SHALL still return the ranked schedules with a null explanation field and an HTTP 200 status code.

### Requirement 7: Natural Language Explanation

**User Story:** As a faculty member, I want a plain-language explanation of why each top schedule is recommended, so that I can communicate the reasoning to colleagues and students.

#### Acceptance Criteria

1. WHEN ranked schedules are generated with mined data, THE Explanation_Service SHALL produce a natural language rationale of 2 to 4 sentences for the top-ranked schedule, citing the co-occurrence frequency data that supports the recommendation.
2. WHEN the Explanation_Service produces a rationale, THE Explanation_Service SHALL reference at least one specific co-occurrence percentage value (e.g., "X% of the cohort enrolled in course Y") drawn from the precomputed mining output.
3. WHEN the Explanation_Service produces a rationale, THE Explanation_Service SHALL mention at least one runner-up candidate schedule or one limitation of the top recommendation (such as estimated unit values or limited cohort size).
4. IF the requested major has no mined historical data (empty course_frequency), THEN THE Explanation_Service SHALL return a rationale stating that no recommendation can be made for that major instead of invoking the language model.
5. IF the Bedrock service is unavailable or fails to respond within 30 seconds, THEN THE Schedules_Endpoint SHALL return the ranked schedules with a null explanation field and an HTTP 200 status code.

### Requirement 8: Data Integrity and Isolation

**User Story:** As a faculty member, I want assurance that the system handles data correctly and does not mix data across majors, so that recommendations are trustworthy.

#### Acceptance Criteria

1. THE Schedule_Optimizer SHALL use only courses from students whose `inferred_major` matches the requested major (case-insensitive, leading/trailing whitespace trimmed) when computing co-occurrence, and SHALL exclude all student records with a different or missing major value.
2. THE Schedule_Optimizer SHALL use randomly assigned, non-reversible student IDs (identifiers that cannot be mapped back to institutional student records) and SHALL NOT expose individual student identifiers, names, or contact information in any API response.
3. THE Schedule_Optimizer SHALL include the cohort size (number of unique students whose records were used in the computation) in the response so faculty can assess statistical confidence.
4. IF the cohort size for the requested major is fewer than 5 unique students, THEN THE Schedule_Optimizer SHALL return an indication that the sample size is insufficient and SHALL NOT produce candidate schedule recommendations for that request.
