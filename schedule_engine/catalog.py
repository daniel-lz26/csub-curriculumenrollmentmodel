"""Unified catalog: sections (E3E4), degree roadmaps + GE areas (xlsx),
and freshman popularity (mined first-semester schedules).

Resolves a major's term-1 roadmap into concrete requirements, each with the
list of real sections that can satisfy it.
"""
import csv
import json
import re
from collections import Counter
from dataclasses import dataclass, field

from . import config

GE_AREA_RE = re.compile(r"GE\s+([0-9][A-C]?)|FYS")


def to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


@dataclass
class Requirement:
    name: str                 # roadmap label, e.g. "GE 1A: English Composition"
    req_type: str             # Major | Major / Gen Ed | General Education | Elective
    units: float
    course_options: list      # course codes that satisfy it, e.g. ["ECON 2018", "AGBS 1240"]
    is_ge_placeholder: bool = False


@dataclass
class Catalog:
    term: str
    snapshot_date: str
    sections: list                      # all section dicts
    by_course: dict                     # course code -> [section dicts]
    ge_courses: dict                    # area -> [course codes] (catalog order)
    roadmaps: dict                      # major -> term1 rows (dicts)
    popularity: Counter                 # course code -> freshman count
    cooccur: Counter = field(default_factory=Counter)  # frozenset pair -> count
    n_freshmen: int = 0

    # ---- requirement resolution -------------------------------------------
    def ge_area_of(self, requirement_name: str):
        if requirement_name.startswith("FYS"):
            return "FYS"
        m = GE_AREA_RE.search(requirement_name)
        return m.group(1) if m and m.group(1) else None

    def requirements_for(self, major: str, term_num: int = 1):
        rows = self.roadmaps.get(major)
        if not rows:
            raise KeyError(f"No roadmap for major {major!r}. "
                           f"Known: {sorted(self.roadmaps)}")
        reqs = []
        for r in rows:
            if int(r["term_num"]) != term_num:
                continue
            name = str(r["requirement"]).strip()
            if r["is_ge_placeholder"]:
                area = self.ge_area_of(name)
                options = [c for c in self.ge_courses.get(area, [])
                           if c in self.by_course]
            elif " or " in name:
                options = [c.strip() for c in name.split(" or ")
                           if c.strip() in self.by_course]
            elif name.lower().startswith("additional course"):
                options = []  # open elective; generator skips, chat may fill
            else:
                options = [name] if name in self.by_course else []
            reqs.append(Requirement(
                name=name, req_type=str(r["req_type"]), units=float(r["units"]),
                course_options=options,
                is_ge_placeholder=bool(r["is_ge_placeholder"])))
        return reqs

    def sections_for(self, course: str):
        return self.by_course.get(course, [])

    def popularity_score(self, course: str) -> float:
        """0..1 share of mined freshmen who took this course first semester."""
        if not self.n_freshmen:
            return 0.0
        return self.popularity.get(course, 0) / self.n_freshmen


def load_catalog(year: int = 2026, term: str = "Fall") -> Catalog:
    import pandas as pd

    with open(config.sections_json_path(year, term)) as f:
        snap = json.load(f)
    by_course = {}
    for s in snap["sections"]:
        by_course.setdefault(s["course"], []).append(s)

    ge = pd.read_excel(config.CATALOG_XLSX, "GE_Courses")
    ge_courses = {}
    for r in ge.itertuples():
        ge_courses.setdefault(str(r.ge_area), []).append(f"{r.subject} {r.course_num}")

    rm = pd.read_excel(config.CATALOG_XLSX, "Program_Roadmaps")
    roadmaps = {}
    for r in rm.to_dict("records"):
        roadmaps.setdefault(str(r["major"]), []).append(r)

    popularity, cooccur = Counter(), Counter()
    n = 0
    with open(config.FRESHMAN_SCHEDULES_CSV, newline="") as f:
        for row in csv.DictReader(f):
            courses = [v for k, v in row.items()
                       if k.startswith("course_") and v]
            n += 1
            popularity.update(courses)
            for i, a in enumerate(courses):
                for b in courses[i + 1:]:
                    cooccur[frozenset((a, b))] += 1

    return Catalog(term=snap["term"], snapshot_date=snap["snapshot_date"],
                   sections=snap["sections"], by_course=by_course,
                   ge_courses=ge_courses, roadmaps=roadmaps,
                   popularity=popularity, cooccur=cooccur, n_freshmen=n)
