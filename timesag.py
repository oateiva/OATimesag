#!/usr/bin/env python3
"""Timesag - weekly timesheet writer (calendar day-column view).

Mon-Fri as calendar columns. Each day is a time axis; boxes auto-stack from 08:00,
box height = its hours. Drag vertically to scroll the hour ruler (wraps 24h).
Click a box to edit type / hours / project. All-day = single box.

Writes ./Timesag/<WN>_oat.txt (WN = ISO week number, 2-digit), one line per box:
  110000,DD-MM-YYYY,0,R,0,<code padded 8>,<hours>,T,<f9>,,<desc>
Bank holiday -> no line written.
"""

import json
import os
import random
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import tkinter as tk
from tkinter import messagebox
from datetime import date, timedelta

import customtkinter as ctk
from tkcalendar import Calendar

# ---- constants ----------------------------------------------------------
EMP = "110000"          # employee id (field 1)
DEFAULT_HOURS = "7.40"
OUT_DIR = "Timesag"

HOLIDAY = {"code": "14002", "f9": "94", "desc": "Holiday"}
SICK = {"code": "14004", "f9": "90", "desc": "paid time off (doctor etc)"}
SICKDAY = {"code": "14003", "f9": "95", "desc": "sick"}

DAY_TYPES = ["Working", "Bank holiday", "Holiday", "Paid time off", "Sick"]

TYPE_COLOR = {
    "Working": "#2e9e5b",
    "Holiday": "#3b82f6",
    "Bank holiday": "#6b7280",
    "Paid time off": "#e0902f",
    "Sick": "#dc2626",
}

# calendar timeline
DAY_START = 8.0         # first box begins at 08:00
MIN_DUR = 0.5           # smallest box = half an hour
PX_PER_HOUR = 120       # fixed scale so a 0.5h box (60px) still fits all controls
COL_WIDTH = 250         # fixed column width so full text (project / preview) is visible
# max window width = 5 columns (+card padx) + outer padx + scrollbar/border fudge;
# capping here stops upsizing past what the content needs.
MAXW = 5 * (COL_WIDTH + 12) + 2 * 18 + 30
TARGET_HOURS = 7.4      # a full day; day-total badge is color-coded against this
CANVAS_BG = "#242424"
GRID_COLOR = "#3a3a3a"
LABEL_COLOR = "#8a8f98"

HERE = os.path.dirname(os.path.abspath(__file__))
CARD_BG = "#2b2b2b"     # matches CTkFrame dark fg (canvas icon backgrounds)

# special days / observances (curated, editable in observances.json)
OBS_FILE = os.path.join(HERE, "observances.json")
OBS_SEED = {
    "01-27": [{"name": "Holocaust Remembrance Day", "scope": "world"}],
    "02-04": [{"name": "World Cancer Day", "scope": "world"}],
    "02-11": [{"name": "Women & Girls in Science", "scope": "world"}],
    "03-08": [{"name": "International Women's Day", "scope": "world"}],
    "04-09": [{"name": "Danmarks besættelse (1940)", "scope": "dk"}],
    "04-22": [{"name": "Earth Day", "scope": "world"}],
    "05-05": [{"name": "Danmarks befrielse (1945)", "scope": "dk"}],
    "05-17": [{"name": "Day Against Homophobia (IDAHOBIT)", "scope": "world"}],
    "06-05": [{"name": "World Environment Day", "scope": "world"},
              {"name": "Grundlovsdag", "scope": "dk"}],
    "06-15": [{"name": "Valdemarsdag", "scope": "dk"}],
    "06-28": [{"name": "LGBTQ+ Pride Day", "scope": "world"}],
    "01-06": [{"name": "Día de Reyes", "scope": "es"}],
    "10-12": [{"name": "Fiesta Nacional de España", "scope": "es"}],
    "12-06": [{"name": "Día de la Constitución", "scope": "es"}],
    "12-08": [{"name": "Inmaculada Concepción", "scope": "es"}],
    "04-23": [{"name": "St George's Day", "scope": "uk"}],
    "11-05": [{"name": "Guy Fawkes Night", "scope": "uk"}],
    "12-26": [{"name": "Boxing Day", "scope": "uk"}],
    "01-26": [{"name": "Republic Day", "scope": "in"}],
    "08-15": [{"name": "Independence Day", "scope": "in"}],
    "10-02": [{"name": "Gandhi Jayanti", "scope": "in"}],
    "09-21": [{"name": "International Day of Peace", "scope": "world"}],
    "10-10": [{"name": "World Mental Health Day", "scope": "world"}],
    "11-19": [{"name": "International Men's Day", "scope": "world"}],
    "12-01": [{"name": "World AIDS Day", "scope": "world"}],
    "12-10": [{"name": "Human Rights Day", "scope": "world"}],
}

# "on this day" historical fact (Wikimedia REST, no API key)
EVENT_URL = "https://en.wikipedia.org/api/rest_v1/feed/onthisday/all/{:02d}/{:02d}"
EVENT_CACHE = os.path.join(HERE, "events_cache.json")
HTTP_HEADERS = {"User-Agent": "Timesag/1.0 (oat@eiva.com)"}
LINK_COLOR = "#7fb0ff"
# prioritise discoveries / historical figures when picking the day's fact
SCIENCE_WORDS = ("discover", "invent", "patent", "physic", "chemist", "chemistry",
                 "biolog", "astronom", "mathematic", "scien", "vaccine", "telescope",
                 "dna", "particle", "element", "theorem", "nobel", "medicine",
                 "genetic", "relativity", "evolution", "spacecraft", "orbit")
FIGURE_WORDS = ("physicist", "scientist", "mathematician", "chemist", "biologist",
                "astronomer", "inventor", "engineer", "philosopher", "naturalist",
                "physician", "explorer", "mathematics")
# diversity boost via Wikidata: P21 sex/gender, P91 sexual orientation, P172 ethnic group
WD_MALE = "Q6581097"
DIVERSITY_CHANCE = 0.5   # up to 50% chance to feature a boosted figure when one exists
PAGEPROPS_URL = ("https://en.wikipedia.org/w/api.php?action=query&prop=pageprops"
                 "&ppprop=wikibase_item&format=json&titles=")
WBENTITIES_URL = ("https://www.wikidata.org/w/api.php?action=wbgetentities"
                  "&props=claims&format=json&ids=")


def load_projects():
    path = os.path.join(HERE, "projects.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        projs = data.get("projects", [])
        if projs:
            return projs
    except (OSError, json.JSONDecodeError):
        pass
    return [{"name": "Deep-odo; Olaya", "code": "10353", "f9": "710"}]


def load_observances():
    try:
        with open(OBS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        try:
            with open(OBS_FILE, "w", encoding="utf-8") as f:
                json.dump(OBS_SEED, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
        return dict(OBS_SEED)
    except (OSError, json.JSONDecodeError):
        return {}


def monday_of(d):
    return d - timedelta(days=d.weekday())


def iso_week(d):
    return d.isocalendar()[1]


def out_path(d):
    wn = f"{iso_week(d):02d}"
    return os.path.join(HERE, OUT_DIR, f"{wn}_oat.txt")


def fmt_line(d, code, hours, f9, desc):
    return f"{EMP},{d.strftime('%d-%m-%Y')},0,R,0,{code:<8},{hours},T,{f9},,{desc}"


def hrs_val(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def _mix(c1, c2, t):
    """Blend hex color c1 toward c2 by fraction t (0..1)."""
    a = tuple(int(c1[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(c2[i:i + 2], 16) for i in (1, 3, 5))
    r = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return "#%02x%02x%02x" % r


def darken(c, t):
    return _mix(c, "#000000", t)


def lighten(c, t):
    return _mix(c, "#ffffff", t)


# ---- app ----------------------------------------------------------------
class App:
    def __init__(self, root):
        self.root = root
        root.title("Timesag")
        root.geometry(f"{MAXW}x820")
        root.minsize(760, 600)
        root.maxsize(MAXW, root.winfo_screenheight())   # can't widen past content

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.projects = load_projects()
        self.proj_names = [p["name"] for p in self.projects]
        self.current = monday_of(date.today())
        self.days = []
        self.events = self._load_events()
        self._fetching = set()
        self.observances = load_observances()
        self.scroll_offset = DAY_START - 1.0   # start a bit before the first box
        self._drag = None

        outer = ctk.CTkFrame(root, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=18, pady=16)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(1, weight=1)

        self._build_header(outer)
        self._build_cards(outer)
        self._build_footer(outer)

        self.render_week()

    # -- header ------------------------------------------------------------
    def _build_header(self, parent):
        head = ctk.CTkFrame(parent, corner_radius=14, height=64)
        head.grid(row=0, column=0, sticky="ew")
        head.pack_propagate(False)

        ctk.CTkLabel(head, text="🗓  Timesag",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(side="left", padx=18)

        nav = ctk.CTkFrame(head, fg_color="transparent")
        nav.pack(side="right", padx=14)
        ctk.CTkButton(nav, text="‹", width=38, command=self.prev_week).pack(side="left", padx=3)
        self.week_lbl = ctk.CTkLabel(nav, text="", width=230,
                                     font=ctk.CTkFont(size=14, weight="bold"))
        self.week_lbl.pack(side="left", padx=6)
        ctk.CTkButton(nav, text="›", width=38, command=self.next_week).pack(side="left", padx=3)
        ctk.CTkButton(nav, text="📅  Calendar", width=110,
                      command=self.pick_week).pack(side="left", padx=(10, 0))

    # -- day columns -------------------------------------------------------
    def _build_cards(self, parent):
        body = ctk.CTkScrollableFrame(parent, orientation="horizontal",
                                      fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", pady=(14, 0))

        for i in range(5):  # Mon-Fri as fixed-width columns (scroll if too narrow)
            card = ctk.CTkFrame(body, corner_radius=14, width=COL_WIDTH)
            card.pack(side="left", fill="y", padx=6)
            card.pack_propagate(False)

            obs = ctk.CTkFrame(card, fg_color="transparent", height=48)  # fixed height
            obs.pack(fill="x", padx=8, pady=(4, 0))
            obs.pack_propagate(False)   # constant top area whether empty or not

            day_name = ctk.CTkLabel(card, text="",
                                    font=ctk.CTkFont(size=16, weight="bold"))
            day_name.pack(pady=(10, 0))
            hdr = ctk.CTkFrame(card, fg_color="transparent")
            hdr.pack()
            dot = ctk.CTkLabel(hdr, text="●", font=ctk.CTkFont(size=16))
            dot.pack(side="left", padx=(0, 6))
            day_date = ctk.CTkLabel(hdr, text="", text_color="#9aa0a6",
                                    font=ctk.CTkFont(size=12))
            day_date.pack(side="left")

            total = ctk.CTkLabel(card, text="", corner_radius=11, height=24, width=76,
                                 font=ctk.CTkFont(size=13, weight="bold"))
            total.pack(pady=(6, 4))

            canvas = tk.Canvas(card, bg=CANVAS_BG, highlightthickness=0, bd=0)
            canvas.pack(padx=8, pady=(8, 6), fill="both", expand=True)

            plus = ctk.CTkButton(card, text="＋  add box", height=28)
            plus.pack(padx=10, pady=(0, 8), fill="x")

            event = ctk.CTkLabel(card, text="", justify="left", text_color="#8a8f98",
                                 wraplength=COL_WIDTH - 24,
                                 font=ctk.CTkFont(size=11, slant="italic"))
            event.pack(padx=12, pady=(0, 12), fill="x")

            day = {"card": card, "obs": obs, "day_name": day_name, "day_date": day_date,
                   "dot": dot, "total": total, "canvas": canvas, "plus": plus,
                   "event": event, "event_url": None, "segments": [], "_date": None,
                   "start": DAY_START}
            event.bind("<Button-1>", lambda _e, dd=day: self._open_event(dd))
            plus.configure(command=lambda dd=day: self._add_segment(dd, hours="1.00"))
            canvas.bind("<Configure>", lambda _e, dd=day: self._redraw_day(dd))
            canvas.bind("<ButtonPress-1>", lambda e, dd=day: self._on_press(e, dd))
            canvas.bind("<B1-Motion>", lambda e, dd=day: self._on_motion(e, dd))
            canvas.bind("<ButtonRelease-1>", lambda e, dd=day: self._on_release(e, dd))
            canvas.bind("<MouseWheel>", self._on_wheel)
            self.days.append(day)

    # -- footer ------------------------------------------------------------
    def _build_footer(self, parent):
        foot = ctk.CTkFrame(parent, fg_color="transparent")
        foot.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        self.status = ctk.CTkLabel(foot, text="", text_color="#9aa0a6", anchor="w")
        self.status.pack(side="left")
        ctk.CTkButton(foot, text="💾  Save", width=130, height=40,
                      font=ctk.CTkFont(size=15, weight="bold"),
                      command=self.save).pack(side="right")
        ctk.CTkButton(foot, text="📋  Copy", width=110, height=40,
                      fg_color="#3f3f46", hover_color="#52525b",
                      font=ctk.CTkFont(size=15, weight="bold"),
                      command=self.copy_clipboard).pack(side="right", padx=(0, 10))

    # -- segment data + live widgets --------------------------------------
    def _add_segment(self, day, hours=DEFAULT_HOURS, type_="Working", proj=None):
        seg = {"hours": tk.StringVar(value=hours),
               "type": tk.StringVar(value=type_),
               "proj": tk.StringVar(value=proj or self.proj_names[0])}
        self._make_seg_widgets(day, seg)
        day["segments"].append(seg)
        self._on_seg_type(day, seg)
        return seg

    def _make_seg_widgets(self, day, seg):
        c = day["canvas"]
        frame = ctk.CTkFrame(c, corner_radius=10)
        seg["frame"] = frame
        seg["winid"] = c.create_window(0, 0, anchor="nw", window=frame)

        # compact 2-row layout so a 0.5h box still fits every control
        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x", padx=5, pady=(4, 2))
        seg["remove"] = ctk.CTkButton(
            top, text="✕", width=22, height=22, fg_color="transparent",
            hover_color="#7f1d1d",
            command=lambda dd=day, ss=seg: self._remove_segment(dd, ss))
        seg["remove"].pack(side="right")
        seg["type_om"] = ctk.CTkOptionMenu(
            top, values=DAY_TYPES, variable=seg["type"], height=22,
            command=lambda _v, dd=day, ss=seg: self._on_seg_type(dd, ss))
        seg["type_om"].pack(side="left", fill="x", expand=True)

        # short centered accent underline -> signals the top row is a dropdown
        seg["sep"] = ctk.CTkFrame(frame, height=1, corner_radius=0)
        seg["sep"].pack(padx=48, pady=(3, 4), fill="x")

        mid = ctk.CTkFrame(frame, fg_color="transparent")
        mid.pack(fill="x", padx=5, pady=(0, 4))
        seg["mid"] = mid
        seg["hrs_e"] = ctk.CTkEntry(mid, textvariable=seg["hours"], width=46, height=22,
                                    justify="center")
        seg["hrs_e"].pack(side="left")
        seg["proj_om"] = ctk.CTkOptionMenu(
            mid, values=self.proj_names, variable=seg["proj"], height=22,
            fg_color="#1f6b3f", button_color="#164e2e", button_hover_color="#164e2e")
        seg["preview_var"] = tk.StringVar()
        seg["preview"] = ctk.CTkEntry(mid, textvariable=seg["preview_var"],
                                      state="disabled", justify="center", height=22)

        seg["hours"].trace_add("write", lambda *_a, dd=day: self._redraw_day(dd))
        # drag on a box's blank area moves that day's start time; wheel still pans view
        for wdg in (frame, top, mid):
            wdg.bind("<ButtonPress-1>", lambda e, dd=day: self._on_box_press(e, dd))
            wdg.bind("<B1-Motion>", lambda e, dd=day: self._on_box_motion(e, dd))
            wdg.bind("<ButtonRelease-1>", lambda e, dd=day: self._on_box_release(e, dd))
            wdg.bind("<Double-Button-1>", lambda e, dd=day: self._reset_start(dd))
            wdg.bind("<MouseWheel>", self._on_wheel)

    def _on_seg_type(self, day, seg):
        t = seg["type"].get()
        color = TYPE_COLOR.get(t, "#6b7280")
        seg["frame"].configure(fg_color=color)
        # dropdown = subtly darker shade for a soft raised-button look
        seg["type_om"].configure(fg_color=darken(color, 0.18),
                                 button_color=darken(color, 0.34),
                                 button_hover_color=darken(color, 0.42))
        seg["sep"].configure(fg_color=lighten(color, 0.22))
        seg["hrs_e"].configure(state="disabled" if t == "Bank holiday" else "normal")
        if t == "Working":
            seg["preview"].pack_forget()
            seg["proj_om"].configure(state="normal")
            seg["proj_om"].pack(side="left", fill="x", expand=True, padx=(5, 0))
        else:
            seg["proj_om"].pack_forget()
            if t == "Holiday":
                seg["preview_var"].set(",,Holiday")
            elif t == "Paid time off":
                seg["preview_var"].set(",,paid time off (doctor etc)")
            elif t == "Sick":
                seg["preview_var"].set(",,sick")
            else:
                seg["preview_var"].set("(no line written)")
            seg["preview"].pack(side="left", fill="x", expand=True, padx=(5, 0))
        self._redraw_day(day)

    def _remove_segment(self, day, seg):
        if len(day["segments"]) <= 1:
            return
        day["canvas"].delete(seg["winid"])
        seg["frame"].destroy()
        day["segments"].remove(seg)
        self._redraw_day(day)

    def _clear_segments(self, day):
        for seg in day["segments"]:
            day["canvas"].delete(seg["winid"])
            seg["frame"].destroy()
        day["segments"] = []

    def _px_per_hour(self, canvas):
        return PX_PER_HOUR   # fixed so min 0.5h box always fits its controls

    # -- drawing -----------------------------------------------------------
    def _redraw_all(self):
        for day in self.days:
            self._redraw_day(day)

    # -- special-day observances (top of column) ---------------------------
    def _set_observance(self, day):
        obs = day["obs"]
        for w in obs.winfo_children():
            w.destroy()
        for it in self.observances.get(day["_date"].strftime("%m-%d"), [])[:2]:
            row = ctk.CTkFrame(obs, fg_color="transparent")
            row.pack(fill="x", pady=(2, 0))
            icon = tk.Canvas(row, width=24, height=15, bg=CARD_BG,
                             highlightthickness=0, bd=0)
            icon.pack(side="left", padx=(0, 6))
            {"dk": self._draw_dk, "es": self._draw_es, "uk": self._draw_uk,
             "in": self._draw_in}.get(it.get("scope"), self._draw_world)(icon)
            ctk.CTkLabel(row, text=it["name"], anchor="w", justify="left",
                         wraplength=COL_WIDTH - 54,
                         font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")

    @staticmethod
    def _draw_world(c):
        c.create_oval(1, 1, 14, 14, fill="#2f6fb0", outline="#cfe0f0")
        c.create_line(7, 1, 7, 14, fill="#bcd3ea")
        c.create_line(1, 7, 14, 7, fill="#bcd3ea")
        c.create_oval(3, 4, 7, 8, fill="#3aa76d", outline="")

    @staticmethod
    def _draw_dk(c):
        c.create_rectangle(1, 1, 23, 14, fill="#c60c30", outline="")
        c.create_rectangle(7, 1, 10, 14, fill="white", outline="")   # vertical (offset left)
        c.create_rectangle(1, 6, 23, 9, fill="white", outline="")    # horizontal

    @staticmethod
    def _draw_es(c):
        c.create_rectangle(1, 1, 23, 14, fill="#c60b1e", outline="")   # red bands
        c.create_rectangle(1, 5, 23, 10, fill="#ffc400", outline="")   # yellow middle

    @staticmethod
    def _draw_uk(c):
        c.create_rectangle(1, 1, 23, 14, fill="#012169", outline="")   # blue field
        c.create_line(1, 1, 23, 14, fill="white", width=3)             # white saltire
        c.create_line(1, 14, 23, 1, fill="white", width=3)
        c.create_line(1, 1, 23, 14, fill="#c8102e", width=1)           # red saltire
        c.create_line(1, 14, 23, 1, fill="#c8102e", width=1)
        c.create_rectangle(10, 1, 14, 14, fill="white", outline="")    # white cross
        c.create_rectangle(1, 5, 23, 10, fill="white", outline="")
        c.create_rectangle(11, 1, 13, 14, fill="#c8102e", outline="")  # red cross
        c.create_rectangle(1, 6, 23, 9, fill="#c8102e", outline="")

    @staticmethod
    def _draw_in(c):
        c.create_rectangle(1, 1, 23, 5, fill="#ff9933", outline="")    # saffron
        c.create_rectangle(1, 5, 23, 10, fill="white", outline="")     # white
        c.create_rectangle(1, 10, 23, 14, fill="#138808", outline="")  # green
        c.create_oval(9, 5, 15, 11, outline="#000080")                 # chakra

    # -- "on this day" fact (clickable, prioritises discovery / figure) ----
    def _load_events(self):
        try:
            with open(EVENT_CACHE, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
        # normalise legacy plain-string entries -> {text, url}
        return {k: (v if isinstance(v, dict) else {"text": v, "url": None})
                for k, v in raw.items()}

    def _save_events(self):
        try:
            with open(EVENT_CACHE, "w", encoding="utf-8") as f:
                json.dump(self.events, f, ensure_ascii=False, indent=0)
        except OSError:
            pass

    def _set_event(self, day):
        key = day["_date"].strftime("%m-%d")
        if key in self.events:
            self._show_event(day, self.events[key])
            return
        day["event"].configure(text="…", text_color="#8a8f98", cursor="")
        day["event_url"] = None
        if key not in self._fetching:
            self._fetching.add(key)
            threading.Thread(target=self._fetch_event, args=(key,),
                             daemon=True).start()

    def _show_event(self, day, entry):
        day["event"].configure(text=entry["text"])
        url = entry.get("url")
        day["event_url"] = url
        if url:
            day["event"].configure(text_color=LINK_COLOR, cursor="hand2")
        else:
            day["event"].configure(text_color="#8a8f98", cursor="")

    def _open_event(self, day):
        if day.get("event_url"):
            webbrowser.open(day["event_url"])

    @staticmethod
    def _score_item(item, src):
        # sources near-equal; relevance keywords decide (event OR person can win)
        base = {"selected": 2, "events": 1, "births": 1, "deaths": 1}[src]
        pages = item.get("pages") or []
        desc = pages[0].get("description", "") if pages else ""
        blob = f"{item.get('text', '')} {desc}".lower()
        if any(w in blob for w in SCIENCE_WORDS):
            base += 3
        if any(w in blob for w in FIGURE_WORDS):
            base += 2
        return base

    @staticmethod
    def _page_title(page):
        return ((page.get("titles") or {}).get("normalized")
                or page.get("normalizedtitle") or page.get("title"))

    @staticmethod
    def _get_json(url):
        req = urllib.request.Request(url, headers=HTTP_HEADERS)
        with urllib.request.urlopen(req, timeout=6) as r:
            return json.loads(r.read().decode("utf-8"))

    @staticmethod
    def _is_boosted(claims):
        # gender (non-male) + sexual orientation. P172 (ethnic group) is NOT used:
        # it's present on ~all notable figures, so it's no signal of minority.
        for c in claims.get("P21", []):   # sex or gender != male
            v = c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            if v and v != WD_MALE:
                return True
        return bool(claims.get("P91"))    # sexual orientation recorded

    def _boosted_titles(self, titles):
        """Titles (women / LGBT / ethnic-minority) via Wikidata claims. 2 API calls."""
        try:
            q = urllib.parse.quote("|".join(titles))
            d1 = self._get_json(PAGEPROPS_URL + q)
            title2qid = {}
            for p in d1.get("query", {}).get("pages", {}).values():
                qid = p.get("pageprops", {}).get("wikibase_item")
                if qid:
                    title2qid[p.get("title")] = qid
            if not title2qid:
                return set()
            d2 = self._get_json(WBENTITIES_URL + "|".join(set(title2qid.values())))
            ents = d2.get("entities", {})
            boosted_q = {qid for qid, e in ents.items()
                         if self._is_boosted(e.get("claims", {}))}
            return {t for t, qid in title2qid.items() if qid in boosted_q}
        except (urllib.error.URLError, OSError, ValueError, KeyError):
            return set()

    def _fetch_event(self, key):
        mm, dd = (int(x) for x in key.split("-"))
        try:
            req = urllib.request.Request(EVENT_URL.format(mm, dd), headers=HTTP_HEADERS)
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            # gather + rank candidates (event OR person can win)
            cands = [(it, src) for src in ("selected", "events", "births", "deaths")
                     for it in data.get(src, []) if it.get("text") and it.get("year")]
            if not cands:
                return
            ranked = sorted(cands, key=lambda c: self._score_item(*c), reverse=True)
            # default = best historical event / discovery (keeps events showing);
            # fall back to overall best if the feed had no event-type items
            event_cands = [c for c in ranked if c[1] in ("selected", "events")]
            item = (event_cands[0][0] if event_cands else ranked[0][0])
            # diversity boost: up to 50% chance to feature women / LGBT figures instead
            titles, title_item = [], {}
            for it, src in ranked[:10]:
                if src in ("births", "deaths"):
                    pg = it.get("pages") or []
                    nt = self._page_title(pg[0]) if pg else None
                    if nt and nt not in title_item:
                        titles.append(nt)
                        title_item[nt] = it
            if titles:
                boosted = self._boosted_titles(titles)
                diverse = [title_item[t] for t in titles if t in boosted]
                if diverse and random.random() < DIVERSITY_CHANCE:
                    item = diverse[0]   # highest-ranked boosted figure
            txt = f"{item['year']} · {item['text']}"   # full phrase (label wraps)
            pages = item.get("pages") or []
            url = None
            if pages:
                url = (pages[0].get("content_urls", {}).get("desktop", {}).get("page")
                       or "https://en.wikipedia.org/wiki/"
                       + pages[0].get("titles", {}).get("canonical", ""))
            self.events[key] = {"text": txt, "url": url}
            self._save_events()
            self.root.after(0, self._apply_events)
        except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError):
            pass
        finally:
            self._fetching.discard(key)

    def _apply_events(self):
        for day in self.days:
            if day["_date"] is None:
                continue
            key = day["_date"].strftime("%m-%d")
            if key in self.events:
                self._show_event(day, self.events[key])

    def _update_total(self, day):
        s = sum(hrs_val(seg["hours"].get()) for seg in day["segments"]
                if seg["type"].get() != "Bank holiday")
        num = f"{s:.1f}".rstrip("0").rstrip(".")
        if abs(s - TARGET_HOURS) < 0.01:
            color, text = "#2e9e5b", f"{num} h ✓"
        elif s <= 0:
            color, text = "#6b7280", "0 h"
        elif s < TARGET_HOURS:
            color, text = "#e0902f", f"{num} h"
        else:
            color, text = "#3b82f6", f"{num} h"
        day["total"].configure(text=text, fg_color=color, text_color="white")

    def _redraw_day(self, day):
        self._update_total(day)
        c = day["canvas"]
        w = c.winfo_width()
        h = c.winfo_height()
        if w <= 1 or h <= 1:
            return
        c.delete("ruler")   # keep embedded box windows; only redraw the ruler
        px = self._px_per_hour(c)
        off = self.scroll_offset

        nrows = int(h / px) + 3
        first = int(off) - 1
        for k in range(first, first + nrows):
            y = (k - off) * px
            if -px <= y <= h + px:
                c.create_line(2, y, w, y, fill=GRID_COLOR, tags="ruler")
                c.create_text(6, y + 2, anchor="nw", fill=LABEL_COLOR,
                              font=("Segoe UI", 8), text=f"{k % 24:02d}:00", tags="ruler")

        # position each box (embedded frame) on the timeline
        start = day["start"]
        for seg in day["segments"]:
            dur = max(MIN_DUR, hrs_val(seg["hours"].get()))
            y0 = (start - off) * px
            y1 = (start + dur - off) * px
            c.coords(seg["winid"], 30, y0)
            c.itemconfigure(seg["winid"], width=max(1, w - 36),
                            height=max(1, int(y1 - y0)),
                            state="hidden" if (y1 < 0 or y0 > h) else "normal")
            start += dur

        if day["segments"]:
            first_t = day["segments"][0]["type"].get()
            day["dot"].configure(text_color=TYPE_COLOR.get(first_t, "#6b7280"))

    # -- mouse: drag scrolls the hour ruler --------------------------------
    def _on_press(self, event, day):
        self._drag = {"y": event.y_root, "off": self.scroll_offset}

    def _on_motion(self, event, day):
        if not self._drag:
            return
        dy = event.y_root - self._drag["y"]
        px = self._px_per_hour(day["canvas"])
        self.scroll_offset = (self._drag["off"] - dy / px) % 24
        self._redraw_all()

    def _on_release(self, event, day):
        self._drag = None

    # -- drag a box to move that day's start time --------------------------
    def _on_box_press(self, event, day):
        self._drag = {"y": event.y_root, "start0": day["start"]}

    def _on_box_motion(self, event, day):
        if not self._drag or "start0" not in self._drag:
            return
        dh = (event.y_root - self._drag["y"]) / PX_PER_HOUR
        new = self._drag["start0"] + dh
        new = round(new / MIN_DUR) * MIN_DUR      # snap to half-hours
        day["start"] = max(0.0, min(24.0, new))
        self._redraw_day(day)

    def _on_box_release(self, event, day):
        self._drag = None

    def _reset_start(self, day):
        day["start"] = DAY_START
        self._redraw_day(day)

    def _on_wheel(self, event):
        step = -1 if event.delta > 0 else 1
        self.scroll_offset = (self.scroll_offset + step) % 24
        self._redraw_all()

    # -- file line ---------------------------------------------------------
    def _line_for(self, d, seg):
        t = seg["type"].get()
        hours = seg["hours"].get().strip() or DEFAULT_HOURS
        if t == "Holiday":
            return fmt_line(d, HOLIDAY["code"], hours, HOLIDAY["f9"], HOLIDAY["desc"])
        if t == "Paid time off":
            return fmt_line(d, SICK["code"], hours, SICK["f9"], SICK["desc"])
        if t == "Sick":
            return fmt_line(d, SICKDAY["code"], hours, SICKDAY["f9"], SICKDAY["desc"])
        if t == "Bank holiday":
            return ""
        p = next((p for p in self.projects if p["name"] == seg["proj"].get()),
                 self.projects[0])
        return fmt_line(d, p["code"], hours, p["f9"], p["name"])

    # -- navigation --------------------------------------------------------
    def prev_week(self):
        self.current -= timedelta(days=7)
        self.render_week()

    def next_week(self):
        self.current += timedelta(days=7)
        self.render_week()

    def pick_week(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Pick a date in the week")
        win.geometry("320x340")
        win.transient(self.root)
        win.grab_set()

        cal = Calendar(
            win, selectmode="day", date_pattern="dd-mm-yyyy",
            year=self.current.year, month=self.current.month, day=self.current.day,
            background="#1f2937", foreground="white", headersbackground="#111827",
            headersforeground="#9aa0a6", selectbackground="#3b82f6",
            weekendbackground="#1f2937", weekendforeground="#cbd5e1",
            othermonthforeground="#4b5563", bordercolor="#111827",
            normalbackground="#1f2937", normalforeground="white",
        )
        cal.pack(padx=16, pady=16, fill="both", expand=True)

        def choose():
            self.current = monday_of(cal.selection_get())
            win.destroy()
            self.render_week()

        ctk.CTkButton(win, text="Open week", command=choose).pack(pady=(0, 14))

    # -- render + load -----------------------------------------------------
    def render_week(self):
        wn = iso_week(self.current)
        end = self.current + timedelta(days=4)
        self.week_lbl.configure(
            text=f"Week {wn:02d} · {self.current:%d} – {end:%d %b %Y}")

        for i, day in enumerate(self.days):
            d = self.current + timedelta(days=i)
            day["_date"] = d
            day["day_name"].configure(text=d.strftime("%a"))
            day["day_date"].configure(text=d.strftime("%d-%m-%Y"))
            day["start"] = DAY_START
            self._clear_segments(day)
            self._add_segment(day)  # default single working box
            self._set_observance(day)
            self._set_event(day)

        self.load_existing()
        self._redraw_all()

    def load_existing(self):
        path = out_path(self.current)
        rel = os.path.relpath(path, HERE)
        if not os.path.exists(path):
            self.status.configure(text=f"New week → {rel}")
            return
        try:
            with open(path, encoding="utf-8") as f:
                lines = [ln.strip() for ln in f if ln.strip()]
        except OSError as e:
            self.status.configure(text=f"Read error: {e}")
            return

        by_date = {}
        for ln in lines:
            parts = ln.split(",")
            if len(parts) < 11:
                continue
            by_date.setdefault(parts[1], []).append(parts)

        for day in self.days:
            dstr = day["_date"].strftime("%d-%m-%Y")
            entries = by_date.get(dstr)
            self._clear_segments(day)
            if not entries:
                self._add_segment(day, type_="Bank holiday")
                continue
            for parts in entries:
                code = parts[5].strip()
                hours = parts[6]
                desc = parts[10] if len(parts) > 10 else ""
                if code == HOLIDAY["code"]:
                    self._add_segment(day, hours=hours, type_="Holiday")
                elif code == SICK["code"]:
                    self._add_segment(day, hours=hours, type_="Paid time off")
                elif code == SICKDAY["code"]:
                    self._add_segment(day, hours=hours, type_="Sick")
                else:
                    match = next((p for p in self.projects if p["code"] == code), None)
                    proj = match["name"] if match else (
                        desc if desc in self.proj_names else self.proj_names[0])
                    self._add_segment(day, hours=hours, type_="Working", proj=proj)
        self.status.configure(text=f"Loaded {rel}")

    # -- save / copy -------------------------------------------------------
    def _build_lines(self):
        lines = []
        for day in self.days:
            for seg in day["segments"]:
                ln = self._line_for(day["_date"], seg)
                if ln:
                    lines.append(ln)
        return lines

    def copy_clipboard(self):
        lines = self._build_lines()
        self.root.clipboard_clear()
        self.root.clipboard_append("\r\n".join(lines))
        self.status.configure(text=f"Copied {len(lines)} line(s) to clipboard")

    def save(self):
        lines = self._build_lines()

        path = out_path(self.current)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8", newline="\r\n") as f:
                f.write("\n".join(lines))
                if lines:
                    f.write("\n")
        except OSError as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.status.configure(
            text=f"Saved {len(lines)} line(s) → {os.path.relpath(path, HERE)}")


def main():
    root = ctk.CTk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
