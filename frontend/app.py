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
