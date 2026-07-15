# Recommendation rationale prompt

System context passed to Kiro:
- Scope: BS Business Administration, Freshman class year, target unit range (14-15)
- The full precomputed JSON for the requested term (course frequency + candidate schedules)
- An explicit instruction not to introduce course names, counts, or claims absent from the JSON

Ask for: 2-4 sentences, staff-appropriate, always citing the frequency/percentage basis
for the recommendation, plus at least one caveat or runner-up alternative.

If the requested term has no mined data (empty `course_frequency`), say so plainly instead
of extrapolating.
