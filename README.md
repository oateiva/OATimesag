# 🗓 Timesag

A modern, calendar-style weekly timesheet app for Windows, built with Python + [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter). Each day is a time axis you fill with coloured "boxes" (working, holiday, sick, …); Timesag writes them out in the exact fixed-width format the payroll system expects.

It also makes the week a little more interesting: every day shows an **on-this-day historical fact** (with an inclusive selection process, see below) and any **special observance** (world / Danish / Spanish / British / Indian) with a hand-drawn flag.

---

## Features

- **Calendar day columns (Mon–Fri).** Each day is a vertical time axis with an hour ruler behind it.
- **Duration boxes.** Boxes auto-stack from a start time; each box's height is proportional to its hours (`120 px/hour`, minimum box = 0.5 h so all controls always fit).
- **Edit in place.** Every box carries its own controls: a **type** dropdown (coloured to match the type), an **hours** field, and a **project** selector (Working only) or a live preview of what will be written (Holiday / Sick / etc.).
- **Add / remove.** `＋ add box` splits a day into several entries; `✕` removes one.
- **Draggable start time.** Drag a box to shift that day's whole stack to a new start (snaps to half-hours); double-click to reset to 08:00. Drag the empty canvas (or scroll-wheel) to pan the hour ruler, which wraps around 24 h.
- **Per-day total badge.** A colour-coded pill shows the summed hours vs a 7.4 h target (green = exact ✓, amber = under, blue = over, grey = none).
- **On-this-day fact.** A clickable Wikipedia link at the bottom of each column (see *Inclusive selection* below).
- **Special days on top.** World 🌍, Danish 🇩🇰, Spanish 🇪🇸, British 🇬🇧 and Indian 🇮🇳 observances, each with a drawn flag icon.
- **Week navigation.** Prev / Next buttons and a calendar picker.
- **Fixed max width.** The window can't be widened past the content, so no layout jitter.

---

## Running

```
python timesag.py
```

Requirements (install once):

```
pip install customtkinter tkcalendar
```

The app writes its timesheet files into a `Timesag/` subfolder next to the script.

---

## Web version

The same interface runs in the browser, published from this repo's `docs/` folder with GitHub Pages:

| | |
|---|---|
| Landing page | <https://oateiva.github.io/OATimesag/> |
| **The app** | <https://oateiva.github.io/OATimesag/app/> |

It is the desktop UI with two differences, both forced by Pages being static:

- **Copy only.** There is no Save button — nothing on a static host to write a file to. Press
  **📋 Copy** to put the whole week's lines on the clipboard.
- **The week lives in your browser.** Every edit auto-saves to `localStorage` under
  `timesag:<ISO year>-W<NN>`, so reopening a week restores it. That replaces reading back
  `Timesag/<WN>_oat.txt`. Clearing site data clears the weeks.

Everything else is the same: five Mon–Fri columns, draggable boxes, the hour ruler, the day-total
badge, observances, and the on-this-day fact (fetched live from Wikimedia and cached per browser,
with the same inclusive 50 % selection described below).

To run it locally, serve `docs/` — opening the files directly with `file://` will not work, because
ES modules and `fetch` are blocked there:

```
python -m http.server 8000 --directory docs
```

Then open <http://localhost:8000/app/>.

> `docs/app/projects.json` is a **copy** of the root `projects.json` — GitHub Pages serves only
> `docs/`, so the root file is not reachable from the published app. Edit both, or the web version
> will show stale projects.

---

## Output format

Saving a week writes `Timesag/<WN>_oat.txt`, where `<WN>` is the 2-digit ISO week number. One line **per box**, comma-separated:

```
110000,DD-MM-YYYY,0,R,0,<code padded to 8>,<hours>,T,<f9>,,<description>
```

| Day type       | code    | f9  | description                    | line written? |
|----------------|---------|-----|--------------------------------|:-------------:|
| Working        | project | proj| project name                   | ✅ |
| Holiday        | `14002` | 94  | `Holiday`                      | ✅ |
| Sick           | `14003` | 95  | `sick`                         | ✅ |
| Paid time off  | `14004` | 90  | `paid time off (doctor etc)`   | ✅ |
| Bank holiday   | —       | —   | —                              | ❌ (no line) |

Example lines:

```
110000,19-01-2026,0,R,0,10353   ,7.40,T,710,,Deep-odo; Olaya
110000,29-12-2025,0,R,0,14002   ,7.40,T,94,,Holiday
110000,29-06-2026,0,R,0,14004   ,7.40,T,90,,paid time off (doctor etc)
```

A day split into several boxes produces several lines with the same date. Re-opening a week reconstructs the boxes from the file.

### `projects.json`

Working-day projects live in `projects.json` and appear in the project dropdown:

```json
{ "projects": [ { "name": "Deep-odo; Olaya", "code": "10353", "f9": "710" } ] }
```

Add your own entries with their `code` (field 6) and `f9` (field 9).

---

## On-this-day fact — inclusive selection

Each day shows one historical fact, fetched from the free **Wikimedia "On This Day"** REST feed (`.../feed/onthisday/all/MM/DD`, no API key). Results are cached in `events_cache.json`, so repeat views and offline use are instant. Every fact is a clickable link to its Wikipedia article.

The item shown for a date is chosen once (then frozen in the cache) by this process:

**1. Score every candidate.** The feed returns `selected`, `events`, `births` and `deaths`. Each candidate gets a relevance score:

- a small base by source (`selected` slightly ahead of `events`/`births`/`deaths`);
- **+3** if its text/description matches *discovery/science* keywords (discover, invent, physics, chemistry, astronomy, Nobel, vaccine, DNA, …);
- **+2** if it matches *figure* keywords (physicist, scientist, mathematician, inventor, …).

**2. Default to an event / discovery.** The highest-scoring **event** (from `selected`/`events`) is the baseline pick — so genuine historical events and scientific discoveries keep appearing, and well-known figures still surface through events *about* them (e.g. *"Einstein sends the special-relativity paper"*).

**3. Inclusive boost — up to a 50 % chance.** Among the top-ranked **people** of the day, Timesag looks up each one's [Wikidata](https://www.wikidata.org) claims (two extra, cached API calls):

- `P21` **sex or gender** — flagged when it is **not male** (women, non-binary, …);
- `P91` **sexual orientation** — flagged when present (recorded orientation, i.e. LGBTQ+ figures).

If at least one such figure exists that day, a **coin flip (50 %)** decides whether to feature the highest-ranked of them instead of the default event. So historically under-represented figures appear on **up to half** of the days that have one, while the other half (and every day without one) still shows a historical event or discovery.

> **Why not ethnic group?** Wikidata's `P172` (ethnic group) is populated for *almost every* notable figure — Newton and Einstein included — so its mere presence is no signal of a minority and would flag nearly everyone. Boosting it would defeat the 50 % balance, so it is deliberately **not** used. Boosting specific ethnic minorities would need a curated list of ethnic-group IDs to match against.

The whole feature is decorative: if there's no network (and no cache yet) the app is fully usable and the fact simply stays blank. It never touches the timesheet output.

---

## Special-day observances

The top of each column shows any observance for that date, from a curated, editable `observances.json`:

```json
{ "06-05": [ { "name": "World Environment Day", "scope": "world" },
             { "name": "Grundlovsdag", "scope": "dk" } ] }
```

`scope` selects the drawn flag icon:

| scope   | icon        | examples |
|---------|-------------|----------|
| `world` | 🌍 globe     | Women's Day, World Cancer Day, Pride Day, Human Rights Day |
| `dk`    | 🇩🇰 Dannebrog | Grundlovsdag, Valdemarsdag, occupation/liberation |
| `es`    | 🇪🇸 flag      | Fiesta Nacional, Día de la Constitución, Reyes |
| `uk`    | 🇬🇧 Union Jack | St George's Day, Guy Fawkes Night, Boxing Day |
| `in`    | 🇮🇳 tricolour  | Republic Day, Independence Day, Gandhi Jayanti |

Flags are **drawn on a small canvas** (not emoji), so they render identically on Windows. The file is seeded on first run with a starter set of fixed-date observances; add or edit entries freely (keyed `MM-DD`). Movable feasts (e.g. Easter) and volatile dates (royal birthdays) are left out by default.

---

## Files

| File | Purpose |
|------|---------|
| `timesag.py` | The application |
| `projects.json` | Working-day projects (name / code / f9) |
| `observances.json` | Curated special days (auto-seeded, editable) |
| `events_cache.json` | Cached on-this-day facts (auto-generated) |
| `Timesag/<WN>_oat.txt` | The weekly timesheet output |
| `docs/index.html` | Landing page published on GitHub Pages |
| `docs/app/` | The browser version (`index.html`, `styles.css`, `data.js`, `app.js`, `projects.json`) |

---

## Notes & limitations

- Only **Mon–Fri** are shown, so weekend observances/facts don't appear.
- The Union Jack is a small-canvas approximation (proper counterchanged diagonals aren't practical at 24 px).
- The web version needs a network connection only for the on-this-day fact; without one the
  fact line stays blank and everything else works.
- Box **start time** is a display convenience — it isn't stored in the timesheet (the format has no start-time field), so it resets to 08:00 on reload.
