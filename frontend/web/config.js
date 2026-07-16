// Frontend configuration — the only file most people need to touch.
//
// API_BASE_URL: the "ApiUrl" output from `infra/deploy.sh` (SAM), e.g.
//   "https://abc123.execute-api.us-west-2.amazonaws.com/Prod"
// Leave it "" to run in offline/demo mode: the app reads the bundled
// snapshot at ./data/recommendation.json instead of calling AWS, and the
// Q&A box is disabled (there's no Bedrock call to make without an API).
const API_BASE_URL = "";

// BSBA concentrations shown in the "Concentration" picker in the masthead.
// Add/remove/rename freely — this list is presentation only. Per
// CHANGES.md, freshman-year course-taking is nearly identical across all
// 10 concentrations, so the mining layer pools them and does not compute
// separate data per concentration; changing this selector changes the
// page's labels only, not which courses/rationale are shown. If the
// mining layer is ever extended to be concentration-aware, this is the
// list to wire a real `?concentration=` query param to.
const BSBA_CONCENTRATIONS = [
  "General Business",
  "Accounting",
  "Economics",
  "Entrepreneurship",
  "Finance",
  "Health Care Management",
  "Human Resource Management",
  "Management",
  "Marketing",
  "Supply Chain Logistics",
];

// Path to the offline fallback snapshot (a copy of
// data/output/recommendation.json), used whenever API_BASE_URL is unset or
// a live fetch fails. Regenerate it with `python -m mining.co_occurrence`
// and copy the output here to refresh the demo data.
const LOCAL_SNAPSHOT_PATH = "./data/recommendation.json";
