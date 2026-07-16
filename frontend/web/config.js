// Frontend configuration — the only file most people need to touch.

// ---- Schedule blocks (schedule_engine artifacts) ---------------------------
// Each entry is a generated artifact from `python3 -m schedule_engine
// generate --major "..."` (see ../../schedule_engine/README.md) — a real,
// conflict-checked set of cohort schedule blocks for that major, Fall 2026.
// This is what drives the major picker, the block/calendar view, and the
// comparison view. To add a major: generate its artifact, copy the JSON into
// data/artifacts/, and add a line here.
const ARTIFACTS_BASE_PATH = "./data/artifacts/";
// { file, label } — label is what shows in the Major picker. Filenames alone
// aren't user-friendly, so every entry needs a human label; the picker won't
// fall back to the raw filename.
const MAJOR_ARTIFACTS = [
  { file: "ba_general_business.json", label: "General Business" },
  { file: "ba_accounting.json", label: "Accounting" },
  { file: "ba_economics.json", label: "Economics" },
  { file: "ba_entrepreneurship.json", label: "Entrepreneurship" },
  { file: "ba_finance.json", label: "Finance" },
  { file: "ba_health_care_management.json", label: "Health Care Management" },
  { file: "ba_human_resource_management.json", label: "Human Resource Management" },
  { file: "ba_management.json", label: "Management" },
  { file: "ba_marketing.json", label: "Marketing" },
  { file: "ba_public_administration.json", label: "Public Administration" },
  { file: "ba_supply_chain_logistics.json", label: "Supply Chain Logistics" },
  { file: "agricultural_business.json", label: "Agricultural Business" },
];
// No live endpoint serves these artifacts yet (schedule_engine has no
// Lambda/API Gateway wiring — it's a CLI pipeline that writes local JSON).
// Regenerate + re-copy into data/artifacts/ to refresh; there's nothing to
// point at a deployed URL for here yet.

// ---- Legacy Q&A endpoint (mining/co_occurrence.py + bedrock/client.py) ----
// The free-text "Ask a question" box still calls the older recommendation
// API (api/handlers/ask.py), which answers over the pooled, all-concentration
// mining dataset — not the specific major/block currently on screen. Leave
// API_BASE_URL "" to run it in offline/demo mode (Q&A disabled, since there's
// no Bedrock call to make without a deployed API); set it to the "ApiUrl"
// output from `infra/deploy.sh` to enable live Q&A.
const API_BASE_URL = "";
