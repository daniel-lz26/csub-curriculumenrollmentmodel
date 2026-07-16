"use strict";

/* ============================================================
   Constants
   ============================================================ */
const TERM_OPTIONS = ["Fall", "Spring"];
const DAY_COLUMNS = [
  { label: "Mon", key: "Mon" },
  { label: "Tue", key: "Tue" },
  { label: "Wed", key: "Wed" },
  { label: "Thu", key: "Thu" },
  { label: "Fri", key: "Fri" },
  { label: "Sat", key: "Sat" },
  { label: "Sun", key: "Sun" },
];
const TOKEN_TO_DAY = { M: "Mon", T: "Tue", W: "Wed", Th: "Thu", F: "Fri", Sa: "Sat", Su: "Sun" };
const KNOWN_TOKENS = ["Th", "Sa", "Su", "M", "T", "W", "F"]; // longest-match-first order

const CAL_START_MIN = 7 * 60;   // 7:00am
const CAL_END_MIN = 21 * 60;    // 9:00pm
const CAL_RANGE_MIN = CAL_END_MIN - CAL_START_MIN;

const REQ_TAG_CLASS = { "Major": "major", "General Education": "gened", "Major / Gen Ed": "gem" };
const CAL_BLOCK_CLASS = { "Major": "req-major", "General Education": "req-gened", "Major / Gen Ed": "req-gem" };

/* ============================================================
   State
   ============================================================ */
const state = {
  mode: API_BASE_URL ? "live" : "demo", // "live" | "demo" | "offline-fallback"
  localSnapshot: null,   // full mine() JSON, loaded lazily
  term: TERM_OPTIONS[0],
  view: null,            // normalized view model for the current term (see fetchTerm)
  activeScheduleIndex: 0,
  qaThread: [],
  qaBusy: false,
};

/* ============================================================
   DOM refs
   ============================================================ */
const el = {
  statusRibbon: document.getElementById("statusRibbon"),
  concentrationSelect: document.getElementById("concentrationSelect"),
  termSelect: document.getElementById("termSelect"),
  cohortChip: document.getElementById("cohortChip"),
  pageTitle: document.getElementById("pageTitle"),
  scopeRow: document.getElementById("scopeRow"),
  assumptionsPanel: document.getElementById("assumptionsPanel"),
  assumptionsList: document.getElementById("assumptionsList"),
  stateBannerHost: document.getElementById("stateBannerHost"),
  topPickSection: document.getElementById("topPickSection"),
  topPickTitle: document.getElementById("topPickTitle"),
  topPickSupport: document.getElementById("topPickSupport"),
  topPickBody: document.getElementById("topPickBody"),
  calendarWrap: document.getElementById("calendarWrap"),
  calendarSourceLabel: document.getElementById("calendarSourceLabel"),
  calendarGrid: document.getElementById("calendarGrid"),
  calendarLegend: document.getElementById("calendarLegend"),
  calendarUnplottable: document.getElementById("calendarUnplottable"),
  rationaleBox: document.getElementById("rationaleBox"),
  rationaleText: document.getElementById("rationaleText"),
  rationaleMeta: document.getElementById("rationaleMeta"),
  comparisonSection: document.getElementById("comparisonSection"),
  comparisonList: document.getElementById("comparisonList"),
  qaThread: document.getElementById("qaThread"),
  qaEmptyState: document.getElementById("qaEmptyState"),
  qaInput: document.getElementById("qaInput"),
  qaSubmit: document.getElementById("qaSubmit"),
  appFooter: document.getElementById("appFooter"),
};

/* ============================================================
   Day/time parsing
   ============================================================ */
function parseDayTokens(daysStr) {
  if (!daysStr) return [];
  const raw = daysStr.trim();
  if (raw.includes(",")) {
    return raw.split(",").map((s) => s.trim()).filter(Boolean);
  }
  const tokens = [];
  let i = 0;
  while (i < raw.length) {
    const hit = KNOWN_TOKENS.find((tok) => raw.startsWith(tok, i));
    if (!hit) { i += 1; continue; }
    tokens.push(hit);
    i += hit.length;
  }
  return tokens;
}

function timeToMinutes(hhmmss) {
  const [h, m] = hhmmss.split(":").map(Number);
  return h * 60 + m;
}

function formatTime12h(hhmmss) {
  const [hStr, mStr] = hhmmss.split(":");
  let h = Number(hStr);
  const m = Number(mStr);
  const ampm = h >= 12 ? "PM" : "AM";
  h = h % 12;
  if (h === 0) h = 12;
  return `${h}:${String(m).padStart(2, "0")}${ampm}`;
}

// A meeting_patterns entry is "plottable" if it has a clean start/end and
// day tokens we recognize. Async ("No Patterns") and free-text entries
// with an embedded caveat note (unparseable source rows) are not.
function plottableSlot(pattern) {
  if (!pattern || pattern.note || !pattern.start || !pattern.end) return false;
  const tokens = parseDayTokens(pattern.days);
  return tokens.length > 0 && tokens.every((t) => TOKEN_TO_DAY[t]);
}

function bestSlotFor(course) {
  const patterns = course.meeting_patterns || [];
  return patterns.find(plottableSlot) || null;
}

/* ============================================================
   Fetching
   ============================================================ */
async function loadLocalSnapshot() {
  if (state.localSnapshot) return state.localSnapshot;
  const resp = await fetch(LOCAL_SNAPSHOT_PATH);
  if (!resp.ok) throw new Error(`Local snapshot fetch failed: ${resp.status}`);
  state.localSnapshot = await resp.json();
  return state.localSnapshot;
}

function viewFromLocalSnapshot(snapshot, term, offline) {
  const termData = snapshot.terms[term] || { cohort_size: 0, course_frequency: [], candidate_schedules: [] };
  return {
    major: snapshot.major,
    class_year: snapshot.class_year,
    unit_target: snapshot.unit_target,
    assumptions: snapshot.assumptions,
    cohort_size: termData.cohort_size,
    candidate_schedules: termData.candidate_schedules,
    rationale: null,
    rationale_error: null,
    offline: !!offline,
  };
}

async function fetchTerm(term) {
  if (state.mode === "live") {
    try {
      const resp = await fetch(`${API_BASE_URL.replace(/\/$/, "")}/recommendation?term=${encodeURIComponent(term)}`);
      const body = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(body.error || `API returned ${resp.status}`);
      }
      return { ...body, offline: false, networkError: null };
    } catch (err) {
      // Can't reach the API at all (bad URL, CORS, stack not deployed,
      // network down) — fall back to the bundled snapshot so the chair
      // still sees course data, and say plainly that it's a connectivity
      // problem rather than "no data."
      const snapshot = await loadLocalSnapshot();
      const view = viewFromLocalSnapshot(snapshot, term, true);
      view.networkError = err.message;
      return view;
    }
  }
  const snapshot = await loadLocalSnapshot();
  return viewFromLocalSnapshot(snapshot, term, true);
}

/* ============================================================
   Rendering — masthead / status
   ============================================================ */
function renderStatusRibbon() {
  el.statusRibbon.classList.remove("mode-demo", "mode-live", "mode-error");
  if (state.mode === "live" && state.view && !state.view.networkError) {
    el.statusRibbon.classList.add("mode-live");
    el.statusRibbon.textContent = `LIVE — connected to ${API_BASE_URL}`;
  } else if (state.view && state.view.networkError) {
    el.statusRibbon.classList.add("mode-error");
    el.statusRibbon.textContent = `Can't reach the API (${state.view.networkError}) — showing the bundled local snapshot instead. Check config.js API_BASE_URL and that infra/deploy.sh has run.`;
  } else {
    el.statusRibbon.classList.add("mode-demo");
    el.statusRibbon.textContent = "DEMO MODE — showing a locally cached data snapshot, not a live API. Set API_BASE_URL in config.js after deploying to go live.";
  }
}

function populatePickers() {
  el.concentrationSelect.innerHTML = BSBA_CONCENTRATIONS
    .map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`)
    .join("");
  el.termSelect.innerHTML = TERM_OPTIONS
    .map((t) => `<option value="${t}">${t}</option>`)
    .join("");
  el.termSelect.value = state.term;
}

/* ============================================================
   Rendering — page header / assumptions
   ============================================================ */
function renderHeader(view) {
  const concentration = el.concentrationSelect.value || BSBA_CONCENTRATIONS[0];
  el.cohortChip.textContent = `Cohort: ${view.cohort_size} incoming BSBA freshmen`;
  el.pageTitle.textContent = `Recommended ${state.term} freshman block`;
  el.scopeRow.innerHTML = [
    `Major: Business Administration (${escapeHtml(concentration)} concentration)`,
    `Class year: ${escapeHtml(view.class_year || "Freshman")}`,
    `Target load: ${view.unit_target ? view.unit_target.join("–") : "14–15"} units`,
  ].map((t) => `<span class="tag scope-tag">${t}</span>`).join("");

  el.assumptionsPanel.hidden = false;
  const a = view.assumptions || {};
  const rows = [];
  if (a.req_type) rows.push(["Requirement type (GEM classification)", a.req_type]);
  if (a.meeting_patterns) rows.push(["Meeting time patterns", a.meeting_patterns]);
  rows.push([
    "Concentration selector",
    "Freshman-year course-taking is nearly identical across all 10 BSBA concentrations, so the data above is pooled across all of them — the picker above changes this page's labels only, not the underlying recommendation.",
  ]);
  el.assumptionsList.innerHTML = rows
    .map(([dt, dd]) => `<div><dt>${escapeHtml(dt)}</dt><dd>${escapeHtml(dd)}</dd></div>`)
    .join("");
}

/* ============================================================
   Rendering — state banners (errors / empty states)
   ============================================================ */
function bannerHtml(kind, message) {
  const cls = { info: "notification-info", warning: "notification-warning", error: "notification-error" }[kind];
  return `<div class="notification-banner ${cls}"><div class="grid"><p>${message}</p></div></div>`;
}

function classifyRationaleError(msg) {
  const lower = (msg || "").toLowerCase();
  if (/credential|access.?denied|not set|unrecognizedclient|forbidden/.test(lower)) {
    return { kind: "error", text: `The AI rationale couldn't be generated — Bedrock access isn't configured for this environment (${escapeHtml(msg)}). The course table above is still accurate; only the written explanation is unavailable. Contact whoever owns AWS deployment.` };
  }
  if (/throttl|timeout|rate|temporar|503|529/.test(lower)) {
    return { kind: "warning", text: "The AI rationale is taking longer than usual to generate. This is temporary — try again in a moment. The course table above is unaffected." };
  }
  return { kind: "warning", text: `The AI rationale is unavailable right now (${escapeHtml(msg)}). The course table above is still accurate.` };
}

function renderStateBanner(view) {
  const banners = [];
  if (view.networkError) {
    banners.push(bannerHtml("error", `Can't reach the API at <code>${escapeHtml(API_BASE_URL)}</code> (${escapeHtml(view.networkError)}). Showing the last-known local snapshot instead — course data below may be stale and no live AI rationale/Q&amp;A is available.`));
  }
  if (view.cohort_size === 0 || !view.candidate_schedules || view.candidate_schedules.length === 0) {
    banners.push(bannerHtml("info", `${escapeHtml(state.term)} doesn't have enough historical enrollment yet to generate a recommendation. Try another term, or check back once more data is available.`));
  }
  el.stateBannerHost.innerHTML = banners.join("");
}

/* ============================================================
   Rendering — top pick + comparison table rows (shared)
   ============================================================ */
function meetingSummaryHtml(course) {
  const patterns = course.meeting_patterns || [];
  if (!patterns.length) {
    return `<span class="no-data">no post-census meeting data</span>`;
  }
  const best = patterns[0];
  if (best.note) {
    return `${escapeHtml(best.days)}<span class="caveat">${escapeHtml(best.note)}</span>`;
  }
  return `${escapeHtml(best.days)} · ${formatTime12h(best.start)}–${formatTime12h(best.end)}<span class="caveat">informational, not conflict-checked</span>`;
}

function reqTagHtml(reqType) {
  if (!reqType) return `<span class="req-tag unknown">Not in freshman roadmap</span>`;
  const cls = REQ_TAG_CLASS[reqType] || "unknown";
  const label = reqType === "Major / Gen Ed" ? "GEM" : reqType === "General Education" ? "Gen ed" : reqType;
  return `<span class="req-tag ${cls}">${escapeHtml(label)}</span>`;
}

function unitsHtml(course) {
  if (course.units_estimated) {
    return `<span class="units-estimated" title="Not found in the E3E4 offering catalog; units defaulted to ${course.units}">${course.units} <span class="uncertain-flag">(uncertain)</span></span>`;
  }
  return `<span class="units-clean">${course.units}</span>`;
}

function pctHtml(course, cohortSize) {
  const pct = Math.round(course.pct_of_cohort * 100);
  const n = cohortSize ? Math.round(course.pct_of_cohort * cohortSize) : null;
  return `<span class="pct-cell"><span class="infobar-graph"><span class="bar" style="width:${pct}%"></span></span><span class="infobar-value">${pct}%</span>${n !== null ? `<span class="n">(${n}/${cohortSize})</span>` : ""}</span>`;
}

function courseRowsHtml(schedule, cohortSize) {
  return schedule.courses
    .map(
      (c) => `<tr>
        <td><strong>${escapeHtml(c.course)}</strong></td>
        <td>${unitsHtml(c)}</td>
        <td>${pctHtml(c, cohortSize)}</td>
        <td>${reqTagHtml(c.req_type)}</td>
        <td class="meeting-cell">${meetingSummaryHtml(c)}</td>
      </tr>`
    )
    .join("");
}

function renderTopPick(view) {
  const schedule = view.candidate_schedules[state.activeScheduleIndex];
  if (!schedule) {
    el.topPickSection.hidden = true;
    return;
  }
  el.topPickSection.hidden = false;
  const isTop = state.activeScheduleIndex === 0;
  el.topPickTitle.textContent = `${schedule.total_units} units · ${schedule.courses.length} courses${isTop ? "" : ` (alternative #${state.activeScheduleIndex + 1})`}`;
  el.topPickSupport.textContent = `support score ${schedule.score.toFixed(2)}`;
  el.topPickBody.innerHTML = courseRowsHtml(schedule, view.cohort_size);
}

/* ============================================================
   Rendering — weekly calendar
   ============================================================ */
function courseColor(course) {
  return CAL_BLOCK_CLASS[course.req_type] || "req-unknown";
}

function renderCalendar(view) {
  const schedule = view.candidate_schedules[state.activeScheduleIndex];
  if (!schedule) {
    el.calendarWrap.hidden = true;
    return;
  }
  el.calendarWrap.hidden = false;
  const isTop = state.activeScheduleIndex === 0;
  el.calendarSourceLabel.textContent = isTop ? "the top pick" : `alternative #${state.activeScheduleIndex + 1}`;

  // Header row
  const headerRow = `<div class="cal-header-row"><div class="cal-corner"></div>${DAY_COLUMNS.map((d) => `<div class="cal-day-head">${d.label}</div>`).join("")}</div>`;

  // Time axis
  const timeLabels = [];
  for (let min = CAL_START_MIN; min <= CAL_END_MIN; min += 60) {
    const topPct = ((min - CAL_START_MIN) / CAL_RANGE_MIN) * 100;
    const hh = Math.floor(min / 60);
    const label = hh > 12 ? `${hh - 12}:00pm` : hh === 12 ? "12:00pm" : `${hh}:00am`;
    timeLabels.push(`<span class="cal-time-label" style="top:${topPct}%">${label}</span>`);
  }
  const timeAxis = `<div class="cal-time-axis">${timeLabels.join("")}</div>`;

  // Day columns + blocks
  const blocksByDay = {};
  DAY_COLUMNS.forEach((d) => (blocksByDay[d.key] = []));
  const unplottable = [];

  schedule.courses.forEach((course) => {
    const slot = bestSlotFor(course);
    if (!slot) {
      const reason = (course.meeting_patterns || []).length ? "no cleanly-parseable meeting time on file" : "no post-census meeting data";
      unplottable.push(`${course.course} — ${reason}`);
      return;
    }
    const startMin = Math.max(CAL_START_MIN, timeToMinutes(slot.start));
    const endMin = Math.min(CAL_END_MIN, timeToMinutes(slot.end));
    if (endMin <= startMin) return;
    const tokens = parseDayTokens(slot.days);
    tokens.forEach((tok) => {
      const dayKey = TOKEN_TO_DAY[tok];
      if (!dayKey) return;
      blocksByDay[dayKey].push({ course, startMin, endMin });
    });
  });

  const dayColsHtml = DAY_COLUMNS.map((d) => {
    const items = blocksByDay[d.key].sort((a, b) => a.startMin - b.startMin);
    // Simple overlap handling: group overlapping items and split width evenly.
    const groups = [];
    items.forEach((item) => {
      const group = groups.find((g) => g.some((other) => item.startMin < other.endMin && other.startMin < item.endMin));
      if (group) group.push(item);
      else groups.push([item]);
    });
    const blocksHtml = groups
      .flatMap((group) =>
        group.map((item, idx) => {
          const topPct = ((item.startMin - CAL_START_MIN) / CAL_RANGE_MIN) * 100;
          const heightPct = ((item.endMin - item.startMin) / CAL_RANGE_MIN) * 100;
          const widthPct = 100 / group.length;
          const leftPct = widthPct * idx;
          return `<div class="cal-block ${courseColor(item.course)}" style="top:${topPct}%;height:${heightPct}%;left:calc(${leftPct}% + 2px);width:calc(${widthPct}% - 4px)" title="${escapeHtml(item.course.course)} — ${formatTime12h(minutesToHHMMSS(item.startMin))}-${formatTime12h(minutesToHHMMSS(item.endMin))}">
            <strong>${escapeHtml(item.course.course)}</strong>
            <span class="cal-time">${formatTime12h(minutesToHHMMSS(item.startMin))}-${formatTime12h(minutesToHHMMSS(item.endMin))}</span>
          </div>`;
        })
      )
      .join("");
    return `<div class="cal-day-col">${blocksHtml}</div>`;
  }).join("");

  const bodyRow = `<div class="cal-body-row">${timeAxis}${dayColsHtml}</div>`;

  el.calendarGrid.innerHTML = headerRow + bodyRow;

  // Legend
  const legendEntries = [
    ["Major", "req-major"],
    ["General Education", "req-gened"],
    ["Major / Gen Ed (GEM)", "req-gem"],
    ["Not in freshman roadmap", "req-unknown"],
  ];
  el.calendarLegend.innerHTML = legendEntries
    .map(([label, cls]) => `<span class="legend-item"><span class="swatch ${cls}" style="background:var(--color-term-element-${cls === "req-major" ? "major" : cls === "req-gened" ? "general-education" : cls === "req-gem" ? "elective" : "unknown"})"></span>${escapeHtml(label)}</span>`)
    .join("");

  if (unplottable.length) {
    el.calendarUnplottable.hidden = false;
    el.calendarUnplottable.innerHTML = `Not shown on the calendar (informational meeting-time gaps, per the assumptions panel above):<ul>${unplottable.map((u) => `<li>${escapeHtml(u)}</li>`).join("")}</ul>`;
  } else {
    el.calendarUnplottable.hidden = true;
    el.calendarUnplottable.innerHTML = "";
  }
}

function minutesToHHMMSS(min) {
  const h = Math.floor(min / 60);
  const m = min % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:00`;
}

/* ============================================================
   Rendering — rationale
   ============================================================ */
function renderRationale(view) {
  if (!view.candidate_schedules || !view.candidate_schedules.length) {
    el.rationaleBox.hidden = true;
    return;
  }
  el.rationaleBox.hidden = false;
  if (view.offline) {
    el.rationaleText.textContent = "Live AI rationale isn't available in demo mode. Set API_BASE_URL in config.js to a deployed API to generate a rationale here.";
    el.rationaleMeta.textContent = "offline / demo mode";
    return;
  }
  if (view.rationale) {
    el.rationaleText.textContent = view.rationale;
    el.rationaleMeta.textContent = `generated · claude on bedrock · ${state.term} · business administration freshman cohort`;
    return;
  }
  if (view.rationale_error) {
    const { text } = classifyRationaleError(view.rationale_error);
    el.rationaleText.innerHTML = text;
    el.rationaleMeta.textContent = "";
    return;
  }
  el.rationaleText.textContent = "No rationale available for this term.";
  el.rationaleMeta.textContent = "";
}

/* ============================================================
   Rendering — comparison view
   ============================================================ */
function renderComparison(view) {
  const others = view.candidate_schedules
    .map((s, i) => ({ s, i }))
    .filter(({ i }) => i !== state.activeScheduleIndex);
  if (!others.length) {
    el.comparisonSection.hidden = true;
    return;
  }
  el.comparisonSection.hidden = false;
  el.comparisonList.innerHTML = others
    .map(({ s, i }) => {
      const courseList = s.courses.map((c) => c.course).join(" · ");
      return `<details class="candidate-alt">
        <summary>
          <span><span class="rank">${i === 0 ? "Top pick" : `Alt #${i + 1}`}</span>&nbsp;${escapeHtml(courseList)} — ${s.total_units} units</span>
          <span class="support">support score ${s.score.toFixed(2)}</span>
        </summary>
        <div class="alt-body">
          <div class="table-wrapper">
            <table class="table-zebra">
              <thead><tr><th>Course</th><th>Units</th><th>% of cohort</th><th>Requirement</th><th>Typical meeting pattern</th></tr></thead>
              <tbody>${courseRowsHtml(s, view.cohort_size)}</tbody>
            </table>
          </div>
          <button class="button button-secondary calendar-swap-btn" data-schedule-index="${i}">View on calendar</button>
        </div>
      </details>`;
    })
    .join("");

  el.comparisonList.querySelectorAll("[data-schedule-index]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.activeScheduleIndex = Number(btn.dataset.scheduleIndex);
      renderAll(state.view);
      document.getElementById("calendarWrap").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

/* ============================================================
   Rendering — Q&A
   ============================================================ */
function renderQaThread() {
  if (!state.qaThread.length) {
    el.qaThread.innerHTML = "";
    el.qaThread.appendChild(el.qaEmptyState);
    return;
  }
  el.qaThread.innerHTML = state.qaThread
    .map((turn) => {
      if (turn.role === "q") {
        return `<div class="qa-turn q">${escapeHtml(turn.text)}</div>`;
      }
      const errCls = turn.error ? " error" : "";
      const guardrail = turn.error
        ? ""
        : `<span class="guardrail">If a question can't be answered from this data, this assistant says so rather than guessing.</span>`;
      return `<div class="qa-turn a${errCls}">${escapeHtml(turn.text)}${guardrail}</div>`;
    })
    .join("");
  el.qaThread.scrollTop = el.qaThread.scrollHeight;
}

async function submitQuestion() {
  const question = el.qaInput.value.trim();
  if (!question || state.qaBusy) return;

  if (state.mode !== "live") {
    state.qaThread.push({ role: "q", text: question });
    state.qaThread.push({ role: "a", text: "Live Q&A requires a deployed API — set API_BASE_URL in config.js. In demo mode this assistant can't answer questions.", error: true });
    el.qaInput.value = "";
    renderQaThread();
    return;
  }

  state.qaBusy = true;
  el.qaSubmit.disabled = true;
  state.qaThread.push({ role: "q", text: question });
  renderQaThread();
  el.qaInput.value = "";

  try {
    const resp = await fetch(`${API_BASE_URL.replace(/\/$/, "")}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const body = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(body.error || `API returned ${resp.status}`);
    state.qaThread.push({ role: "a", text: body.answer });
  } catch (err) {
    const { text } = classifyRationaleError(err.message);
    state.qaThread.push({ role: "a", text: stripHtml(text), error: true });
  } finally {
    state.qaBusy = false;
    el.qaSubmit.disabled = false;
    renderQaThread();
  }
}

function stripHtml(html) {
  const div = document.createElement("div");
  div.innerHTML = html;
  return div.textContent || "";
}

/* ============================================================
   Orchestration
   ============================================================ */
function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function renderAll(view) {
  renderStatusRibbon();
  renderHeader(view);
  renderStateBanner(view);
  renderTopPick(view);
  renderCalendar(view);
  renderRationale(view);
  renderComparison(view);
}

async function loadTerm(term) {
  state.term = term;
  state.activeScheduleIndex = 0;
  el.pageTitle.textContent = `Loading ${term} recommendation…`;
  const view = await fetchTerm(term);
  state.view = view;
  renderAll(view);
}

function wireControls() {
  el.termSelect.addEventListener("change", () => loadTerm(el.termSelect.value));
  el.concentrationSelect.addEventListener("change", () => {
    if (state.view) renderHeader(state.view);
  });
  el.qaSubmit.addEventListener("click", submitQuestion);
  el.qaInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") submitQuestion();
  });
}

async function init() {
  populatePickers();
  wireControls();
  try {
    await loadTerm(state.term);
  } catch (err) {
    el.stateBannerHost.innerHTML = bannerHtml("error", `Could not load any data (API or local snapshot): ${escapeHtml(err.message)}. If running locally, make sure you're serving this folder over http:// (not file://) — see frontend/web/README.md.`);
    el.statusRibbon.textContent = "ERROR — no data source available";
    el.statusRibbon.classList.add("mode-error");
  }
}

init();
