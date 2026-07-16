"""Tests for the deterministic roadmap/prerequisite engine. Runs against the
real precomputed data/output/roadmap_advisor.json (regenerate with
`python -m advisor.build_data` if the catalog source changes) plus a couple
of synthetic-data cases for edge conditions the real data doesn't exercise.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from advisor.roadmap import RoadmapAdvisor, extract_course_codes

DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "output" / "roadmap_advisor.json"


@pytest.fixture(scope="module")
def real_data() -> dict:
    if not DATA_PATH.exists():
        pytest.skip("data/output/roadmap_advisor.json not built -- run `python -m advisor.build_data`")
    return json.loads(DATA_PATH.read_text())


@pytest.fixture(scope="module")
def advisor(real_data) -> RoadmapAdvisor:
    return RoadmapAdvisor(real_data)


class TestExtractCourseCodes:
    def test_finds_codes_in_free_text(self):
        assert extract_course_codes("What if I fail MATH 2200 next term?") == ["MATH 2200"]

    def test_dedupes_and_sorts(self):
        assert extract_course_codes("ACCT 2200 and math 2200 and ACCT 2200") == ["ACCT 2200"]

    def test_no_codes_in_plain_question(self):
        assert extract_course_codes("What courses are typically morning classes?") == []


class TestRoadmapPosition:
    def test_direct_course_found_in_known_major(self, advisor):
        hits = advisor.course_roadmap_position("BA - Accounting", "MATH 2200")
        assert hits == [{
            "major": "BA - Accounting", "term_num": 1, "term_season": "Fall",
            "requirement": "MATH 2200", "req_type": "Major / Gen Ed",
        }]

    def test_ge_placeholder_resolves_to_real_course_list(self, advisor):
        hits = advisor.course_roadmap_position("BA - Accounting", "COMM 1008")
        assert hits and hits[0]["requirement"] == "GE 1C: Oral Communication"

    def test_unknown_course_returns_empty(self, advisor):
        assert advisor.course_roadmap_position("BA - Accounting", "ZZZZ 9999") == []

    def test_no_major_searches_all_majors(self, advisor):
        hits = advisor.course_roadmap_position(None, "MATH 2200")
        assert any(h["major"] == "BA - Accounting" for h in hits)


class TestPrerequisites:
    def test_parsed_course_codes(self, advisor):
        prereq = advisor.explicit_prerequisites("BA 3010")
        assert prereq["course_codes"] == ["MATH 2200", "MIS 2000"]

    def test_parsed_unit_threshold(self, advisor):
        prereq = advisor.explicit_prerequisites("BA 3008")
        assert prereq["unit_threshold"] == 45
        assert prereq["course_codes"] == []

    def test_no_prerequisite_data_is_none_not_empty_dict(self, advisor):
        # MATH 2200 has no row in BA_Courses at all -- this must be
        # distinguishable from "has prerequisites, just none listed".
        assert advisor.explicit_prerequisites("MATH 2200") is None

    def test_reverse_lookup_finds_dependents(self, advisor):
        assert "BA 3010" in advisor.courses_that_require("MATH 2200")

    def test_reverse_lookup_empty_for_course_nothing_depends_on(self, advisor):
        assert advisor.courses_that_require("ART 1009") == []


class TestSwapEquivalence:
    def test_same_ge_area_alternatives_are_swappable(self, advisor):
        assert advisor.same_requirement_slot("BA - Accounting", "COMM 1008", "THTR 1009") is True

    def test_different_slot_courses_are_not_swappable(self, advisor):
        assert advisor.same_requirement_slot("BA - Accounting", "MATH 2200", "ACCT 2200") is False

    def test_course_not_in_roadmap_returns_none(self, advisor):
        assert advisor.same_requirement_slot("BA - Accounting", "ZZZZ 9999", "COMM 1008") is None

    def test_alternatives_for_excludes_self(self, advisor):
        alts = advisor.alternatives_for("BA - Accounting", "COMM 1008")
        assert "THTR 1009" in alts
        assert "COMM 1008" not in alts


class TestComputeImpact:
    def test_identifies_course_from_question_text(self, advisor):
        result = advisor.compute_impact("What if I fail MATH 2200?", major="BA - Accounting")
        assert result["courses_discussed"] == ["MATH 2200"]
        assert result["major_resolved"] == "BA - Accounting"
        assert result["findings"][0]["would_delay_if_not_completed"] == ["BA 3010"]

    def test_flags_missing_prerequisite_data_honestly(self, advisor):
        result = advisor.compute_impact("What if I fail MATH 2200?", major="BA - Accounting")
        assert any("No prerequisite text on file for MATH 2200" in n for n in result["no_data_found"])

    def test_unrecognized_major_falls_back_with_a_note(self, advisor):
        result = advisor.compute_impact("What if I fail MATH 2200?", major="Not A Real Major")
        assert result["major_resolved"] is None
        assert "not a recognized major" in result["major_note"]

    def test_no_course_found_is_flagged_not_silently_empty(self, advisor):
        result = advisor.compute_impact("How many units do freshmen usually take?", major="BA - Accounting")
        assert result["courses_discussed"] == []
        assert result["no_data_found"] == ["No specific course code was recognized in the question or context."]

    def test_swap_question_runs_equivalence_check(self, advisor):
        result = advisor.compute_impact(
            "What if I take THTR 1009 instead of COMM 1008?", major="BA - Accounting")
        assert result["swap_check"] == {
            "course_a": "COMM 1008", "course_b": "THTR 1009",
            "same_requirement_slot": True,
        }


class TestSyntheticEdgeCases:
    """Cases the real catalog data doesn't exercise -- constructed fixtures."""

    def test_major_resolution_is_case_and_whitespace_tolerant(self):
        data = {"majors": {"BA - Marketing": []}, "ge_areas": {}, "course_to_ge_area": {},
                "course_titles": {}, "prerequisites": {}, "cumulative_units": {}}
        a = RoadmapAdvisor(data)
        assert a.resolve_major("  ba - marketing  ") == "BA - Marketing"
        assert a.resolve_major("BA - Nonexistent") is None
        assert a.resolve_major(None) is None

    def test_empty_data_everything_is_none_or_empty_not_a_crash(self):
        a = RoadmapAdvisor({})
        assert a.known_majors() == []
        assert a.course_roadmap_position("Anything", "MATH 2200") == []
        assert a.explicit_prerequisites("MATH 2200") is None
        assert a.same_requirement_slot("Anything", "A 100", "B 200") is None
