# Ad hoc Q&A prompt

System context passed to Claude on every call (stateless — no conversation memory needed,
the computed dataset is small enough to pass whole each time):
- Scope: BS Business Administration, Freshman class year, target unit range (14-15)
- The full precomputed JSON for all mined terms (course frequency + candidate schedules)
- An explicit instruction to answer only from the provided JSON, re-filtering/re-explaining
  it as needed, and to say so plainly if the question can't be answered from it (e.g. a
  major outside scope, or a term with no mined data) rather than extrapolating.

Each staff question is answered fresh against the same JSON — no code path per scenario.
