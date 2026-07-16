"""Paths and default preferences for the schedule engine."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

DATA_DIR = os.path.join(HERE, "data")
ARTIFACT_DIR = os.path.join(REPO, "artifacts")

E3E4_CSV = os.path.join(
    REPO, "dxhub-camp-2026-csub-curriculum-enrollment-model", "data",
    "E3E4_Course Offering and Waitlist_daily snapshot for Fall 2025 and 2026.csv")
CATALOG_XLSX = os.path.join(
    REPO, "dxhub-camp-2026-csub-curriculum-enrollment-model", "data",
    "BSBAcourse_catalog.xlsx")
FRESHMAN_SCHEDULES_CSV = os.path.join(REPO, "freshman_dataset", "freshman_schedules.csv")

def sections_json_path(year: int, term: str) -> str:
    return os.path.join(DATA_DIR, f"sections_{term.lower()}_{year}.json")

# CSUB is heavily commuter: default to in-person classes packed into a
# late-morning/early-afternoon window on as few campus days as possible.
DEFAULT_PREFERENCES = {
    "profile": "commuter_morning",
    "preferred_window": {"start": "10:00", "end": "15:00"},
    "preferred_days_off": [],          # e.g. ["F"] to keep Fridays free
    "mode_preference": "in_person_lean",  # in_person_lean | online_lean | no_preference
    "minimize_campus_days": True,
    "avoid_waitlisted_sections": True,
    "cohort_size_target": 25,
    "num_blocks": 8,                   # 5-10 cohort blocks per major
}

# Flavor profiles used to diversify the generated blocks. Each overrides
# scoring weights so counselors see genuinely different shapes, not eight
# near-clones of the same schedule.
BLOCK_FLAVORS = [
    {"label": "Morning core (10-3)",       "weights": {}},
    {"label": "MW-compact commuter",       "weights": {"day_pref": ["M", "W"]}},
    {"label": "TTh-compact commuter",      "weights": {"day_pref": ["T", "Th"]}},
    {"label": "Fridays-free",              "weights": {"days_off": ["F"]}},
    {"label": "Early start (9-1)",         "weights": {"window": ("09:00", "13:00")}},
    {"label": "Midday (11-4)",             "weights": {"window": ("11:00", "16:00")}},
    {"label": "Online-lean flex",          "weights": {"mode": "online_lean"}},
    {"label": "Most popular pairings",     "weights": {"popularity": 2.5}},
    {"label": "Afternoon (12-5)",          "weights": {"window": ("12:00", "17:00")}},
    {"label": "Lightest waitlist risk",    "weights": {"seat_health": 2.5}},
]

# Base scoring weights (see generator.score_section / score_block).
BASE_WEIGHTS = {
    "window_fit": 3.0,     # meeting minutes inside the preferred window
    "popularity": 1.0,     # how often real freshmen took the course
    "seat_health": 1.0,    # open seats remaining / capacity
    "compactness": 1.5,    # few campus days, small gaps between classes
    "mode_fit": 0.8,       # matches mode_preference
}

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
BEDROCK_MODEL = os.environ.get(
    "BEDROCK_MODEL", "us.anthropic.claude-3-5-haiku-20241022-v1:0")
BEDROCK_REGION = os.environ.get("AWS_REGION", "us-west-2")
