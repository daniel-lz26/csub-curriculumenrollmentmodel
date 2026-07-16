"use strict";

/* ============================================================
   Constants
   ============================================================ */
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

const CAL_START_MIN = 7 * 60;   // 7:00am
const CAL_END_MIN = 21 * 60;    // 9:00pm
const CAL_RANGE_MIN = CAL_END_MIN - CAL_START_MIN;

const REQ_TAG_CLASS = { "Major": "major", "General Education": "gened", "Major / Gen Ed": "gem" };
const CAL_BLOCK_CLASS = { "Major": "req-major", "General Education": "req-gened", "Major / Gen Ed": "req-gem" };
const ONLINE_MODE = "On-Line/Web";

// The generator's beam-search score is a weighted sum (see
// schedule_engine/config.py BASE_WEIGHTS) of these four signals. It's an
// arbitrary-scale ranking number for comparing blocks against each other
// within the *same* major/run — not a percentage, probability, or
// cross-major-comparable figure. Shown with this definition attached
// everywhere it appears, per explicit request — never bare.
const SCORE_DEFINITION =
  "Fit score: a weighted composite of four signals — how much of each course's meeting time falls in the preferred window, how popular the course was with real historical freshmen, how healthy the section's seat count is, and how compact the resulting week is (few campus days, small gaps). Higher is a better match for this block's preference profile. It is not a percentage, probability, or a number comparable across different majors.";
// Shorter version for space-constrained inline captions (full definition
// above is still used in title="" tooltips).
const SCORE_DEFINITION_SHORT =
  "Composite of time-window fit, popularity, seat health, and compactness — higher is a better match for this profile, not a percentage or a cross-major comparison.";

/* ============================================================
   State
   ============================================================ */
const state = {
  artifact: null,        // currently loaded schedule_engine artifact
  activeBlockIndex: 0,    // index into state.blocksSorted
  blocksSorted: [],       // artifact.blocks sorted by score desc
  qaThread: [],
  qaBusy: false,
};

/* ============================================================
   DOM refs
   ============================================================ */
const el = {
  statusRibbon: document.getElementById("statusRibbon"),
  majorSelect: document.getElementById("majorSelect"),
  blockSelect: document.getElementById("blockSelect"),
  cohortChip: document.getElementById("cohortChip"),
  pageTitle: document.getElementById("pageTitle"),
  scopeRow: document.getElementById("scopeRow"),
  assumptionsPanel: document.getElementById("assumptionsPanel"),
  assumptionsList: document.getElementById("assumptionsList"),
  stateBannerHost: document.getElementById("stateBannerHost"),
  topPickSection: document.getElementById("topPickSection"),
  topPickBadge: document.getElementById("topPickBadge"),
  topPickTitle: document.getElementById("topPickTitle"),
  topPickSupport: document.getElementById("topPickSupport"),
  scoreCaption: document.getElementById("scoreCaption"),
  advisoriesBanner: document.getElementById("advisoriesBanner"),
  topPickBody: document.getElementById("topPickBody"),
  calendarWrap: document.getElementById("calendarWrap"),
  calendarSourceLabel: document.getElementById("calendarSourceLabel"),
  calendarConflictBanner: document.getElementById("calendarConflictBanner"),
  calendarGrid: document.getElementById("calendarGrid"),
  calendarLegend: document.getElementById("calendarLegend"),
  calendarUnplottable: document.getElementById("calendarUnplottable"),
  rationaleBox: document.getElementById("rationaleBox"),
  rationaleText: document.getElementById("rationaleText"),
  comparisonSection: document.getElementById("comparisonSection"),
  comparisonList: document.getElementById("comparisonList"),
  qaThread: document.getElementById("qaThread"),
  qaEmptyState: document.getElementById("qaEmptyState"),
  qaInput: document.getElementById("qaInput"),
  qaSubmit: document.getElementById("qaSubmit"),
};

/* ============================================================
   Time helpers — artifact times are already clean "HH:MM" 24h strings
   and days are already an array of M/T/W/Th/F tokens (real, conflict-
   checked sections), so there's no free-text parsing needed here (unlike
   the older mining-output format).
   ============================================================ */
function timeToMinutes(hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

function formatTime12h(hhmm) {
  let [h, m] = hhmm.split(":").map(Number);
  const ampm = h >= 12 ? "PM" : "AM";
  h = h % 12;
  if (h === 0) h = 12;
  return `${h}:${String(m).padStart(2, "0")}${ampm}`;
}

// A course is plottable on the calendar only if it has real days AND a
// real start/end time. Anything else (TBA face-to-face sections, async
// online sections) is explicitly excluded and called out to the user
// instead of being silently dropped or shown with a fabricated time.
function isPlottable(course) {
  return Array.isArray(course.days) && course.days.length > 0 && !!course.start && !!course.end;
}

function isAsyncOnline(course) {
  return !isPlottable(course) && course.mode === ONLINE_MODE;
}

// Face-to-face/hybrid sections with no meeting time on file are genuinely
// TBA (registrar hasn't posted a room/time yet) — distinct from an async
// online section, which has no meeting time by design.
function meetingLabel(course) {
  if (isPlottable(course)) {
    return `${course.days.join("")} · ${formatTime12h(course.start)}–${formatTime12h(course.end)}`;
  }
  if (isAsyncOnline(course)) {
    return `<span class="no-time-tag">Online — async, no fixed meeting time</span>`;
  }
  return `<span class="no-time-tag tba">TBA</span>`;
}

/* ============================================================
   Fetching
   ============================================================ */
async function loadArtifact(filename) {
  const resp = await fetch(`${ARTIFACTS_BASE_PATH}${filename}`);
  if (!resp.ok) throw new Error(`Could not load ${filename}: ${resp.status}`);
  return resp.json();
}

/* ============================================================
   Rendering — masthead / status
   ============================================================ */
function renderStatusRibbon() {
  el.statusRibbon.classList.remove("mode-demo", "mode-live", "mode-error");
  el.statusRibbon.classList.add("mode-demo");
  el.statusRibbon.textContent =
    `Showing generated schedule blocks from schedule_engine (${state.artifact.sections_snapshot} section snapshot). ` +
    (API_BASE_URL
      ? `Q&A is live against ${API_BASE_URL}.`
      : `Q&A is in offline/demo mode — set API_BASE_URL in config.js to enable it.`);
}

function populateMajorPicker() {
  el.majorSelect.innerHTML = MAJOR_ARTIFACTS
    .map((m) => `<option value="${escapeHtml(m.file)}">${escapeHtml(m.label)}</option>`)
    .join("");
}

// Single source of truth for how a block is identified in text, used by the
// block picker, the selected-block card, the calendar caption, and the
// comparison list — so those four places can never show a different name
// for the same block.
function blockShortLabel(block, index) {
  return index === 0 ? `★ Top pick (Block ${block.block_id})` : `Block ${block.block_id}`;
}
function blockFullLabel(block, index) {
  return `Block ${block.block_id} — ${block.label}${index === 0 ? " (top pick)" : ""}`;
}

function populateBlockPicker() {
  el.blockSelect.innerHTML = state.blocksSorted
    .map((b, i) => `<option value="${i}">${escapeHtml(blockFullLabel(b, i))}</option>`)
    .join("");
  el.blockSelect.value = state.activeBlockIndex;
}

/* ============================================================
   Rendering — page header / assumptions
   ============================================================ */
function renderHeader() {
  const a = state.artifact;
  const totalSeats = a.blocks.reduce((sum, b) => sum + (b.cohort_capacity || 0), 0);
  el.cohortChip.textContent = `${a.blocks.length} block${a.blocks.length === 1 ? "" : "s"} · ~${totalSeats} planned seats`;
  el.pageTitle.textContent = `${a.major} — ${a.term} freshman blocks`;

  const prefs = a.preferences || {};
  const window_ = prefs.preferred_window || {};
  el.scopeRow.innerHTML = [
    `Major: ${escapeHtml(a.major)}`,
    `Term: ${escapeHtml(a.term)}`,
    `Preference profile: ${escapeHtml(prefs.profile || "default")}`,
    `Preferred window: ${escapeHtml(window_.start || "?")}–${escapeHtml(window_.end || "?")}`,
  ].map((t) => `<span class="tag scope-tag">${t}</span>`).join("");

  el.assumptionsPanel.hidden = false;
  const rows = [
    ["What this is", "Real, section-level Fall 2026 blocks — every course/time was open at the snapshot, and each block is deterministically validated conflict-free."],
    ["Fit score", SCORE_DEFINITION_SHORT],
    ["Meeting times", "No listed time → “TBA” (not yet scheduled) or “Online — async”; neither is plotted on the calendar below."],
    ["Popularity", "“N/D mined freshmen” = N of D real historical freshmen in this major took that course."],
  ];
  if (a.notes && a.notes.length) {
    rows.push(["Generator notes", a.notes.join(" ")]);
  }
  el.assumptionsList.innerHTML = rows
    .map(([dt, dd]) => `<div><dt>${escapeHtml(dt)}</dt><dd>${dd}</dd></div>`)
    .join("");
}

/* ============================================================
   Rendering — state banners
   ============================================================ */
function bannerHtml(kind, message) {
  const cls = { info: "notification-info", warning: "notification-warning", error: "notification-error" }[kind];
  return `<div class="notification-banner ${cls}"><div class="grid"><p>${message}</p></div></div>`;
}

function renderStateBanner() {
  const banners = [];
  if (!state.artifact.blocks || state.artifact.blocks.length === 0) {
    banners.push(bannerHtml("info", `No schedule blocks were generated for ${escapeHtml(state.artifact.major)}. Check schedule_engine's generator notes below, or try another major.`));
  }
  el.stateBannerHost.innerHTML = banners.join("");
}

/* ============================================================
   Rendering — course rows (shared by selected block + comparison view)
   ============================================================ */
function reqTagHtml(reqType) {
  const cls = REQ_TAG_CLASS[reqType] || "unknown";
  const label = reqType === "Major / Gen Ed" ? "GEM" : reqType === "General Education" ? "Gen ed" : reqType || "Elective";
  return `<span class="req-tag ${cls}">${escapeHtml(label)}</span>`;
}

function popularityHtml(course) {
  if (!course.freshman_popularity) return `<span class="popularity-cell">—</span>`;
  return `<span class="popularity-cell">${escapeHtml(course.freshman_popularity)}</span>`;
}

function courseRowsHtml(block) {
  return block.courses
    .map((c) => {
      const seatNote = c.waitlist > 0
        ? ` <span class="uncertain-flag">(waitlist ${c.waitlist})</span>`
        : c.seats_open_at_generation <= 0
        ? ` <span class="uncertain-flag">(full)</span>`
        : "";
      return `<tr>
        <td><strong>${escapeHtml(c.course)}</strong><br><span style="color:var(--color-text-gray);font-size:.82rem">${escapeHtml(c.title || "")} · sec ${escapeHtml(c.section)}${seatNote}</span></td>
        <td>${escapeHtml(c.requirement)}</td>
        <td class="units-clean">${c.units}</td>
        <td>${popularityHtml(c)}</td>
        <td>${reqTagHtml(c.req_type)}</td>
        <td class="meeting-cell">${meetingLabel(c)}</td>
      </tr>`;
    })
    .join("");
}

function renderAdvisories(block) {
  if (!block.advisories || !block.advisories.length) {
    el.advisoriesBanner.innerHTML = "";
    return;
  }
  el.advisoriesBanner.innerHTML = `<div class="advisories-banner"><strong>Seat advisories</strong><ul>${block.advisories
    .map((a) => `<li>${escapeHtml(a)}</li>`)
    .join("")}</ul></div>`;
}

function renderSelectedBlock() {
  const block = state.blocksSorted[state.activeBlockIndex];
  if (!block) {
    el.topPickSection.hidden = true;
    return;
  }
  el.topPickSection.hidden = false;
  const isTop = state.activeBlockIndex === 0;
  el.topPickBadge.textContent = isTop ? "Top pick" : `Block ${block.block_id}`;
  el.topPickBadge.classList.toggle("alt", !isTop);
  el.topPickTitle.textContent = `${blockFullLabel(block, state.activeBlockIndex)} · ${block.total_units} units · ${block.courses.length} courses`;
  el.topPickSupport.textContent = `fit score ${block.score.toFixed(2)}`;
  el.topPickSupport.title = SCORE_DEFINITION;
  el.scoreCaption.textContent = SCORE_DEFINITION_SHORT;
  renderAdvisories(block);
  el.topPickBody.innerHTML = courseRowsHtml(block);
}

/* ============================================================
   Rendering — weekly calendar
   ============================================================ */
function courseColor(course) {
  return CAL_BLOCK_CLASS[course.req_type] || "req-unknown";
}

function minutesToHHMM(min) {
  const h = Math.floor(min / 60);
  const m = min % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function renderCalendar() {
  const block = state.blocksSorted[state.activeBlockIndex];
  if (!block) {
    el.calendarWrap.hidden = true;
    return;
  }
  el.calendarWrap.hidden = false;
  el.calendarSourceLabel.textContent = blockFullLabel(block, state.activeBlockIndex);

  const headerRow = `<div class="cal-header-row"><div class="cal-corner"></div>${DAY_COLUMNS.map((d) => `<div class="cal-day-head">${d.label}</div>`).join("")}</div>`;

  const timeLabels = [];
  for (let min = CAL_START_MIN; min <= CAL_END_MIN; min += 60) {
    const topPct = ((min - CAL_START_MIN) / CAL_RANGE_MIN) * 100;
    const hh = Math.floor(min / 60);
    const label = hh > 12 ? `${hh - 12}:00pm` : hh === 12 ? "12:00pm" : `${hh}:00am`;
    timeLabels.push(`<span class="cal-time-label" style="top:${topPct}%">${label}</span>`);
  }
  const timeAxis = `<div class="cal-time-axis">${timeLabels.join("")}</div>`;

  const blocksByDay = {};
  DAY_COLUMNS.forEach((d) => (blocksByDay[d.key] = []));
  const excluded = [];

  block.courses.forEach((course) => {
    if (!isPlottable(course)) {
      excluded.push(`${course.course} — ${isAsyncOnline(course) ? "online, asynchronous (no fixed meeting time)" : "TBA (not yet scheduled by the registrar)"}`);
      return;
    }
    const startMin = Math.max(CAL_START_MIN, timeToMinutes(course.start));
    const endMin = Math.min(CAL_END_MIN, timeToMinutes(course.end));
    if (endMin <= startMin) return;
    course.days.forEach((tok) => {
      const dayKey = TOKEN_TO_DAY[tok];
      if (!dayKey) return;
      blocksByDay[dayKey].push({ course, startMin, endMin });
    });
  });

  // Explicit conflict check, not just an absence of visual overlap. Blocks
  // are generated conflict-free (schedule_engine/validator.py), but this
  // renders that guarantee visibly instead of asking the reader to trust it
  // — and it would catch a real problem if an artifact were hand-edited
  // outside the validator.
  const conflicts = [];
  DAY_COLUMNS.forEach((d) => {
    const items = blocksByDay[d.key];
    for (let i = 0; i < items.length; i += 1) {
      for (let j = i + 1; j < items.length; j += 1) {
        const A = items[i], B = items[j];
        if (A.startMin < B.endMin && B.startMin < A.endMin) {
          conflicts.push(
            `${A.course.course} vs ${B.course.course} on ${d.label} (${formatTime12h(minutesToHHMM(A.startMin))}–${formatTime12h(minutesToHHMM(A.endMin))} overlaps ${formatTime12h(minutesToHHMM(B.startMin))}–${formatTime12h(minutesToHHMM(B.endMin))})`
          );
        }
      }
    }
  });
  if (conflicts.length) {
    el.calendarConflictBanner.innerHTML = `<div class="notification-banner notification-error"><div class="grid"><p><strong>Time conflict detected</strong> in ${escapeHtml(blockFullLabel(block, state.activeBlockIndex))}: ${conflicts.map(escapeHtml).join("; ")}. This block should not be published as-is.</p></div></div>`;
  } else {
    el.calendarConflictBanner.innerHTML = `<div class="calendar-ok">&#10003; No time conflicts among the ${block.courses.filter(isPlottable).length} scheduled course${block.courses.filter(isPlottable).length === 1 ? "" : "s"} shown below.</div>`;
  }

  const dayColsHtml = DAY_COLUMNS.map((d) => {
    const items = blocksByDay[d.key].sort((a, b) => a.startMin - b.startMin);
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
          const timeStr = `${formatTime12h(minutesToHHMM(item.startMin))}-${formatTime12h(minutesToHHMM(item.endMin))}`;
          return `<div class="cal-block ${courseColor(item.course)}" style="top:${topPct}%;height:${heightPct}%;left:calc(${leftPct}% + 2px);width:calc(${widthPct}% - 4px)" title="${escapeHtml(item.course.course)} — ${timeStr}">
            <strong>${escapeHtml(item.course.course)}</strong>
            <span class="cal-time">${timeStr}</span>
          </div>`;
        })
      )
      .join("");
    return `<div class="cal-day-col">${blocksHtml}</div>`;
  }).join("");

  const bodyRow = `<div class="cal-body-row">${timeAxis}${dayColsHtml}</div>`;
  el.calendarGrid.innerHTML = headerRow + bodyRow;

  const legendEntries = [
    ["Major", "major"],
    ["General Education", "gened"],
    ["Major / Gen Ed (GEM)", "gem"],
    ["Elective / other", "unknown"],
  ];
  el.calendarLegend.innerHTML = legendEntries
    .map(([label, key]) => {
      const varName = key === "major" ? "major" : key === "gened" ? "general-education" : key === "gem" ? "elective" : "unknown";
      return `<span class="legend-item"><span class="swatch" style="background:var(--color-term-element-${varName})"></span>${escapeHtml(label)}</span>`;
    })
    .join("");

  if (excluded.length) {
    el.calendarUnplottable.hidden = false;
    el.calendarUnplottable.innerHTML = `Not shown on the calendar (no usable meeting time on file):<ul>${excluded.map((u) => `<li>${escapeHtml(u)}</li>`).join("")}</ul>`;
  } else {
    el.calendarUnplottable.hidden = true;
    el.calendarUnplottable.innerHTML = "";
  }
}

/* ============================================================
   Rendering — "why this block" (deterministic, no LLM call)
   ============================================================ */
function renderRationale() {
  const block = state.blocksSorted[state.activeBlockIndex];
  if (!block) {
    el.rationaleBox.hidden = true;
    return;
  }
  el.rationaleBox.hidden = false;
  const isTop = state.activeBlockIndex === 0;
  const campusDays = new Set(block.courses.filter(isPlottable).flatMap((c) => c.days)).size;
  const tbaCount = block.courses.filter((c) => !isPlottable(c) && !isAsyncOnline(c)).length;
  const asyncCount = block.courses.filter(isAsyncOnline).length;
  const popular = block.courses.filter((c) => c.freshman_popularity).sort((a, b) => {
    const pa = parseInt(a.freshman_popularity, 10) || 0;
    const pb = parseInt(b.freshman_popularity, 10) || 0;
    return pb - pa;
  })[0];

  const parts = [];
  parts.push(
    `${blockFullLabel(block, state.activeBlockIndex)}${isTop ? " is the highest fit-score block generated for this major" : ""} — fit score ${block.score.toFixed(2)} (see the definition above).`
  );
  parts.push(`It covers ${block.courses.length} courses (${block.total_units} units) across ${campusDays} campus day${campusDays === 1 ? "" : "s"}${block.cohort_capacity ? `, sized for ~${block.cohort_capacity} students given current seat availability` : ""}.`);
  if (popular) {
    parts.push(`${popular.course} is the most historically popular course in this block (${popular.freshman_popularity}).`);
  }
  if (block.advisories && block.advisories.length) {
    parts.push(`${block.advisories.length} section${block.advisories.length === 1 ? " needs" : "s need"} attention before this can be published — see the advisory banner above.`);
  }
  if (tbaCount) {
    parts.push(`${tbaCount} course${tbaCount === 1 ? "" : "s"} ${tbaCount === 1 ? "is" : "are"} still TBA and excluded from the week view below.`);
  }
  if (asyncCount) {
    parts.push(`${asyncCount} course${asyncCount === 1 ? " is" : "s are"} fully online/asynchronous and also excluded from the week view.`);
  }
  el.rationaleText.textContent = parts.join(" ");
}

/* ============================================================
   Rendering — comparison view
   ============================================================ */
function renderComparison() {
  const others = state.blocksSorted.map((b, i) => ({ b, i })).filter(({ i }) => i !== state.activeBlockIndex);
  if (!others.length) {
    el.comparisonSection.hidden = true;
    return;
  }
  el.comparisonSection.hidden = false;
  el.comparisonList.innerHTML = others
    .map(({ b, i }) => {
      const courseList = b.courses.map((c) => c.course).join(" · ");
      return `<details class="candidate-alt">
        <summary>
          <span><span class="rank">${escapeHtml(blockShortLabel(b, i))}</span>&nbsp;${escapeHtml(b.label)}: ${escapeHtml(courseList)} — ${b.total_units} units</span>
          <span class="support" title="${escapeHtml(SCORE_DEFINITION)}">fit score ${b.score.toFixed(2)}</span>
        </summary>
        <div class="alt-body">
          ${b.advisories && b.advisories.length ? `<div class="advisories-banner"><strong>Seat advisories</strong><ul>${b.advisories.map((a) => `<li>${escapeHtml(a)}</li>`).join("")}</ul></div>` : ""}
          <div class="table-wrapper">
            <table class="table-zebra">
              <thead><tr><th>Course</th><th>Requirement</th><th>Units</th><th>Freshman popularity</th><th>Requirement type</th><th>Meeting pattern</th></tr></thead>
              <tbody>${courseRowsHtml(b)}</tbody>
            </table>
          </div>
          <button class="button button-secondary calendar-swap-btn" data-block-index="${i}">View on calendar</button>
        </div>
      </details>`;
    })
    .join("");

  el.comparisonList.querySelectorAll("[data-block-index]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.activeBlockIndex = Number(btn.dataset.blockIndex);
      el.blockSelect.value = state.activeBlockIndex;
      renderAll();
      el.calendarWrap.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

/* ============================================================
   Rendering — schedule advisor (/advisor endpoint: what-if/prerequisite
   questions grounded in the real degree-roadmap data, not the pooled
   mining dataset the old /ask endpoint used)
   ============================================================ */
function renderQaThread() {
  if (!state.qaThread.length) {
    el.qaThread.innerHTML = "";
    el.qaThread.appendChild(el.qaEmptyState);
    return;
  }
  el.qaThread.innerHTML = state.qaThread
    .map((turn) => {
      if (turn.role === "q") return `<div class="qa-turn q">${escapeHtml(turn.text)}</div>`;
      const errCls = turn.error ? " error" : "";
      const guardrail = turn.error ? "" : `<span class="guardrail">If a question can't be answered from this data, this assistant says so rather than guessing.</span>`;
      return `<div class="qa-turn a${errCls}">${escapeHtml(turn.text)}${guardrail}</div>`;
    })
    .join("");
  el.qaThread.scrollTop = el.qaThread.scrollHeight;
}

function classifyError(msg) {
  const lower = (msg || "").toLowerCase();
  if (/credential|access.?denied|not set|bedrock|forbidden/.test(lower)) {
    return `The advisor isn't configured for this environment (${msg}). Contact whoever owns AWS deployment.`;
  }
  if (/throttl|timeout|rate|temporar|503|529/.test(lower)) {
    return "This is taking longer than usual — try again in a moment.";
  }
  return `Unavailable right now (${msg}).`;
}

async function submitQuestion() {
  const question = el.qaInput.value.trim();
  if (!question || state.qaBusy) return;

  if (!API_BASE_URL) {
    state.qaThread.push({ role: "q", text: question });
    state.qaThread.push({ role: "a", text: "Live advisor requires a deployed API — set API_BASE_URL in config.js. In demo mode this assistant can't answer questions.", error: true });
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
    const resp = await fetch(`${API_BASE_URL.replace(/\/$/, "")}/advisor`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // `major` is whatever's currently on screen -- the advisor also
      // regex-extracts a course code from the question text itself, so
      // this is a hint, not a requirement.
      body: JSON.stringify({ question, major: state.artifact ? state.artifact.major : undefined }),
    });
    const body = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(body.error || `API returned ${resp.status}`);
    state.qaThread.push({ role: "a", text: body.answer });
  } catch (err) {
    state.qaThread.push({ role: "a", text: classifyError(err.message), error: true });
  } finally {
    state.qaBusy = false;
    el.qaSubmit.disabled = false;
    renderQaThread();
  }
}

/* ============================================================
   Orchestration
   ============================================================ */
function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function renderAll() {
  renderStatusRibbon();
  renderHeader();
  renderStateBanner();
  renderSelectedBlock();
  renderCalendar();
  renderRationale();
  renderComparison();
}

async function selectMajor(filename) {
  const known = MAJOR_ARTIFACTS.find((m) => m.file === filename);
  el.pageTitle.textContent = `Loading ${known ? known.label : filename}…`;
  const artifact = await loadArtifact(filename);
  state.artifact = artifact;
  state.blocksSorted = [...(artifact.blocks || [])].sort((a, b) => b.score - a.score);
  state.activeBlockIndex = 0;
  populateBlockPicker();
  renderAll();
}

function wireControls() {
  el.majorSelect.addEventListener("change", () => selectMajor(el.majorSelect.value).catch(showFatalError));
  el.blockSelect.addEventListener("change", () => {
    state.activeBlockIndex = Number(el.blockSelect.value);
    renderAll();
  });
  el.qaSubmit.addEventListener("click", submitQuestion);
  el.qaInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") submitQuestion();
  });
}

function showFatalError(err) {
  el.stateBannerHost.innerHTML = bannerHtml(
    "error",
    `Could not load schedule data: ${escapeHtml(err.message)}. If running locally, make sure you're serving this folder over http:// (not file://) — see frontend/web/README.md.`
  );
  el.statusRibbon.textContent = "ERROR — no data source available";
  el.statusRibbon.classList.remove("mode-demo", "mode-live");
  el.statusRibbon.classList.add("mode-error");
}

async function init() {
  populateMajorPicker();
  wireControls();
  try {
    await selectMajor(MAJOR_ARTIFACTS[0].file);
  } catch (err) {
    showFatalError(err);
  }
}

init();
