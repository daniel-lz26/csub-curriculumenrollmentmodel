"""Validates the mining pipeline against the known-good numbers recorded in
contextv67/claude-starter-context.md, so a refactor can't silently drift
from the confirmed real-data baseline.
"""
from mining.co_occurrence import (
    build_candidate_schedules,
    course_frequency,
    load_ba_freshman_rows,
    load_meeting_patterns,
    load_requirement_types,
    load_unit_catalog,
    units_for,
)

# From contextv67/claude-starter-context.md section 6: top first-term courses among the
# 156 Business Administration students, grouped by earliest Course Term
# (all term types combined).
CONFIRMED_FIRST_TERM_COUNTS = {
    "ENGL 1109": 77,
    "CSUB 1029": 71,
    "COMM 1008": 53,
    "MATH 2200": 41,
    "MATH 1010": 40,
    "BA 1008": 35,
    "PHIL 1019": 27,
    "BA 1000": 24,
    "MATH 1050": 22,
    "BA 1028": 22,
    "ACCT 2200": 21,
}


def test_freshman_row_filter_matches_confirmed_student_count():
    freshman = load_ba_freshman_rows()
    assert freshman["Random ID"].nunique() == 156


def test_course_frequency_matches_confirmed_numbers():
    freshman = load_ba_freshman_rows()
    freq = course_frequency(freshman, term_type=None)
    counts = dict(zip(freq["course"], freq["count"]))
    for course, expected_count in CONFIRMED_FIRST_TERM_COUNTS.items():
        assert counts.get(course) == expected_count, (
            f"{course}: expected {expected_count}, got {counts.get(course)}"
        )


def test_unit_catalog_flags_bimodal_courses_as_ambiguous():
    catalog = load_unit_catalog()
    # MATH 1010 is a near-even split between a 3-unit lecture and a 1-unit
    # paired support section under the same catalog number.
    units, ambiguous = units_for("MATH 1010", catalog)
    assert ambiguous is True
    assert units == 3  # canonical/credit-bearing value, not the paired lab


def test_unit_catalog_missing_course_falls_back_with_estimate_flag():
    catalog = load_unit_catalog()
    units, estimated = units_for("ZZZZ 9999", catalog)
    assert estimated is True
    assert units == 3


def test_candidate_schedules_sum_within_unit_target():
    freshman = load_ba_freshman_rows()
    freq = course_frequency(freshman, term_type="Fall")
    catalog = load_unit_catalog()
    schedules = build_candidate_schedules(freq, catalog)
    assert len(schedules) > 0
    for schedule in schedules:
        assert 14 <= schedule["total_units"] <= 15
        assert schedule["total_units"] == sum(c["units"] for c in schedule["courses"])


def test_requirement_types_tag_major_gem_and_ge_courses():
    req_types = load_requirement_types()
    # Major/Gen Ed (GEM): satisfies both a major requirement and GE at once.
    assert req_types["MATH 2200"] == "Major / Gen Ed"
    assert req_types["BA 1028"] == "Major / Gen Ed"
    # Pure major requirement, not GE-eligible.
    assert req_types["ACCT 2200"] == "Major"
    # Pure GE course (from the GE_Courses sheet, not tied to any major).
    assert req_types["ENGL 1109"] == "General Education"


def test_meeting_patterns_only_use_post_census_snapshots():
    patterns = load_meeting_patterns()
    # MATH 2200 is a real Fall 2025 freshman course with day/time recorded
    # in snapshots taken after the 2025-10-20 census fix.
    assert "MATH 2200" in patterns
    for slot in patterns["MATH 2200"]:
        assert slot["sections"] > 0
        # Either a real day/time pair, or an honest note about why not.
        assert (slot["start"] is not None) != (slot["note"] is not None)


def test_candidate_schedule_courses_carry_req_type_and_meeting_patterns():
    freshman = load_ba_freshman_rows()
    freq = course_frequency(freshman, term_type="Fall")
    catalog = load_unit_catalog()
    req_types = load_requirement_types()
    meeting_patterns = load_meeting_patterns()
    schedules = build_candidate_schedules(freq, catalog, req_types, meeting_patterns)
    assert len(schedules) > 0
    for schedule in schedules:
        for course in schedule["courses"]:
            assert "req_type" in course
            assert "meeting_patterns" in course
