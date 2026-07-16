# schedule_engine — CSUB freshman block-schedule engine

Turns real CSUB data into **4–8 JSON cohort schedule blocks** per major, then
lets a counselor reshape them (whole cohort or one student) through a chat
loop where Claude edits the JSON and a deterministic validator guarantees
every result is real, conflict-free, and requirement-complete.

## Data in
| Input | Source | Role |
|---|---|---|
| Section catalog (times, seats, waitlists, mode) | `E3E4_...csv` — latest daily snapshot for the term | the only sections the system may use |
| Term-1 degree roadmaps + GE areas | `BSBAcourse_catalog.xlsx` | what a freshman block must cover |
| Real freshman first-semester schedules | `freshman_dataset/freshman_schedules.csv` | popularity & co-occurrence weights |

## Pipeline
```bash
python3 -m schedule_engine extract                       # 134MB E3E4 -> compact sections JSON (once per term)
python3 -m schedule_engine majors                        # list majors with roadmaps
python3 -m schedule_engine generate --major "BA - Marketing"   # -> artifacts/ba_marketing.json
python3 -m schedule_engine validate artifacts/ba_marketing.json
python3 -m schedule_engine chat artifacts/ba_marketing.json                 # cohort-level chat
python3 -m schedule_engine chat artifacts/ba_marketing.json --student S001  # one student's schedule
```

## How generation works
Each block picks one real section per roadmap requirement via beam search:
no time conflicts, scored for **commuter fit** (default: in-person classes
inside 10:00–15:00, few campus days, small gaps), freshman popularity,
co-occurrence, and seat health. Ten "flavors" (morning core, TTh-compact,
Fridays-free, online-lean, …) diversify the set, and a shared seat ledger
decrements capacity as each cohort is placed so blocks don't oversubscribe
the same sections. Full-at-snapshot sections become per-block `advisories`
("needs reserved seats") instead of silent failures.

Preferences are plain JSON (`--prefs my_prefs.json` overrides
`config.DEFAULT_PREFERENCES`) — window, days off, mode lean, cohort size,
number of blocks.

## The chat loop (the "movable AI artifact")
The artifact JSON *is* the interface. Each counselor turn:

1. Claude gets the artifact + the complete list of real alternative sections
   for every requirement (its only allowed building blocks).
2. It replies with a short rationale + the FULL updated artifact JSON.
3. `validator.py` checks it: sections must exist in the catalog with exact
   fields, no time conflicts, every requirement still covered, units honest.
4. Hard errors are sent back for repair (max 3 rounds). **Nothing invalid is
   ever saved.** Soft issues (outside window, full section) surface as
   warnings for the counselor.
5. Valid edits are saved with a `change_log` entry; every version is appended
   to `<artifact>.history.jsonl`.

Example turns it's built for:
- "Most of our students commute — make every block morning-heavy."
- "No instructor is available for MATH 2200 at 1pm — move those sections."
- "Block C is missing the oral-communication requirement." (the validator
  catches this class of error even if the counselor doesn't)
- `--student S001`: "She works afternoons, shift everything before noon."

Student schedules start as a copy of a cohort block and deviate individually
(`artifacts/<name>.students/S001.json`), validated against the same roadmap.

## LLM credentials
Put `ANTHROPIC_API_KEY=...` in a `.env` at the repo root (preferred), or have
AWS credentials with `bedrock:InvokeModel` (auto-fallback, `us-west-2`).
Model override: `CLAUDE_MODEL` / `BEDROCK_MODEL` env vars.

## Design stance
Decision support, not automated decision-making: the LLM can only recombine
real sections, the validator is deterministic, advisories and warnings go to
a human, and counselors approve every save.
