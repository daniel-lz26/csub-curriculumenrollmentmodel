"""Deterministic degree-roadmap / prerequisite lookups for the schedule
"what-if" advisor (see api/handlers/advisor.py).

Operates entirely on the precomputed JSON from advisor/build_data.py -- no
pandas/openpyxl at runtime, no dependency on the raw (gitignored) .xlsx.
Everything here is plain lookups; no LLM call happens in this module (same
compute-first split as mining/co_occurrence.py vs bedrock/client.py).

Coverage is intentionally honest about its limits: `Program_Roadmaps` gives
every course's normal term-slot, and `GE_Courses` gives clean interchangeable
alternatives per GE area, but `BA_Courses.prerequisites` (free text) only
covers 24 generic BA-prefixed courses -- most major-specific courses (ACCT,
ECON, MATH, ...) have no prerequisite data anywhere in the source catalog.
Callers should surface `no_data_found` rather than assume "no dependency"
means "confirmed no dependency".
"""
from __future__ import annotations

import re

COURSE_CODE_RE = re.compile(r"\b([A-Z]{2,4})\s?(\d{3,4})\b")


def extract_course_codes(text: str) -> list[str]:
    return sorted({f"{sub} {num}" for sub, num in COURSE_CODE_RE.findall(text or "")})


class RoadmapAdvisor:
    def __init__(self, data: dict):
        self.majors: dict[str, list[dict]] = data.get("majors", {})
        self.ge_areas: dict[str, list[str]] = data.get("ge_areas", {})
        self.course_to_ge_area: dict[str, str] = data.get("course_to_ge_area", {})
        self.course_titles: dict[str, dict] = data.get("course_titles", {})
        self.prerequisites: dict[str, dict] = data.get("prerequisites", {})
        self.cumulative_units: dict[str, dict] = data.get("cumulative_units", {})

    # ---- basic lookups ------------------------------------------------
    def known_majors(self) -> list[str]:
        return sorted(self.majors)

    def resolve_major(self, major: str | None) -> str | None:
        """Case-insensitive/whitespace-tolerant match against known majors."""
        if not major:
            return None
        norm = major.strip().lower()
        for m in self.majors:
            if m.lower() == norm:
                return m
        return None

    def known_course(self, course: str) -> bool:
        if course in self.course_titles or course in self.prerequisites:
            return True
        return any(
            course in row["course_options"]
            for rows in self.majors.values()
            for row in rows
        )

    def title_of(self, course: str) -> str | None:
        info = self.course_titles.get(course)
        return info["title"] if info else None

    # ---- roadmap position -----------------------------------------------
    def course_roadmap_position(self, major: str | None, course: str) -> list[dict]:
        """Every roadmap row (across the given major, or all majors if
        major is None/unresolved) where `course` is a valid option."""
        majors_to_search = [major] if major and major in self.majors else self.majors
        hits = []
        for m in majors_to_search:
            for row in self.majors[m]:
                if course in row["course_options"]:
                    hits.append({
                        "major": m,
                        "term_num": row["term_num"],
                        "term_season": row["term_season"],
                        "requirement": row["requirement"],
                        "req_type": row["req_type"],
                    })
        return hits

    # ---- prerequisites -----------------------------------------------
    def explicit_prerequisites(self, course: str) -> dict | None:
        return self.prerequisites.get(course)

    def courses_that_require(self, course: str) -> list[str]:
        return sorted(
            dependent for dependent, info in self.prerequisites.items()
            if course in info["course_codes"]
        )

    # ---- swap / alternatives -----------------------------------------------
    def alternatives_for(self, major: str, course: str) -> list[str]:
        rows = self.course_roadmap_position(major, course)
        alts: set[str] = set()
        for hit in rows:
            for row in self.majors.get(hit["major"], []):
                if row["term_num"] == hit["term_num"] and course in row["course_options"]:
                    alts.update(row["course_options"])
        alts.discard(course)
        return sorted(alts)

    def same_requirement_slot(self, major: str, course_a: str, course_b: str) -> bool | None:
        """True/False if we can determine whether course_b satisfies the same
        roadmap slot as course_a in `major`; None if course_a isn't placed in
        this major's roadmap at all (no basis to compare)."""
        if major not in self.majors:
            return None
        found = False
        for row in self.majors[major]:
            if course_a in row["course_options"]:
                found = True
                if course_b in row["course_options"]:
                    return True
        return False if found else None

    # ---- the main entry point -----------------------------------------------
    def compute_impact(self, question: str, major: str | None = None,
                       course: str | None = None) -> dict:
        resolved_major = self.resolve_major(major)
        major_note = None
        if major and not resolved_major:
            major_note = f"'{major}' is not a recognized major; searched across all majors instead."

        courses: list[str] = []
        if course and self.known_course(course):
            courses.append(course)
        for code in extract_course_codes(question):
            if code not in courses and self.known_course(code):
                courses.append(code)

        no_data_found = []
        findings = []
        for c in courses:
            position = self.course_roadmap_position(resolved_major, c)
            if not position:
                no_data_found.append(f"No roadmap position on file for {c}"
                                     f"{f' in {resolved_major}' if resolved_major else ''}.")
            prereq = self.explicit_prerequisites(c)
            if not prereq:
                no_data_found.append(f"No prerequisite text on file for {c} in the catalog data "
                                     "-- this does not confirm there is no real prerequisite, "
                                     "only that this dataset doesn't list one.")
            dependents = self.courses_that_require(c)
            findings.append({
                "course": c,
                "title": self.title_of(c),
                "roadmap_position": position,
                "explicit_prerequisites": prereq,
                "would_delay_if_not_completed": dependents,
                "alternatives_in_same_slot": self.alternatives_for(resolved_major, c) if resolved_major else [],
            })

        swap_check = None
        if resolved_major and len(courses) == 2:
            result = self.same_requirement_slot(resolved_major, courses[0], courses[1])
            swap_check = {
                "course_a": courses[0], "course_b": courses[1],
                "same_requirement_slot": result,
            }

        if not courses:
            no_data_found.append("No specific course code was recognized in the question or context.")

        return {
            "major_requested": major,
            "major_resolved": resolved_major,
            "major_note": major_note,
            "courses_discussed": courses,
            "findings": findings,
            "swap_check": swap_check,
            "no_data_found": no_data_found,
        }
