"""Generate 5-10 diverse cohort schedule blocks for a major as a JSON artifact.

For each "flavor" (morning core, TTh-compact, Fridays-free, ...) we run a
beam search that picks one real section per roadmap requirement, prunes time
conflicts, and scores against the preference profile. A shared seat ledger
decrements capacity as each cohort block is placed, so ten cohorts of 25
don't all get assigned the same ENGL section.
"""
import copy
import json
import os
from datetime import datetime, timezone

from . import config
from .catalog import Catalog, load_catalog, to_minutes

BEAM_WIDTH = 250


# ---- scoring ---------------------------------------------------------------

def _window_fit(sec, window, mode_pref):
    """Fraction of meeting time inside the preferred window. Async/online
    sections are window-neutral (good for commuters but not a f2f slot)."""
    if not sec["days"] or not sec["start"] or not sec["end"]:
        return 0.85 if mode_pref != "in_person_lean" else 0.6
    lo, hi = to_minutes(window[0]), to_minutes(window[1])
    s, e = to_minutes(sec["start"]), to_minutes(sec["end"])
    if e <= s:
        return 0.5
    overlap = max(0, min(e, hi) - max(s, lo))
    return overlap / (e - s)


def _seat_health(sec, ledger):
    cap = sec["capacity"] or 1
    open_now = ledger.get(sec["class_nbr"], sec["seats_open"])
    health = max(open_now, 0) / cap
    if sec["waitlist"] > 0:
        health *= 0.5
    return health


def _mode_fit(sec, mode_pref):
    online = not sec["days"]
    f2f = sec["mode"] == "Face to Face"
    if mode_pref == "in_person_lean":
        return 1.0 if f2f else (0.6 if online else 0.8)
    if mode_pref == "online_lean":
        return 1.0 if online else 0.7
    return 1.0


def score_section(sec, cat: Catalog, prefs, weights, ledger):
    w = dict(config.BASE_WEIGHTS)
    window = weights.get("window",
                         (prefs["preferred_window"]["start"],
                          prefs["preferred_window"]["end"]))
    mode_pref = weights.get("mode", prefs["mode_preference"])
    if "popularity" in weights:
        w["popularity"] = weights["popularity"]
    if "seat_health" in weights:
        w["seat_health"] = weights["seat_health"]

    s = (w["window_fit"] * _window_fit(sec, window, mode_pref)
         + w["popularity"] * cat.popularity_score(sec["course"])
         + w["seat_health"] * _seat_health(sec, ledger)
         + w["mode_fit"] * _mode_fit(sec, mode_pref))

    days_off = set(weights.get("days_off", prefs["preferred_days_off"]))
    if days_off and set(sec["days"]) & days_off:
        s -= 2.0
    day_pref = weights.get("day_pref")
    if day_pref and sec["days"] and not set(sec["days"]) <= set(day_pref):
        s -= 1.0
    if prefs["avoid_waitlisted_sections"] and ledger.get(
            sec["class_nbr"], sec["seats_open"]) <= 0:
        s -= 5.0
    return s


def conflicts(a, b):
    """True if two sections overlap in time on a shared day."""
    if not (a["days"] and b["days"] and a["start"] and b["start"]):
        return False
    if not set(a["days"]) & set(b["days"]):
        return False
    return (to_minutes(a["start"]) < to_minutes(b["end"])
            and to_minutes(b["start"]) < to_minutes(a["end"]))


def block_bonus(sections, cat: Catalog, prefs):
    """Block-level shaping: commuter compactness + real co-occurrence."""
    timed = [s for s in sections if s["days"] and s["start"]]
    days = {}
    for s in timed:
        for d in s["days"]:
            days.setdefault(d, []).append((to_minutes(s["start"]),
                                           to_minutes(s["end"])))
    gap_min = 0
    for meetings in days.values():
        meetings.sort()
        for (s1, e1), (s2, _) in zip(meetings, meetings[1:]):
            gap_min += max(0, s2 - e1)
    compact = 0.0
    if prefs["minimize_campus_days"]:
        compact -= 0.5 * len(days)          # each extra campus day costs
    compact -= gap_min / 240.0              # 4h of daily gaps ~ -1

    co = 0.0
    if cat.n_freshmen:
        courses = [s["course"] for s in sections]
        for i, a in enumerate(courses):
            for b in courses[i + 1:]:
                co += cat.cooccur.get(frozenset((a, b)), 0) / cat.n_freshmen
    return config.BASE_WEIGHTS["compactness"] * compact + co


# ---- search ----------------------------------------------------------------

def best_blocks_for_flavor(cat, reqs, prefs, weights, ledger, top_n=3):
    """Beam search: requirements ordered fewest-options-first, one section
    per requirement, no time conflicts. Returns top_n complete blocks."""
    active = [r for r in reqs if r.course_options]
    active.sort(key=lambda r: sum(len(cat.sections_for(c))
                                  for c in r.course_options))
    beams = [([], 0.0)]
    for req in active:
        cands = []
        for course in req.course_options:
            for sec in cat.sections_for(course):
                cands.append((sec, score_section(sec, cat, prefs, weights, ledger)))
        cands.sort(key=lambda t: -t[1])
        nxt = []
        for chosen, score in beams:
            used = {s["course"] for s in chosen}
            for sec, s_score in cands[:60]:
                if sec["course"] in used:
                    continue
                if any(conflicts(sec, c) for c in chosen):
                    continue
                nxt.append((chosen + [sec], score + s_score))
        if not nxt:   # requirement unsatisfiable under constraints; skip it
            continue
        nxt.sort(key=lambda t: -t[1])
        beams = nxt[:BEAM_WIDTH]

    scored = [(sections, score + block_bonus(sections, cat, prefs))
              for sections, score in beams]
    scored.sort(key=lambda t: -t[1])
    return scored[:top_n]


def _claim_seats(sections, ledger, target):
    """Cohort size = seats jointly available across the block's sections.
    Sections that are already full at the snapshot don't zero the block —
    block registration typically reserves seats before open enrollment —
    they come back as advisories for the counselor instead.
    Returns (size, advisories)."""
    advisories = []
    open_counts = []
    for s in sections:
        remaining = ledger.get(s["class_nbr"], s["seats_open"])
        if s["seats_open"] <= 0:
            advisories.append(
                f"{s['course']} #{s['class_nbr']} is full at snapshot "
                f"(waitlist {s['waitlist']}) — needs reserved/added seats "
                f"for this cohort")
        else:
            open_counts.append(remaining)
    size = max(min(open_counts + [target]), 0) if open_counts else target
    for s in sections:
        ledger[s["class_nbr"]] = ledger.get(s["class_nbr"], s["seats_open"]) - size
    return size, advisories


def _course_row(sec, req, cat: Catalog, ledger):
    return {
        "requirement": req.name,
        "req_type": req.req_type,
        "course": sec["course"],
        "title": sec["title"],
        "class_nbr": sec["class_nbr"],
        "section": sec["section"],
        "units": sec["units"],
        "days": sec["days"],
        "start": sec["start"],
        "end": sec["end"],
        "mode": sec["mode"],
        "seats_open_at_generation": ledger.get(sec["class_nbr"], sec["seats_open"]),
        "waitlist": sec["waitlist"],
        "freshman_popularity": (
            f"{cat.popularity.get(sec['course'], 0)}/{cat.n_freshmen} mined freshmen"
            if cat.popularity.get(sec["course"]) else None),
    }


def generate(major: str, year: int = 2026, term: str = "Fall",
             prefs: dict | None = None, cat: Catalog | None = None) -> dict:
    prefs = {**config.DEFAULT_PREFERENCES, **(prefs or {})}
    cat = cat or load_catalog(year, term)
    reqs = cat.requirements_for(major)
    req_by_course = {}
    for r in reqs:
        for c in r.course_options:
            req_by_course.setdefault(c, r)

    ledger = {}       # class_nbr -> remaining seats (shared across blocks)
    blocks, seen = [], set()
    for flavor in config.BLOCK_FLAVORS:
        if len(blocks) >= prefs["num_blocks"]:
            break
        for sections, score in best_blocks_for_flavor(
                cat, reqs, prefs, flavor["weights"], ledger, top_n=5):
            sig = frozenset(s["class_nbr"] for s in sections)
            # require a genuinely different block: >=2 section changes
            if any(len(sig ^ old) < 4 for old in seen):
                continue
            size, advisories = _claim_seats(sections, ledger,
                                            prefs["cohort_size_target"])
            if size < 5:  # not enough shared seats left to be a cohort
                continue
            seen.add(sig)
            rows = [_course_row(s, req_by_course[s["course"]], cat, ledger)
                    for s in sections]
            rows.sort(key=lambda r: (r["days"] == [],
                                     r["start"] or "99", r["course"]))
            blocks.append({
                "block_id": chr(ord("A") + len(blocks)),
                "label": flavor["label"],
                "cohort_capacity": size,
                "total_units": round(sum(r["units"] for r in rows), 1),
                "score": round(score, 2),
                "advisories": advisories,
                "courses": rows,
            })
            break

    unmet = [r.name for r in reqs if not r.course_options]
    artifact = {
        "artifact_type": "cohort_schedule_set",
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "term": cat.term,
        "sections_snapshot": cat.snapshot_date,
        "major": major,
        "preferences": prefs,
        "roadmap_term1": [
            {"requirement": r.name, "req_type": r.req_type, "units": r.units,
             "course_options": r.course_options,
             "note": "no offered sections found" if not r.course_options else None}
            for r in reqs],
        "notes": ([f"Requirements with no matching Fall sections (left to "
                   f"counselor): {unmet}"] if unmet else []),
        "blocks": blocks,
        "change_log": [{
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "actor": "generator",
            "summary": f"Generated {len(blocks)} blocks for {major} "
                       f"({cat.term}, snapshot {cat.snapshot_date})",
        }],
    }
    return artifact


def save_artifact(artifact: dict, path: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(artifact, f, indent=1)
    return path
