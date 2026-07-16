"""Deterministic validation of schedule artifacts (cohort sets and student
schedules). The LLM proposes edits; this module decides whether they are real.

Hard ERRORS  -> artifact rejected, fed back to the model for repair:
  - section doesn't exist in the term's catalog (or fields don't match it)
  - time conflict inside a block / student schedule
  - a roadmap requirement is no longer covered
  - duplicate course in one block
Soft WARNINGS -> surfaced to the counselor, never block a save:
  - meetings outside the preferred window
  - section full / waitlisted
  - units off the roadmap target
"""
from .catalog import Catalog, to_minutes
from .generator import conflicts


def _index_catalog(cat: Catalog):
    return {s["class_nbr"]: s for s in cat.sections}


def _check_courses(rows, cat_idx, where, errors, warnings, prefs):
    win = prefs.get("preferred_window", {"start": "10:00", "end": "15:00"})
    lo, hi = to_minutes(win["start"]), to_minutes(win["end"])
    seen_courses = set()
    for r in rows:
        tag = f"{where}: {r.get('course', '?')} #{r.get('class_nbr', '?')}"
        sec = cat_idx.get(str(r.get("class_nbr")))
        if sec is None:
            errors.append(f"{tag} — class_nbr not in the {prefs.get('_term','term')} catalog (invented section?)")
            continue
        for f_art, f_cat in (("course", "course"), ("section", "section"),
                             ("units", "units")):
            if r.get(f_art) != sec[f_cat]:
                errors.append(f"{tag} — field '{f_art}'={r.get(f_art)!r} does not "
                              f"match catalog value {sec[f_cat]!r}")
        if sorted(r.get("days") or []) != sorted(sec["days"]) or \
                r.get("start") != sec["start"] or r.get("end") != sec["end"]:
            errors.append(f"{tag} — meeting days/times don't match catalog "
                          f"({sec['days']} {sec['start']}-{sec['end']})")
        if r.get("course") in seen_courses:
            errors.append(f"{tag} — duplicate course in the same schedule")
        seen_courses.add(r.get("course"))

        if sec["days"] and sec["start"]:
            s, e = to_minutes(sec["start"]), to_minutes(sec["end"])
            if s < lo or e > hi:
                warnings.append(f"{tag} — meets {sec['start']}-{sec['end']}, "
                                f"outside preferred window {win['start']}-{win['end']}")
        if sec["seats_open"] <= 0:
            warnings.append(f"{tag} — section is full "
                            f"(waitlist {sec['waitlist']}) at snapshot")

    # pairwise time conflicts against the real catalog rows
    real = [cat_idx[str(r["class_nbr"])] for r in rows
            if str(r.get("class_nbr")) in cat_idx]
    for i, a in enumerate(real):
        for b in real[i + 1:]:
            if conflicts(a, b):
                errors.append(f"{where} — time conflict: {a['course']} #{a['class_nbr']} "
                              f"({','.join(a['days'])} {a['start']}-{a['end']}) vs "
                              f"{b['course']} #{b['class_nbr']} "
                              f"({','.join(b['days'])} {b['start']}-{b['end']})")


def _check_requirements(rows, reqs, where, errors):
    covered = {r.get("course") for r in rows}
    for req in reqs:
        if not req.course_options:
            continue  # roadmap row with no offered sections; counselor's call
        if not covered & set(req.course_options):
            errors.append(f"{where} — requirement not covered: {req.name!r} "
                          f"(any of {req.course_options})")


def validate_cohort(artifact: dict, cat: Catalog):
    errors, warnings = [], []
    prefs = dict(artifact.get("preferences") or {})
    prefs["_term"] = artifact.get("term")
    cat_idx = _index_catalog(cat)
    try:
        reqs = cat.requirements_for(artifact["major"])
    except KeyError as e:
        return [str(e)], warnings

    blocks = artifact.get("blocks") or []
    if not blocks:
        errors.append("artifact has no blocks")
    ids = [b.get("block_id") for b in blocks]
    if len(ids) != len(set(ids)):
        errors.append(f"duplicate block_ids: {ids}")

    for b in blocks:
        where = f"block {b.get('block_id')}"
        rows = b.get("courses") or []
        _check_courses(rows, cat_idx, where, errors, warnings, prefs)
        _check_requirements(rows, reqs, where, errors)
        units = sum(float(r.get("units") or 0) for r in rows)
        if abs(units - float(b.get("total_units") or 0)) > 0.01:
            errors.append(f"{where} — total_units={b.get('total_units')} but "
                          f"courses sum to {units}")
        if not 12 <= units <= 18:
            warnings.append(f"{where} — {units} units is outside the typical "
                            f"14-17 freshman block range")
    return errors, warnings


def validate_student(student: dict, parent: dict, cat: Catalog):
    errors, warnings = [], []
    prefs = {**(parent.get("preferences") or {}),
             **(student.get("preferences") or {})}
    prefs["_term"] = parent.get("term")
    cat_idx = _index_catalog(cat)
    try:
        reqs = cat.requirements_for(parent["major"])
    except KeyError as e:
        return [str(e)], warnings
    rows = student.get("courses") or []
    where = f"student {student.get('student_id')}"
    _check_courses(rows, cat_idx, where, errors, warnings, prefs)
    _check_requirements(rows, reqs, where, errors)
    return errors, warnings


def report(errors, warnings) -> str:
    lines = []
    for e in errors:
        lines.append(f"ERROR   {e}")
    for w in warnings:
        lines.append(f"warning {w}")
    if not lines:
        lines.append("OK — no errors, no warnings")
    return "\n".join(lines)
