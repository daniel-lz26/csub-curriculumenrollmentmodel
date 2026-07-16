"""Counselor chat loop: natural-language constraints -> edited JSON artifact.

Two scopes:
  cohort  — edits the whole cohort_schedule_set ("commuters: make everything
            morning-heavy", "no instructor at that slot, move it", "you're
            missing the FYS requirement").
  student — edits one student's schedule (starts as a copy of a block, then
            deviates per that student's preferences).

Protocol: the model gets the artifact + the real alternative sections for
every course in play, and must reply with a short rationale followed by the
FULL updated artifact in a ```json fence. The deterministic validator then
checks the result; on hard errors the violations are sent back for repair
(up to 3 rounds). Nothing invalid is ever saved.
"""
import copy
import json
import os
import re
from datetime import datetime, timezone

from . import config
from .catalog import Catalog, load_catalog
from .llm import LLM
from .validator import validate_cohort, validate_student, report

JSON_FENCE = re.compile(r"```json\s*(.*?)```", re.DOTALL)
MAX_REPAIRS = 3


# ---- context building -------------------------------------------------------

def _alternatives(cat: Catalog, major: str):
    """Real sections for every course that can satisfy each term-1
    requirement — the model's only allowed building blocks."""
    out = []
    for req in cat.requirements_for(major):
        for course in req.course_options:
            for s in cat.sections_for(course):
                out.append({
                    "requirement": req.name, "course": course,
                    "class_nbr": s["class_nbr"], "section": s["section"],
                    "title": s["title"], "units": s["units"],
                    "days": s["days"], "start": s["start"], "end": s["end"],
                    "mode": s["mode"], "seats_open": s["seats_open"],
                    "waitlist": s["waitlist"],
                })
    return out


def _system_prompt(scope: str, artifact: dict, cat: Catalog) -> str:
    major = artifact["major"] if scope == "cohort" else artifact["_parent"]["major"]
    alts = _alternatives(cat, major)
    return f"""You are a schedule-editing engine for CSUB freshman block registration.
A counselor gives you constraints in plain English; you edit the JSON schedule
artifact to satisfy them. This is decision support — the counselor approves
everything, you never invent data.

HARD RULES
1. Only use sections from the ALTERNATIVE SECTIONS list below. Copy class_nbr,
   section, units, days, start, end, mode exactly. Never invent or alter them.
2. Every roadmap requirement with course options must stay covered in every
   block/schedule (swap sections or courses, don't drop requirements).
3. No time conflicts (overlapping times on a shared day).
4. Keep the JSON schema exactly as given. Update total_units when courses
   change. Append one change_log entry: {{"at": "<iso>", "actor":
   "counselor_chat", "summary": "<what changed and why>"}}.
5. Bakersfield context: most students are commuters. Unless told otherwise,
   prefer in-person classes between 10:00 and 15:00, packed into few campus
   days.

RESPONSE FORMAT — always:
- 2-6 sentences: what you changed and why (counselor-readable, mention
  specific sections/times).
- Then the FULL updated artifact in a ```json fence. If the request needs no
  JSON change (a pure question), answer it and return the artifact unchanged.

SCOPE: {"the whole cohort set — edits apply to blocks for entire cohorts of students"
        if scope == "cohort" else
        "one student's individual schedule — edit only this student's courses; record intent in 'deviations'"}

TERM: {cat.term} (sections snapshot {cat.snapshot_date})

ALTERNATIVE SECTIONS (the complete universe you may use):
{json.dumps(alts, separators=(",", ":"))}
"""


# ---- artifact IO ------------------------------------------------------------

def _save(path: str, artifact: dict):
    with open(path, "w") as f:
        json.dump(artifact, f, indent=1)
    hist = os.path.splitext(path)[0] + ".history.jsonl"
    with open(hist, "a") as f:
        f.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(
            timespec="seconds"), "artifact": artifact}) + "\n")


def new_student_artifact(parent: dict, parent_path: str, student_id: str,
                         block_id: str | None = None) -> dict:
    blocks = parent["blocks"]
    block = next((b for b in blocks if b["block_id"] == block_id), blocks[0])
    return {
        "artifact_type": "student_schedule",
        "schema_version": 1,
        "student_id": student_id,
        "parent_artifact": os.path.basename(parent_path),
        "major": parent["major"],
        "term": parent["term"],
        "base_block": block["block_id"],
        "preferences": {},
        "courses": copy.deepcopy(block["courses"]),
        "deviations": [],
        "change_log": [{
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "actor": "generator",
            "summary": f"Initialized from cohort block {block['block_id']} "
                       f"({block['label']})",
        }],
    }


def student_path(parent_path: str, student_id: str) -> str:
    d = os.path.splitext(parent_path)[0] + ".students"
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{student_id}.json")


# ---- the loop ---------------------------------------------------------------

def _validate(scope, artifact, parent, cat):
    if scope == "cohort":
        return validate_cohort(artifact, cat)
    return validate_student(artifact, parent, cat)


def process_turn(llm: LLM, system: str, history: list, user_text: str,
                 scope: str, parent: dict | None, cat: Catalog):
    """One counselor turn -> (rationale, new_artifact | None, transcript)."""
    history.append({"role": "user", "content": user_text})
    for attempt in range(1 + MAX_REPAIRS):
        reply = llm.chat(system, history)
        history.append({"role": "assistant", "content": reply})
        m = JSON_FENCE.search(reply)
        rationale = reply[:m.start()].strip() if m else reply.strip()
        if not m:
            return rationale, None, history  # pure Q&A turn
        try:
            artifact = json.loads(m.group(1))
        except json.JSONDecodeError as e:
            feedback = f"Your JSON did not parse: {e}. Resend the full corrected artifact."
        else:
            if scope == "student":
                artifact.pop("_parent", None)
            errors, warnings = _validate(scope, artifact, parent, cat)
            if not errors:
                if warnings:
                    rationale += "\n\n[validator warnings]\n" + "\n".join(
                        f"  - {w}" for w in warnings)
                return rationale, artifact, history
            feedback = ("The validator rejected your edit. Fix these and "
                        "resend the FULL artifact:\n" +
                        "\n".join(f"- {e}" for e in errors))
        history.append({"role": "user", "content": feedback})
    return (f"Could not produce a valid edit after {MAX_REPAIRS} repair "
            f"attempts. Last validator output:\n{feedback}", None, history)


def run_chat(artifact_path: str, student_id: str | None = None,
             block_id: str | None = None):
    with open(artifact_path) as f:
        parent = json.load(f)
    year = int(parent["term"].split()[-1])
    term = parent["term"].split()[0]
    cat = load_catalog(year, term)
    llm = LLM()

    if student_id:
        scope = "student"
        path = student_path(artifact_path, student_id)
        if os.path.exists(path):
            with open(path) as f:
                artifact = json.load(f)
        else:
            artifact = new_student_artifact(parent, artifact_path,
                                            student_id, block_id)
            _save(path, artifact)
            print(f"Created {path} from block {artifact['base_block']}.")
    else:
        scope, path, artifact = "cohort", artifact_path, parent

    art_for_prompt = dict(artifact)
    if scope == "student":
        art_for_prompt["_parent"] = {"major": parent["major"]}
    system = _system_prompt(scope, art_for_prompt, cat)
    history = [{"role": "user", "content":
                "Current artifact:\n```json\n" +
                json.dumps(artifact, indent=1) + "\n```"},
               {"role": "assistant", "content":
                "Loaded. Tell me the constraint or question."}]

    who = f"student {student_id}" if student_id else f"cohort set ({parent['major']})"
    print(f"\nChatting about {who} — {parent['term']} | model: {llm.model} "
          f"({llm.provider})\nType a constraint, 'show' for a summary, "
          f"'quit' to exit.\n")
    while True:
        try:
            text = input("counselor> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text.lower() in ("quit", "exit", "q"):
            break
        if text.lower() == "show":
            print(summarize(artifact))
            continue
        rationale, new_art, history = process_turn(
            llm, system, history, text, scope,
            parent if scope == "student" else None, cat)
        print("\n" + rationale + "\n")
        if new_art is not None:
            artifact = new_art
            _save(path, artifact)
            print(f"[saved {path}]")
            print(summarize(artifact))


def summarize(artifact: dict) -> str:
    lines = []
    if artifact.get("artifact_type") == "student_schedule":
        lines.append(f"-- {artifact['student_id']} (base block "
                     f"{artifact['base_block']}) --")
        for r in artifact["courses"]:
            days = ",".join(r["days"]) if r["days"] else "async"
            t = f"{r['start']}-{r['end']}" if r["start"] else "online"
            lines.append(f"  {r['course']:<11} #{r['class_nbr']} {days:<8} "
                         f"{t:<12} {r['units']}u  {r['title']}")
        return "\n".join(lines)
    for b in artifact.get("blocks", []):
        lines.append(f"-- block {b['block_id']}: {b['label']} "
                     f"({b['total_units']}u, cohort cap {b['cohort_capacity']}) --")
        for r in b["courses"]:
            days = ",".join(r["days"]) if r["days"] else "async"
            t = f"{r['start']}-{r['end']}" if r["start"] else "online"
            lines.append(f"  {r['course']:<11} #{r['class_nbr']} {days:<8} "
                         f"{t:<12} {r['units']}u  {r['title']}")
    return "\n".join(lines)
