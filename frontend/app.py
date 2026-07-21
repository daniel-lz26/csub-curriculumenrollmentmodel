"""Staff-facing Streamlit app: pick a term, see the recommended lineup and
rationale, ask follow-up questions underneath.

Calls the API handler functions in-process (no network hop) so this is
runnable without deploying anything to AWS. Swapping to real HTTP calls
against API Gateway later is a one-line change per call site.
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.handlers._data import load_mined_data
from bedrock.client import answer_question, generate_recommendation

st.set_page_config(page_title="BA Freshman Scheduling", layout="centered")
st.title("BS Business Administration — Freshman Scheduling")
st.caption("Staff decision support: recommended course lineups from real historical patterns.")

data = load_mined_data()

# ---------------------------------------------------------------------------
# Assumptions & methodology panel
# ---------------------------------------------------------------------------
# The mining layer already calculates an "assumptions" dictionary and stores
# it in the recommendation data. This dictionary explains how the results
# were produced and what limitations the user should understand.
#
# We use .get() instead of directly accessing data["assumptions"] so the app
# will not crash if an older recommendation.json file does not contain this
# newer field. In that situation, the panel will display a fallback message.
assumptions = data.get("assumptions", {})

# Retrieve the two methodology explanations created by
# mining/co_occurrence.py:
#
# 1. "req_type" explains how courses are labeled as Major, General Education,
#    or Major / General Education.
#
# 2. "meeting_patterns" explains where typical meeting times come from and
#    warns the user that those times are informational rather than guaranteed
#    conflict-free section assignments.
requirement_assumption = assumptions.get(
    "req_type",
    "Requirement labels are not available in the current recommendation data.",
)

meeting_time_assumption = assumptions.get(
    "meeting_patterns",
    "Meeting-time methodology is not available in the current recommendation data.",
)

# This heading is intentionally outside an expander. A department chair or
# advisor should see the data limitations immediately instead of having to
# search for them.
st.markdown("### Assumptions & methodology")

# st.info() gives the methodology a visually distinct information-panel
# appearance in Streamlit. The text is written for staff users who need to
# understand how much confidence to place in the recommendation.
st.info(
    f"**Requirement labels:** {requirement_assumption}\n\n"
    f"**Meeting-time information:** {meeting_time_assumption}"
)

# This reminder reinforces an important project limitation directly beside
# the recommendation interface. The mining code reports common meeting
# patterns, but it does not choose actual sections or test every course
# combination for a time conflict.
st.caption(
    "Important: meeting times are informational patterns from the source data. "
    "They are not guaranteed section assignments and are not conflict-checked."
)

term = st.selectbox("Term", options=list(data["terms"].keys()))
term_data = data["terms"][term]

st.subheader(f"{term} — cohort size: {term_data['cohort_size']}")

if not term_data["course_frequency"]:
    st.warning(f"No mined historical data is available for {term} for BS Business Administration freshmen.")
else:
    with st.spinner("Generating rationale..."):
        try:
            rationale = generate_recommendation(term, term_data)
        except RuntimeError as e:
            rationale = f"(LLM unavailable: {e})"
    st.markdown("### Recommended lineup")
    top = term_data["candidate_schedules"][0] if term_data["candidate_schedules"] else None
    if top:
        def _meeting_summary(course: dict) -> str:
            patterns = course.get("meeting_patterns") or []
            if not patterns:
                return "no post-census meeting data"
            best = patterns[0]
            if best["note"]:
                return best["note"]
            return f"{best['days']} {best['start']}-{best['end']}"

        st.table(
            [
                {
                    "Course": c["course"],
                    "Units": c["units"] if not c["units_estimated"] else f"{c['units']} (uncertain)",
                    "% of cohort": f"{c['pct_of_cohort']:.0%}",
                    "Requirement": c.get("req_type") or "—",
                    "Typical meeting time": _meeting_summary(c),
                }
                for c in top["courses"]
            ]
        )
        st.write(f"**Total units:** {top['total_units']}")
        st.caption(
            "Meeting times are informational (most common section slot currently "
            "on file) and aren't checked for conflicts across courses."
        )
    st.markdown("### Rationale")
    st.write(rationale)

    with st.expander("All candidate schedules"):
        for i, sched in enumerate(term_data["candidate_schedules"], 1):
            st.write(f"{i}. {', '.join(c['course'] for c in sched['courses'])} — {sched['total_units']} units")

    with st.expander("Full course frequency table"):
        st.table(
            [
                {
                    "Course": c["course"],
                    "Count": c["count"],
                    "% of cohort": f"{c['pct_of_cohort']:.0%}",
                    "Units": c["units"],
                    "Requirement": c.get("req_type") or "—",
                }
                for c in term_data["course_frequency"]
            ]
        )

st.markdown("---")
st.subheader("Ask a follow-up question")
question = st.text_input("e.g. \"What if we can only run one section of ACCT 2200?\"")
if st.button("Ask") and question:
    with st.spinner("Thinking..."):
        try:
            answer = answer_question(question, data)
        except RuntimeError as e:
            answer = f"(LLM unavailable: {e})"
    st.write(answer)
