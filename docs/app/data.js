// Constants ported 1:1 from timesag.py (lines 29-115). No DOM access here.
// The payroll output format depends on these values -- keep them in sync.

export const EMP = "110000";            // employee id (field 1)
export const DEFAULT_HOURS = "7.40";

export const HOLIDAY = { code: "14002", f9: "94", desc: "Holiday" };
export const SICK = { code: "14004", f9: "90", desc: "paid time off (doctor etc)" };
export const SICKDAY = { code: "14003", f9: "95", desc: "sick" };

export const DAY_TYPES = ["Working", "Bank holiday", "Holiday", "Paid time off", "Sick"];

export const TYPE_COLOR = {
  "Working": "#2e9e5b",
  "Holiday": "#3b82f6",
  "Bank holiday": "#6b7280",
  "Paid time off": "#e0902f",
  "Sick": "#dc2626",
};

// preview text shown instead of the project dropdown for non-working types
export const TYPE_PREVIEW = {
  "Holiday": ",,Holiday",
  "Paid time off": ",,paid time off (doctor etc)",
  "Sick": ",,sick",
  "Bank holiday": "(no line written)",
};

// calendar timeline
export const DAY_START = 8.0;      // first box begins at 08:00
export const MIN_DUR = 0.5;        // smallest box = half an hour
export const PX_PER_HOUR = 120;    // fixed scale so a 0.5h box still fits all controls
export const COL_WIDTH = 250;      // fixed column width so full text is visible
export const TARGET_HOURS = 7.4;   // a full day; day-total badge is colour-coded against this
export const GRID_COLOR = "#3a3a3a";
export const LABEL_COLOR = "#8a8f98";
export const LINK_COLOR = "#7fb0ff";

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"];

// used when docs/app/projects.json can't be fetched (offline, file://, 404)
export const FALLBACK_PROJECTS = [
  { name: "Deep-odo; Olaya", code: "10353", f9: "710" },
];

// special days / observances. observances.json is gitignored, so the seed IS the data.
export const OBS_SEED = {
  "01-27": [{ name: "Holocaust Remembrance Day", scope: "world" }],
  "02-04": [{ name: "World Cancer Day", scope: "world" }],
  "02-11": [{ name: "Women & Girls in Science", scope: "world" }],
  "03-08": [{ name: "International Women's Day", scope: "world" }],
  "04-09": [{ name: "Danmarks besættelse (1940)", scope: "dk" }],
  "04-22": [{ name: "Earth Day", scope: "world" }],
  "05-05": [{ name: "Danmarks befrielse (1945)", scope: "dk" }],
  "05-17": [{ name: "Day Against Homophobia (IDAHOBIT)", scope: "world" }],
  "06-05": [{ name: "World Environment Day", scope: "world" },
            { name: "Grundlovsdag", scope: "dk" }],
  "06-15": [{ name: "Valdemarsdag", scope: "dk" }],
  "06-28": [{ name: "LGBTQ+ Pride Day", scope: "world" }],
  "01-06": [{ name: "Día de Reyes", scope: "es" }],
  "10-12": [{ name: "Fiesta Nacional de España", scope: "es" }],
  "12-06": [{ name: "Día de la Constitución", scope: "es" }],
  "12-08": [{ name: "Inmaculada Concepción", scope: "es" }],
  "04-23": [{ name: "St George's Day", scope: "uk" }],
  "11-05": [{ name: "Guy Fawkes Night", scope: "uk" }],
  "12-26": [{ name: "Boxing Day", scope: "uk" }],
  "01-26": [{ name: "Republic Day", scope: "in" }],
  "08-15": [{ name: "Independence Day", scope: "in" }],
  "10-02": [{ name: "Gandhi Jayanti", scope: "in" }],
  "09-21": [{ name: "International Day of Peace", scope: "world" }],
  "10-10": [{ name: "World Mental Health Day", scope: "world" }],
  "11-19": [{ name: "International Men's Day", scope: "world" }],
  "12-01": [{ name: "World AIDS Day", scope: "world" }],
  "12-10": [{ name: "Human Rights Day", scope: "world" }],
};

// Flags drawn at 24x15, same primitives/coordinates as the tk.Canvas versions
// (_draw_world / _draw_dk / _draw_es / _draw_uk / _draw_in, timesag.py:427-463).
const SVG = (body) =>
  `<svg class="flag" viewBox="0 0 24 15" width="24" height="15" aria-hidden="true">${body}</svg>`;

export const FLAG_SVG = {
  world: SVG(
    `<circle cx="7.5" cy="7.5" r="6.5" fill="#2f6fb0" stroke="#cfe0f0"/>` +
    `<path d="M7 1V14M1 7.5H14" stroke="#bcd3ea" stroke-width="1"/>` +
    `<ellipse cx="5" cy="6" rx="2" ry="2" fill="#3aa76d"/>`),
  dk: SVG(
    `<rect x="1" y="1" width="22" height="13" fill="#c60c30"/>` +
    `<rect x="7" y="1" width="3" height="13" fill="#fff"/>` +
    `<rect x="1" y="6" width="22" height="3" fill="#fff"/>`),
  es: SVG(
    `<rect x="1" y="1" width="22" height="13" fill="#c60b1e"/>` +
    `<rect x="1" y="5" width="22" height="5" fill="#ffc400"/>`),
  uk: SVG(
    `<rect x="1" y="1" width="22" height="13" fill="#012169"/>` +
    `<path d="M1 1L23 14M1 14L23 1" stroke="#fff" stroke-width="3"/>` +
    `<path d="M1 1L23 14M1 14L23 1" stroke="#c8102e" stroke-width="1"/>` +
    `<rect x="10" y="1" width="4" height="13" fill="#fff"/>` +
    `<rect x="1" y="5" width="22" height="5" fill="#fff"/>` +
    `<rect x="11" y="1" width="2" height="13" fill="#c8102e"/>` +
    `<rect x="1" y="6" width="22" height="3" fill="#c8102e"/>`),
  in: SVG(
    `<rect x="1" y="1" width="22" height="4" fill="#ff9933"/>` +
    `<rect x="1" y="5" width="22" height="5" fill="#fff"/>` +
    `<rect x="1" y="10" width="22" height="4" fill="#138808"/>` +
    `<circle cx="12" cy="8" r="3" fill="none" stroke="#000080"/>`),
};

// -- "on this day" fact -------------------------------------------------------
export const EVENT_URL =
  "https://en.wikipedia.org/api/rest_v1/feed/onthisday/all/{MM}/{DD}";
// The Action API needs &origin=* for browser CORS; the REST feed above does not.
export const PAGEPROPS_URL =
  "https://en.wikipedia.org/w/api.php?action=query&prop=pageprops" +
  "&ppprop=wikibase_item&format=json&origin=*&titles=";
export const WBENTITIES_URL =
  "https://www.wikidata.org/w/api.php?action=wbgetentities" +
  "&props=claims&format=json&origin=*&ids=";
export const FETCH_TIMEOUT = 6000;   // matches urlopen(timeout=6)

// prioritise discoveries / historical figures when picking the day's fact
export const SCIENCE_WORDS = ["discover", "invent", "patent", "physic", "chemist", "chemistry",
  "biolog", "astronom", "mathematic", "scien", "vaccine", "telescope",
  "dna", "particle", "element", "theorem", "nobel", "medicine",
  "genetic", "relativity", "evolution", "spacecraft", "orbit"];
export const FIGURE_WORDS = ["physicist", "scientist", "mathematician", "chemist", "biologist",
  "astronomer", "inventor", "engineer", "philosopher", "naturalist",
  "physician", "explorer", "mathematics"];
export const SRC_BASE = { selected: 2, events: 1, births: 1, deaths: 1 };

// diversity boost via Wikidata: P21 sex/gender, P91 sexual orientation.
// P172 (ethnic group) is NOT used: present on ~all notable figures, so no signal.
export const WD_MALE = "Q6581097";
export const DIVERSITY_CHANCE = 0.5;

// -- localStorage keys --------------------------------------------------------
export const LS_WEEK = (isoYear, week) =>
  `timesag:${isoYear}-W${String(week).padStart(2, "0")}`;
export const LS_EVENTS = "timesag:events";
export const LS_OFFSET = "timesag:offset";
export const STORE_VERSION = 1;
