"""CLI entry point.

  python3 -m schedule_engine extract  [--year 2026] [--term Fall]
  python3 -m schedule_engine majors
  python3 -m schedule_engine generate --major "BA - Marketing" [-o out.json]
                                      [--prefs prefs.json] [--num-blocks 8]
  python3 -m schedule_engine validate artifacts/xyz.json
  python3 -m schedule_engine chat     artifacts/xyz.json
                                      [--student S001 [--block B]]
"""
import argparse
import json
import os
import re
import sys

from . import config


def main(argv=None):
    p = argparse.ArgumentParser(prog="schedule_engine")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("extract", help="E3E4 CSV -> compact sections JSON")
    e.add_argument("--year", type=int, default=2026)
    e.add_argument("--term", default="Fall")

    sub.add_parser("majors", help="list majors with roadmaps")

    g = sub.add_parser("generate", help="build cohort blocks artifact")
    g.add_argument("--major", required=True)
    g.add_argument("--year", type=int, default=2026)
    g.add_argument("--term", default="Fall")
    g.add_argument("--prefs", help="JSON file overriding default preferences")
    g.add_argument("--num-blocks", type=int)
    g.add_argument("-o", "--out")

    v = sub.add_parser("validate", help="validate an artifact")
    v.add_argument("artifact")

    c = sub.add_parser("chat", help="counselor chat over an artifact")
    c.add_argument("artifact")
    c.add_argument("--student", help="student id -> individual-schedule mode")
    c.add_argument("--block", help="base block for a new student schedule")

    a = p.parse_args(argv)

    if a.cmd == "extract":
        from .extract_sections import extract
        extract(a.year, a.term)

    elif a.cmd == "majors":
        from .catalog import load_catalog
        cat = load_catalog()
        for m in sorted(cat.roadmaps):
            n = sum(1 for r in cat.roadmaps[m] if int(r["term_num"]) == 1)
            print(f"{m}  ({n} term-1 requirements)")

    elif a.cmd == "generate":
        from .catalog import load_catalog
        from .generator import generate, save_artifact
        from .validator import validate_cohort, report
        prefs = {}
        if a.prefs:
            with open(a.prefs) as f:
                prefs = json.load(f)
        if a.num_blocks:
            prefs["num_blocks"] = a.num_blocks
        cat = load_catalog(a.year, a.term)
        artifact = generate(a.major, a.year, a.term, prefs, cat)
        slug = re.sub(r"[^a-z0-9]+", "_", a.major.lower()).strip("_")
        out = a.out or os.path.join(config.ARTIFACT_DIR, f"{slug}.json")
        save_artifact(artifact, out)
        errors, warnings = validate_cohort(artifact, cat)
        print(f"{len(artifact['blocks'])} blocks -> {out}")
        print(report(errors, warnings))
        from .chat import summarize
        print()
        print(summarize(artifact))
        if errors:
            sys.exit(1)

    elif a.cmd == "validate":
        from .catalog import load_catalog
        from .validator import validate_cohort, validate_student, report
        with open(a.artifact) as f:
            artifact = json.load(f)
        year = int(artifact["term"].split()[-1])
        cat = load_catalog(year, artifact["term"].split()[0])
        if artifact.get("artifact_type") == "student_schedule":
            parent_path = os.path.join(
                os.path.dirname(os.path.dirname(a.artifact)),
                artifact["parent_artifact"])
            with open(parent_path) as f:
                parent = json.load(f)
            errors, warnings = validate_student(artifact, parent, cat)
        else:
            errors, warnings = validate_cohort(artifact, cat)
        print(report(errors, warnings))
        if errors:
            sys.exit(1)

    elif a.cmd == "chat":
        from .chat import run_chat
        run_chat(a.artifact, a.student, a.block)


if __name__ == "__main__":
    main()
