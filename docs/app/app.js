// Timesag -- web port of the CustomTkinter week interface (timesag.py).
// Same columns, boxes, ruler and payroll lines; Copy only, no Save.
// The week auto-persists to localStorage instead of Timesag/<WN>_oat.txt.

import {
  EMP, DEFAULT_HOURS, HOLIDAY, SICK, SICKDAY, DAY_TYPES, TYPE_COLOR, TYPE_PREVIEW,
  DAY_START, MIN_DUR, PX_PER_HOUR, TARGET_HOURS, GRID_COLOR, LABEL_COLOR,
  MONTHS, WEEKDAYS, FALLBACK_PROJECTS, OBS_SEED, FLAG_SVG,
  EVENT_URL, PAGEPROPS_URL, WBENTITIES_URL, FETCH_TIMEOUT,
  SCIENCE_WORDS, FIGURE_WORDS, SRC_BASE, WD_MALE, DIVERSITY_CHANCE,
  LS_WEEK, LS_EVENTS, LS_OFFSET, STORE_VERSION,
} from "./data.js";

// ---- helpers ---------------------------------------------------------------

// JS % is remainder, not modulo -- every hour wrap needs this.
export const mod24 = (x) => ((x % 24) + 24) % 24;

const pad2 = (n) => String(n).padStart(2, "0");

export function mondayOf(d) {
  const m = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  m.setDate(m.getDate() - ((m.getDay() + 6) % 7));
  return m;
}

const addDays = (d, n) => {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  x.setDate(x.getDate() + n);
  return x;
};

// ISO-8601 week AND week-numbering year. 2025-12-29 is 2026-W01, so the year
// here is not getFullYear() -- using that would corrupt two weeks every year.
export function isoWeekParts(d) {
  const t = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  t.setDate(t.getDate() + 3 - ((t.getDay() + 6) % 7));   // Thursday of this week
  const isoYear = t.getFullYear();
  const jan4 = new Date(isoYear, 0, 4);
  const week = 1 + Math.round(
    ((t - jan4) / 86400000 - 3 + ((jan4.getDay() + 6) % 7)) / 7);
  return { isoYear, week };
}

// Local getters only -- toISOString() shifts the date by the UTC offset.
export const dayKey = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
const mmdd = (d) => `${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
const ddmmyyyy = (d) => `${pad2(d.getDate())}-${pad2(d.getMonth() + 1)}-${d.getFullYear()}`;

// timesag.py:158 -- code is left-justified into 8 chars ({code:<8}).
export const fmtLine = (d, code, hours, f9, desc) =>
  `${EMP},${ddmmyyyy(d)},0,R,0,${String(code).padEnd(8)},${hours},T,${f9},,${desc}`;

// Python float(): "7.4abc" raises -> 0.0. parseFloat would give 7.4 and drift.
const NUMERIC = /^\s*[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?\s*$/;
export const hrsVal = (s) => (NUMERIC.test(s ?? "") ? Number(s) : 0);

// Python round() is half-to-even; Math.round is half-up, which shifts one
// channel of the box colours by 1.
function roundHalfEven(x) {
  const f = Math.floor(x);
  const d = x - f;
  if (d > 0.5) return f + 1;
  if (d < 0.5) return f;
  return f % 2 === 0 ? f : f + 1;
}

export function mix(c1, c2, t) {
  const a = [1, 3, 5].map((i) => parseInt(c1.slice(i, i + 2), 16));
  const b = [1, 3, 5].map((i) => parseInt(c2.slice(i, i + 2), 16));
  return "#" + a.map((v, i) => roundHalfEven(v + (b[i] - v) * t)
    .toString(16).padStart(2, "0")).join("");
}
export const darken = (c, t) => mix(c, "#000000", t);
export const lighten = (c, t) => mix(c, "#ffffff", t);

// ---- storage ---------------------------------------------------------------

let storageOK = true;

function lsGet(key) {
  try { return localStorage.getItem(key); }
  catch { storageOK = false; return null; }
}
function lsSet(key, value) {
  try { localStorage.setItem(key, value); }
  catch { storageOK = false; }
}

function loadWeek(monday) {
  const { isoYear, week } = isoWeekParts(monday);
  const raw = lsGet(LS_WEEK(isoYear, week));
  if (!raw) return null;
  try {
    const data = JSON.parse(raw);
    return data && data.days ? data.days : null;
  } catch { return null; }
}

function saveWeek() {
  const { isoYear, week } = isoWeekParts(state.monday);
  const days = {};
  for (const day of state.days) {
    days[dayKey(day.date)] = {
      start: day.start,
      segments: day.segments.map((s) => ({ type: s.type, hours: s.hours, proj: s.proj })),
    };
  }
  lsSet(LS_WEEK(isoYear, week), JSON.stringify({ v: STORE_VERSION, days }));
  setStatus(`Week ${pad2(week)} · ${storageOK ? "saved locally" : "not saved (storage blocked)"}`);
}

let saveTimer = null;
const saveWeekSoon = () => {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveWeek, 200);
};

function loadEvents() {
  const raw = lsGet(LS_EVENTS);
  if (!raw) return {};
  try {
    const data = JSON.parse(raw);
    const items = data && data.items ? data.items : data || {};
    // normalise legacy plain-string entries -> {text, url}
    return Object.fromEntries(Object.entries(items).map(
      ([k, v]) => [k, typeof v === "string" ? { text: v, url: null } : v]));
  } catch { return {}; }
}

const saveEvents = () =>
  lsSet(LS_EVENTS, JSON.stringify({ v: STORE_VERSION, items: state.events }));

// ---- state -----------------------------------------------------------------

const state = {
  monday: mondayOf(new Date()),
  scrollOffset: DAY_START - 1.0,   // start a bit before the first box
  projects: FALLBACK_PROJECTS,
  days: [],                        // Mon..Fri
  events: {},
};

const inFlight = new Set();
const failed = new Set();
let fetchCtl = null;
let drag = null;

const $ = (sel) => document.querySelector(sel);
const setStatus = (t) => { $("#status").textContent = t; };

// ---- column construction (once) --------------------------------------------

function buildColumns() {
  const week = $("#week");
  for (let i = 0; i < 5; i++) {
    const col = document.createElement("section");
    col.className = "col";
    col.innerHTML = `
      <div class="obs"></div>
      <div class="dayname"></div>
      <div class="dayhdr"><span class="dot">●</span><span class="daydate"></span></div>
      <div class="total"></div>
      <div class="axis"><div class="ruler"></div></div>
      <button class="add" type="button">＋  add box</button>
      <div class="fact"></div>`;
    week.appendChild(col);

    const day = {
      date: null, start: DAY_START, segments: [],
      col,
      obs: col.querySelector(".obs"),
      name: col.querySelector(".dayname"),
      dateEl: col.querySelector(".daydate"),
      dot: col.querySelector(".dot"),
      total: col.querySelector(".total"),
      axis: col.querySelector(".axis"),
      ruler: col.querySelector(".ruler"),
      fact: col.querySelector(".fact"),
      rows: [],
    };
    col.querySelector(".add").addEventListener("click", () => {
      addSegment(day, { hours: "1.00" });
      layoutDay(day);
      saveWeek();
    });
    new ResizeObserver(() => layoutDay(day)).observe(day.axis);
    state.days.push(day);
  }
}

// ---- segments --------------------------------------------------------------

function addSegment(day, { hours = DEFAULT_HOURS, type = "Working", proj = null } = {}) {
  const seg = { type, hours, proj: proj || state.projects[0].name };

  const box = document.createElement("div");
  box.className = "seg";
  box.innerHTML = `
    <div class="seg-top">
      <select class="seg-type"></select>
      <button class="seg-del" type="button" title="remove box">✕</button>
    </div>
    <div class="seg-sep"></div>
    <div class="seg-mid">
      <input class="seg-hours" type="text" inputmode="decimal">
      <select class="seg-proj"></select>
      <input class="seg-preview" type="text" disabled>
    </div>`;

  seg.el = box;
  seg.typeSel = box.querySelector(".seg-type");
  seg.del = box.querySelector(".seg-del");
  seg.sep = box.querySelector(".seg-sep");
  seg.hoursIn = box.querySelector(".seg-hours");
  seg.projSel = box.querySelector(".seg-proj");
  seg.preview = box.querySelector(".seg-preview");

  seg.typeSel.append(...DAY_TYPES.map((t) => new Option(t, t)));
  seg.projSel.append(...state.projects.map((p) => new Option(p.name, p.name)));
  seg.typeSel.value = seg.type;
  seg.projSel.value = seg.proj;
  seg.hoursIn.value = seg.hours;

  seg.typeSel.addEventListener("change", () => {
    seg.type = seg.typeSel.value;
    styleSegment(day, seg);
    layoutDay(day);
    saveWeek();
  });
  seg.projSel.addEventListener("change", () => {
    seg.proj = seg.projSel.value;
    saveWeek();
  });
  seg.hoursIn.addEventListener("input", () => {
    seg.hours = seg.hoursIn.value;
    layoutDay(day);
    saveWeekSoon();
  });
  seg.del.addEventListener("click", () => removeSegment(day, seg));

  day.axis.appendChild(box);
  day.segments.push(seg);
  // restyle the whole stack: the ✕ of the previous last box has to re-enable
  day.segments.forEach((s) => styleSegment(day, s));
  return seg;
}

function removeSegment(day, seg) {
  if (day.segments.length <= 1) return;   // timesag.py:388
  seg.el.remove();
  day.segments.splice(day.segments.indexOf(seg), 1);
  day.segments.forEach((s) => styleSegment(day, s));
  layoutDay(day);
  saveWeek();
}

function clearSegments(day) {
  day.segments.forEach((s) => s.el.remove());
  day.segments = [];
}

// port of _on_seg_type (timesag.py:360)
function styleSegment(day, seg) {
  const c = TYPE_COLOR[seg.type] || "#6b7280";
  seg.el.style.background = c;
  seg.typeSel.style.background = darken(c, 0.18);
  seg.typeSel.style.borderColor = darken(c, 0.34);
  seg.sep.style.background = lighten(c, 0.22);
  seg.hoursIn.disabled = seg.type === "Bank holiday";
  seg.del.disabled = day.segments.length <= 1;

  const working = seg.type === "Working";
  seg.projSel.hidden = !working;
  seg.preview.hidden = working;
  if (!working) seg.preview.value = TYPE_PREVIEW[seg.type] ?? "";
}

// ---- drawing ---------------------------------------------------------------

// port of _update_total (timesag.py:613)
function updateTotal(day) {
  const s = day.segments
    .filter((seg) => seg.type !== "Bank holiday")
    .reduce((acc, seg) => acc + hrsVal(seg.hours), 0);
  const num = s.toFixed(1).replace(/0+$/, "").replace(/\.$/, "");
  let color, text;
  if (Math.abs(s - TARGET_HOURS) < 0.01) { color = "#2e9e5b"; text = `${num} h ✓`; }
  else if (s <= 0) { color = "#6b7280"; text = "0 h"; }
  else if (s < TARGET_HOURS) { color = "#e0902f"; text = `${num} h`; }
  else { color = "#3b82f6"; text = `${num} h`; }
  day.total.textContent = text;
  day.total.style.background = color;
}

// port of _redraw_day (timesag.py:627): hour ruler behind, boxes stacked on top
function layoutDay(day) {
  updateTotal(day);
  const h = day.axis.clientHeight;
  const w = day.axis.clientWidth;
  if (w <= 1 || h <= 1) return;

  const off = state.scrollOffset;
  const nrows = Math.floor(h / PX_PER_HOUR) + 3;
  const first = Math.floor(off) - 1;

  while (day.rows.length < nrows) {
    const row = document.createElement("div");
    row.className = "rule";
    row.innerHTML = `<span></span>`;
    row.firstChild.style.color = LABEL_COLOR;
    row.style.background = "transparent";
    row.style.borderTop = `1px solid ${GRID_COLOR}`;
    day.ruler.appendChild(row);
    day.rows.push(row);
  }
  day.rows.forEach((row, i) => {
    const k = first + i;
    const y = (k - off) * PX_PER_HOUR;
    row.hidden = i >= nrows || y < -PX_PER_HOUR || y > h + PX_PER_HOUR;
    row.style.top = `${y}px`;
    row.firstChild.textContent = `${pad2(mod24(k))}:00`;
  });

  let start = day.start;
  for (const seg of day.segments) {
    const dur = Math.max(MIN_DUR, hrsVal(seg.hours));
    const y0 = (start - off) * PX_PER_HOUR;
    const y1 = (start + dur - off) * PX_PER_HOUR;
    seg.el.style.top = `${y0}px`;
    seg.el.style.height = `${Math.max(1, y1 - y0)}px`;
    seg.el.hidden = y1 < 0 || y0 > h;   // also keeps off-screen selects out of the tab order
    start += dur;
  }

  if (day.segments.length) {
    day.dot.style.color = TYPE_COLOR[day.segments[0].type] || "#6b7280";
  }
}

const layoutAll = () => state.days.forEach(layoutDay);

// ---- observances -----------------------------------------------------------

function setObservance(day) {
  day.obs.replaceChildren();
  for (const it of (OBS_SEED[mmdd(day.date)] || []).slice(0, 2)) {
    const row = document.createElement("div");
    row.className = "obs-row";
    row.innerHTML = FLAG_SVG[it.scope] || FLAG_SVG.world;
    const label = document.createElement("span");
    label.textContent = it.name;
    row.appendChild(label);
    day.obs.appendChild(row);
  }
}

// ---- "on this day" fact ----------------------------------------------------

// The timeout is PER REQUEST, like urlopen(timeout=6) -- a whole-chain deadline
// would blank days whose feed + 2 Wikidata calls together take longer than that.
// `signal` is the current render's, so a superseded render drops its responses.
async function getJSON(url, signal) {
  const deadline = AbortSignal.timeout(FETCH_TIMEOUT);
  const sig = AbortSignal.any ? AbortSignal.any([signal, deadline]) : signal;
  const resp = await fetch(url, { signal: sig, headers: { Accept: "application/json" } });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

// port of _score_item (timesag.py:507)
function scoreItem(item, src) {
  let base = SRC_BASE[src];
  const pages = item.pages || [];
  const desc = pages.length ? (pages[0].description || "") : "";
  const blob = `${item.text || ""} ${desc}`.toLowerCase();
  if (SCIENCE_WORDS.some((w) => blob.includes(w))) base += 3;
  if (FIGURE_WORDS.some((w) => blob.includes(w))) base += 2;
  return base;
}

const pageTitle = (p) =>
  (p.titles && p.titles.normalized) || p.normalizedtitle || p.title;

// port of _is_boosted (timesag.py:531). P172 deliberately unused.
function isBoosted(claims) {
  for (const c of claims.P21 || []) {
    const v = c?.mainsnak?.datavalue?.value?.id;
    if (v && v !== WD_MALE) return true;
  }
  return Boolean(claims.P91 && claims.P91.length);
}

// port of _boosted_titles (timesag.py:540). Two Action-API calls, both with origin=*.
async function boostedTitles(titles, signal) {
  try {
    const d1 = await getJSON(PAGEPROPS_URL + encodeURIComponent(titles.join("|")), signal);
    const title2qid = new Map();
    for (const p of Object.values(d1?.query?.pages || {})) {
      const qid = p?.pageprops?.wikibase_item;
      if (qid) title2qid.set(p.title, qid);
    }
    if (!title2qid.size) return new Set();
    // the QID list keeps its raw "|" -- encoding it breaks wbgetentities
    const ids = [...new Set(title2qid.values())].join("|");
    const d2 = await getJSON(WBENTITIES_URL + ids, signal);
    const boostedQ = new Set(Object.entries(d2?.entities || {})
      .filter(([, e]) => isBoosted(e.claims || {}))
      .map(([qid]) => qid));
    return new Set([...title2qid].filter(([, qid]) => boostedQ.has(qid)).map(([t]) => t));
  } catch {
    return new Set();   // a Wikidata outage still leaves the default event
  }
}

// port of _fetch_event (timesag.py:560)
async function fetchEvent(key, ctl) {
  const [mm, dd] = key.split("-");
  const signal = ctl.signal;
  try {
    const data = await getJSON(EVENT_URL.replace("{MM}", mm).replace("{DD}", dd), signal);
    const cands = [];
    for (const src of ["selected", "events", "births", "deaths"]) {
      for (const it of data[src] || []) {
        if (it.text && it.year) cands.push([it, src]);
      }
    }
    if (!cands.length) return;
    const ranked = cands.slice().sort((a, b) => scoreItem(b[0], b[1]) - scoreItem(a[0], a[1]));

    // default = best historical event / discovery; fall back to the overall best
    const eventCands = ranked.filter(([, src]) => src === "selected" || src === "events");
    let item = (eventCands[0] || ranked[0])[0];

    // diversity boost: up to 50% chance to feature women / LGBTQ+ figures instead
    const titles = [];
    const titleItem = new Map();
    for (const [it, src] of ranked.slice(0, 10)) {
      if (src !== "births" && src !== "deaths") continue;
      const pg = it.pages || [];
      const nt = pg.length ? pageTitle(pg[0]) : null;
      if (nt && !titleItem.has(nt)) { titles.push(nt); titleItem.set(nt, it); }
    }
    if (titles.length) {
      const boosted = await boostedTitles(titles, signal);
      const diverse = titles.filter((t) => boosted.has(t)).map((t) => titleItem.get(t));
      if (diverse.length && Math.random() < DIVERSITY_CHANCE) item = diverse[0];
    }

    const pages = item.pages || [];
    const url = pages.length
      ? (pages[0]?.content_urls?.desktop?.page
        || "https://en.wikipedia.org/wiki/" + (pages[0]?.titles?.canonical || ""))
      : null;
    state.events[key] = { text: `${item.year} · ${item.text}`, url };
    saveEvents();
    applyEvents();
  } catch {
    // a superseded render is not a failure -- only a real one earns a retry block
    if (!ctl.signal.aborted) failed.add(key);
  } finally {
    inFlight.delete(key);
  }
}

function showEvent(day, entry) {
  day.fact.replaceChildren();
  if (!entry) return;
  if (entry.url) {
    const a = document.createElement("a");
    a.href = entry.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = entry.text;
    day.fact.appendChild(a);
  } else {
    day.fact.textContent = entry.text;
  }
}

function applyEvents() {
  for (const day of state.days) {
    if (!day.date) continue;
    const entry = state.events[mmdd(day.date)];
    if (entry) showEvent(day, entry);
  }
}

function setEvent(day, ctl) {
  const key = mmdd(day.date);
  const entry = state.events[key];
  if (entry) { showEvent(day, entry); return; }
  day.fact.replaceChildren();                       // decorative: blank until it lands
  if (inFlight.has(key) || failed.has(key)) return;
  inFlight.add(key);
  fetchEvent(key, ctl);
}

// ---- payroll lines + copy --------------------------------------------------

// port of _line_for (timesag.py:704)
function lineFor(d, seg) {
  const hours = (seg.hours || "").trim() || DEFAULT_HOURS;
  if (seg.type === "Holiday") return fmtLine(d, HOLIDAY.code, hours, HOLIDAY.f9, HOLIDAY.desc);
  if (seg.type === "Paid time off") return fmtLine(d, SICK.code, hours, SICK.f9, SICK.desc);
  if (seg.type === "Sick") return fmtLine(d, SICKDAY.code, hours, SICKDAY.f9, SICKDAY.desc);
  if (seg.type === "Bank holiday") return "";
  const p = state.projects.find((x) => x.name === seg.proj) || state.projects[0];
  return fmtLine(d, p.code, hours, p.f9, p.name);
}

const buildLines = () => state.days.flatMap(
  (day) => day.segments.map((seg) => lineFor(day.date, seg)).filter(Boolean));

// clipboard needs a user gesture and a secure context; execCommand is the http fallback
function copyWeek() {
  const lines = buildLines();
  const text = lines.join("\r\n");
  const done = () => setStatus(`Copied ${lines.length} line(s) to clipboard`);

  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(done, () => legacyCopy(text, lines.length));
    return;
  }
  legacyCopy(text, lines.length);
}

function legacyCopy(text, count) {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.className = "copy-fallback";
  document.body.appendChild(ta);
  ta.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch { ok = false; }
  if (ok) {
    ta.remove();
    setStatus(`Copied ${count} line(s) to clipboard`);
  } else {
    // last resort: leave the lines on screen so they can be copied by hand
    ta.classList.add("visible");
    setStatus("Copy blocked by the browser — select the text below and copy manually");
  }
}

// ---- week rendering --------------------------------------------------------

// port of render_week (timesag.py:754) + the localStorage load that replaces load_existing
function renderWeek() {
  if (fetchCtl) fetchCtl.abort();
  fetchCtl = new AbortController();
  const ctl = fetchCtl;

  const { week } = isoWeekParts(state.monday);
  const end = addDays(state.monday, 4);
  $("#weeklabel").textContent =
    `Week ${pad2(week)} · ${state.monday.getDate()} – ${end.getDate()} ` +
    `${MONTHS[end.getMonth()]} ${end.getFullYear()}`;
  $("#picker").value = dayKey(state.monday);

  const stored = loadWeek(state.monday);

  state.days.forEach((day, i) => {
    const d = addDays(state.monday, i);
    day.date = d;
    day.name.textContent = WEEKDAYS[i];
    day.dateEl.textContent = ddmmyyyy(d);
    clearSegments(day);

    const saved = stored && stored[dayKey(d)];
    day.start = saved && typeof saved.start === "number" ? saved.start : DAY_START;
    const segs = saved && Array.isArray(saved.segments) && saved.segments.length
      ? saved.segments : [{}];
    for (const s of segs) {
      addSegment(day, {
        hours: s.hours ?? DEFAULT_HOURS,
        type: DAY_TYPES.includes(s.type) ? s.type : "Working",
        proj: s.proj,
      });
    }
    day.segments.forEach((seg) => styleSegment(day, seg));

    setObservance(day);
    setEvent(day, ctl);
  });

  setStatus(stored
    ? `Week ${pad2(week)} · restored from this browser`
    : `Week ${pad2(week)} · new week`);
  layoutAll();
}

// ---- pointer / wheel -------------------------------------------------------

function onPointerDown(e) {
  const axis = e.target.closest(".axis");
  if (!axis) return;
  if (e.target.closest("select, input, button, a")) return;   // the control wins

  const day = state.days.find((d) => d.axis === axis);
  if (!day) return;

  drag = e.target.closest(".seg")
    ? { kind: "start", y: e.clientY, start0: day.start, day, axis, moved: false }
    : { kind: "pan", y: e.clientY, off: state.scrollOffset, axis, moved: false };
  axis.setPointerCapture(e.pointerId);
}

function onPointerMove(e) {
  if (!drag) return;
  const dy = e.clientY - drag.y;
  if (!drag.moved && Math.abs(dy) < 3) return;   // ignore trackpad jitter on a click
  drag.moved = true;

  if (drag.kind === "pan") {
    state.scrollOffset = mod24(drag.off - dy / PX_PER_HOUR);
    layoutAll();
  } else {
    const snapped = Math.round((drag.start0 + dy / PX_PER_HOUR) / MIN_DUR) * MIN_DUR;
    drag.day.start = Math.max(0, Math.min(24, snapped));
    layoutDay(drag.day);
  }
}

function onPointerUp(e) {
  if (!drag) return;
  const { kind, moved, axis } = drag;
  drag = null;
  try { axis.releasePointerCapture(e.pointerId); } catch { /* already released */ }
  if (!moved) return;
  if (kind === "pan") lsSet(LS_OFFSET, String(state.scrollOffset));
  else saveWeek();
}

function onWheel(e) {
  if (!e.target.closest(".axis")) return;
  e.preventDefault();
  state.scrollOffset = mod24(state.scrollOffset + (e.deltaY < 0 ? -1 : 1));
  layoutAll();
  lsSet(LS_OFFSET, String(state.scrollOffset));
}

function onDblClick(e) {
  const box = e.target.closest(".seg");
  if (!box || e.target.closest("select, input, button, a")) return;
  const day = state.days.find((d) => d.segments.some((s) => s.el === box));
  if (!day) return;
  day.start = DAY_START;
  layoutDay(day);
  saveWeek();
}

// ---- boot ------------------------------------------------------------------

async function loadProjects() {
  // docs/ is the Pages site root, so the repo-root projects.json is unreachable
  // from /app/ -- this is the copy that ships with the app.
  try {
    const resp = await fetch("./projects.json");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    if (Array.isArray(data.projects) && data.projects.length) return data.projects;
  } catch { /* fall through */ }
  return FALLBACK_PROJECTS;   // mirrors timesag.py:127
}

async function main() {
  state.projects = await loadProjects();
  state.events = loadEvents();
  const off = Number(lsGet(LS_OFFSET));
  if (Number.isFinite(off) && lsGet(LS_OFFSET) !== null) state.scrollOffset = mod24(off);

  buildColumns();

  $("#prev").addEventListener("click", () => {
    state.monday = addDays(state.monday, -7);
    renderWeek();
  });
  $("#next").addEventListener("click", () => {
    state.monday = addDays(state.monday, 7);
    renderWeek();
  });
  $("#picker").addEventListener("change", (e) => {
    const [y, m, d] = e.target.value.split("-").map(Number);
    if (!y) return;
    state.monday = mondayOf(new Date(y, m - 1, d));
    renderWeek();
  });
  $("#copy").addEventListener("click", copyWeek);

  const week = $("#week");
  week.addEventListener("pointerdown", onPointerDown);
  week.addEventListener("pointermove", onPointerMove);
  week.addEventListener("pointerup", onPointerUp);
  week.addEventListener("pointercancel", onPointerUp);
  week.addEventListener("dblclick", onDblClick);
  week.addEventListener("wheel", onWheel, { passive: false });

  renderWeek();
  if (!storageOK) setStatus("Browser storage is blocked — this week won't be remembered");
}

// guarded so the pure helpers above can be imported and tested under node
if (typeof document !== "undefined") main();
