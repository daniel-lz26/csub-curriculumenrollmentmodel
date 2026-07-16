"""Extract a compact section catalog from the 134MB E3E4 daily-snapshot CSV.

Takes the LATEST snapshot for the requested term/year, keeps UGRD sections,
parses meeting days/times, and writes schedule_engine/data/sections_<term>_<year>.json.
Run once per term; everything downstream reads the JSON.
"""
import csv
import json
import os
import re

from . import config

DAY_TOKEN = re.compile(r"(Th|Sa|Su|M|T|W|F)")
VALID_DAYS = ["M", "T", "W", "Th", "F", "Sa", "Su"]


def _date_key(d: str):
    m, dd, y = d.split("/")
    return (int(y), int(m), int(dd))


def parse_days(raw: str):
    """'M,W' -> ['M','W']; 'No Patterns' -> []; complex multi-pattern strings
    are parsed best-effort (all day tokens found) and flagged."""
    raw = (raw or "").strip()
    if not raw or raw == "No Patterns":
        return [], False
    if "(" in raw:  # rare multi-pattern rows with embedded facility text
        toks = DAY_TOKEN.findall(raw.split("(")[0] + " " + raw)
        days = [d for d in VALID_DAYS if d in toks]
        return days, True
    toks = DAY_TOKEN.findall(raw)
    return [d for d in VALID_DAYS if d in toks], False


def _hhmm(t: str):
    """'09:00:00' -> '09:00'; midnight (placeholder for async) -> None."""
    t = (t or "").strip()
    if not t or t.startswith("00:00"):
        return None
    return t[:5]


def extract(year: int = 2026, term: str = "Fall", careers=("UGRD",)) -> str:
    latest = None
    with open(config.E3E4_CSV, newline="") as f:
        for row in csv.DictReader(f):
            if row["YEAR"] == str(year) and row["TERM"] == term:
                if latest is None or _date_key(row["SNAPSHOT_DATE"]) > _date_key(latest):
                    latest = row["SNAPSHOT_DATE"]
    if latest is None:
        raise SystemExit(f"No rows for {term} {year} in E3E4 CSV")

    sections = []
    with open(config.E3E4_CSV, newline="") as f:
        for row in csv.DictReader(f):
            if (row["YEAR"] != str(year) or row["TERM"] != term
                    or row["SNAPSHOT_DATE"] != latest
                    or row["ACAD_CAREER_CLASS_TBL"] not in careers):
                continue
            days, complex_pat = parse_days(row["MEETING_DAY"])
            cap = int(float(row["SUM_CAP_ENRL"] or 0))
            enrolled = int(float(row["SUM_TOT_ENRL"] or 0))
            sections.append({
                "class_nbr": row["CLASS_NBR"],
                "subject": row["SUBJECT"].strip(),
                "catalog_nbr": row["CATALOG_NBR"].strip(),
                "course": f'{row["SUBJECT"].strip()} {row["CATALOG_NBR"].strip()}',
                "section": row["CLASS_SECTION"].strip(),
                "title": row["DESCR"].strip(),
                "units": float(row["CSU_APDB_CMP_UNITS"] or 0),
                "days": days,
                "start": _hhmm(row["MEETING_TIME_START"]),
                "end": _hhmm(row["MEETING_TIME_END"]),
                "pattern_complex": complex_pat,
                "mode": row["instruction_mode_descr"].strip(),
                "capacity": cap,
                "enrolled": enrolled,
                "seats_open": max(cap - enrolled, 0),
                "waitlist": int(float(row["SUM_WAIT_TOT"] or 0)),
            })

    out = {
        "term": f"{term} {year}",
        "snapshot_date": latest,
        "source": os.path.basename(config.E3E4_CSV),
        "careers": list(careers),
        "sections": sections,
    }
    os.makedirs(config.DATA_DIR, exist_ok=True)
    path = config.sections_json_path(year, term)
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    print(f"{term} {year}: snapshot {latest}, {len(sections)} sections -> {path}")
    return path


if __name__ == "__main__":
    extract()
