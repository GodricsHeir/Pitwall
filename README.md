<div align="center">

```
██████╗ ██╗████████╗██╗    ██╗ █████╗ ██╗     ██╗
██╔══██╗██║╚══██╔══╝██║    ██║██╔══██╗██║     ██║
██████╔╝██║   ██║   ██║ █╗ ██║███████║██║     ██║
██╔═══╝ ██║   ██║   ██║███╗██║██╔══██║██║     ██║
██║     ██║   ██║   ╚███╔███╔╝██║  ██║███████╗███████╗
╚═╝     ╚═╝   ╚═╝    ╚══╝╚══╝ ╚═╝  ╚═╝╚══════╝╚══════╝
```

### `ANALYTICS`

**Professional F1 Strategy & Telemetry Dashboard**
*Powered by FastF1 · Built with Streamlit · 2018 – 2026*

---

![Python](https://img.shields.io/badge/Python-3.10%2B-3671C6?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.57-E8002D?style=for-the-badge&logo=streamlit&logoColor=white)
![FastF1](https://img.shields.io/badge/FastF1-3.8.3-FF8000?style=for-the-badge)
![Plotly](https://img.shields.io/badge/Plotly-6.7-00D2BE?style=for-the-badge&logo=plotly&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-229971?style=for-the-badge)

</div>

---

## 🏁 What Is PitWall?

**PitWall Analytics** is a full-stack Formula 1 data application that replicates the kind of analysis used by real F1 strategy teams. It pulls live and historical session data directly from the official F1 timing feed via the [FastF1](https://github.com/theOehrly/Fast-F1) library and presents it in a sleek, matte dark dashboard across **8 analysis modules**.

> Every session from **2018 to 2026** — Race, Qualifying, Sprint, Sprint Shootout, FP1/2/3 — is fully supported.

---

## ⚡ Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/yourname/pitwall-analytics.git
cd pitwall-analytics

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

# 3. Install all dependencies
pip install -r requirements.txt

# 4. Launch the app
streamlit run main.py
```

> **First load** will be slow — FastF1 downloads session data from the F1 timing servers and caches it locally in `f1_cache/`. Every subsequent load of the same session is **near-instant**.

---

## 📁 Project Structure

```
pitwall-analytics/
│
├── 🔴  main.py          — App entry point, global CSS, tab routing
├── 🟡  utils.py         — Shared helpers, team colours, data loaders
│
├── ⚪  plot.py          — Pace Trace module
├── ⚪  compare.py       — Head-to-Head comparison module
├── ⚪  teammates.py     — Teammate Duel module
├── ⚪  strategy.py      — Strategy Board + Undercut/Overcut analyser
├── ⚪  engineer.py      — Driver Telemetry deep-dive (20Hz)
├── ⚪  replay.py        — Race Replay engine (canvas map + timing tower)
├── ⚪  race.py          — Session Results & Sector timing matrix
├── ⚪  champion.py      — Championship Standings tracker (WDC + WCC)
│
├── 📄  requirements.txt — Full pinned dependency list
├── 📄  .gitignore
└── 📂  f1_cache/        — Auto-created FastF1 local cache directory
```

---

## 🧩 Feature Modules

### `TAB 1` — 🏆 Results

> **File:** `race.py`

The official session classification with live-timing colour coding, gap calculations, and fastest-lap sector splits.

| Feature | Detail |
|---|---|
| **Classification Table** | Full finishing order with gap-to-leader, interval-to-car-ahead, grid position, points scored |
| **Grid Delta** | `↑` green / `↓` red arrows showing positions gained or lost vs starting grid |
| **Fastest Lap** | `💜 Purple` highlight for the session's fastest lap holder |
| **Sector Matrix** | Per-driver fastest lap broken into Sector 1 / 2 / 3 with live-timing colour coding |
| **Ideal Lap** | Theoretical combined best sectors across all drivers — the lap no one actually set |
| **Colour Coding** | `💜 Purple` = session best · `🟢 Green` = personal best · `🟡 Yellow` = faster than average |

---

### `TAB 2` — 📈 Pace Trace

> **File:** `plot.py`

Lap-by-lap pace visualisation for a single driver or the entire grid.

| Feature | Detail |
|---|---|
| **Race Trace** | Continuous line chart with tyre compound colouring, split by stint |
| **Quali Scatter** | Lap-by-lap scatter with tyre colour coding |
| **Pit Annotations** | Optional vertical dashed lines marking pit-in laps |
| **Driver Metrics** | Best lap · Avg pace · Consistency σ · Total laps · Stints · Finish position |
| **Grid Metrics** | Total drivers tracked · Clean laps · Fastest driver · Compounds used |
| **Stint Table** | Lap range · Laps · Best lap · Avg pace · Σ consistency · Deg rate · Δ vs session best · Pit lap |
| **Delta Waterfall** | Per-lap bar chart showing gap to session best (green = close, red = slow) |

**Tyre Colour Map:**

| Compound | Colour |
|---|---|
| 🔴 SOFT | `#e10600` |
| 🟡 MEDIUM | `#ffd700` |
| ⚪ HARD | `#d0d0d0` |
| 🟢 INTERMEDIATE | `#43b02a` |
| 🔵 WET | `#0082fa` |
| 💖 HYPERSOFT | `#ffb3c6` |
| 💜 ULTRASOFT | `#b300b3` |
| ❤️ SUPERSOFT | `#ff4444` |

---

### `TAB 3` — ⚔️ Head-to-Head

> **File:** `compare.py`

Side-by-side driver comparison with overlaid pace traces, distribution plots, and a direct delta chart.

| Feature | Detail |
|---|---|
| **Driver Cards** | Per-driver metric cards with team colour stripe, best lap delta, avg pace delta, consistency σ, clean laps, finish position |
| **Auto-Include Winner** | Checkbox to automatically add the session winner to the comparison |
| **Race Pace Overlay** | Multi-driver line chart, tyre-coloured, pit laps filtered out |
| **Lap Delta Bar Chart** | Lap-by-lap `DriverA minus DriverB` delta — coloured by who is faster each lap |
| **Violin Distribution** | Full lap-time distribution with box plot and outliers per driver |
| **Stint Comparison Table** | Best lap · Avg · Σ · Deg rate · Δ vs session best · Avg Δ vs session best · Pit lap |
| **Max Drivers** | Up to **6 drivers** simultaneously |

---

### `TAB 4` — 🤝 Teammate Duel

> **File:** `teammates.py` → routes to `compare.py`

Automatically extracts all intra-team pairings for the selected session and fires the full Head-to-Head engine.

| Feature | Detail |
|---|---|
| **Dynamic Extraction** | Reads the official `TeamName` field — works for mid-season driver swaps |
| **Pair Selector** | Dropdown showing all valid pairs e.g. `McLaren: NOR vs PIA` |
| **Full H2H Engine** | Identical output to the Head-to-Head tab — distribution, delta chart, stint table |

---

### `TAB 5` — 🧠 Strategy Board

> **File:** `strategy.py`

Full grid strategy visualisation plus a surgical undercut/overcut analyser.

| Feature | Detail |
|---|---|
| **Gantt Chart** | Horizontal bar chart — every driver's stints laid out by lap number, tyre-coloured, sorted by finish order |
| **Undercut / Overcut Analyser** | Select two drivers and two pit stops — get immediate, stint-end, and race-finish position deltas |
| **Auto-Match Mode** | Toggle to automatically find the driver who gained the most positions from a pit cycle |
| **Similar Pace Filter** | Restricts auto-match to cars within 1.0s average pace (same performance bracket) |
| **Track Status Injection** | Detects if a pit stop occurred under SC / VSC / Red Flag and warns that the time comparison is skewed |
| **Phase Breakdown Chart** | Grouped bar — in-lap time vs out-lap time for each driver to show *where* the time was won |
| **SC / Flag Detection** | Reads `TrackStatus` codes: `4` = SC · `6/7` = VSC · `5` = Red Flag · `2` = Yellow |

---

### `TAB 6` — 🔬 Driver Telemetry

> **File:** `engineer.py`

Raw 20Hz telemetry overlaid across any two laps — the closest thing to actual race engineer data.

| Feature | Detail |
|---|---|
| **Lap Selector** | Choose any lap from the session — defaults to the driver's fastest |
| **4-Panel Telemetry** | Speed · Throttle · Brake · Gear — all on shared x-axis (track distance) |
| **Benchmark Overlay** | Fastest lap shown as a dashed white reference on every panel |
| **DRS Detection** | DRS-open sections highlighted in `🟢 green` on the speed trace |
| **Pit Lap Flagging** | Auto-detects in/out laps and warns that track distance alignment will diverge |
| **Lap History Table** | Full session log with colour-coded sector times |
| **Colour Coding** | `💜 Purple` = session best sector · `🟢 Green` = personal best · `🟡 Yellow` = standard |
| **Ideal Lap Toggle** | Checkbox to append a `THEORETICAL IDEAL` row — sum of the driver's three personal best sectors |

---

### `TAB 7` — 🎬 Race Replay

> **File:** `replay.py`

Lap-by-lap circuit map replay with a live timing tower — rendered fully in-browser, zero external JS dependencies.

| Feature | Detail |
|---|---|
| **Circuit Map** | Pure HTML5 Canvas — sector-coloured track outline with S/F flag marker |
| **Car Dots** | GPS position dots coloured by team, with driver labels |
| **Live Timing Tower** | Position · Driver (team colour) · Grid Δ · Interval · Tyre history · Tyre age |
| **Interval Trend** | `↓` closing / `↑` losing — colour-coded green/red |
| **Playback Controls** | Play / Pause · Reset · Lap slider · Speed selector (0.5× / 1× / 2× / 4×) |
| **Status Bar** | Track status (Clear / Yellow / SC / Red Flag) · Air temp · Track temp · Rain flag |
| **Local Yellow Flags** | Per-sector yellow flag banner when flag data is available |
| **Map Tints** | Background tint changes: `gold` under SC/VSC · `red` under Red Flag |
| **Lapped Car Detection** | Drivers > 1 lap behind shown as faded dots marked `+NL` |
| **Two-Phase Load** | Lap data (fast) and circuit telemetry (single lap only) loaded and cached separately |

> **Note:** GPS dot positions require `pos_data` to be available in FastF1 for the session. Most sessions from 2019 onwards have this. Older sessions will show an empty track with the timing tower still fully functional.

---

### `TAB 8` — 🏆 Championship Standings

> **File:** `champion.py`

Full WDC and WCC standings tracker that crawls the season up to the currently selected round.

| Feature | Detail |
|---|---|
| **WDC Table** | Pos · Pos Δ · Driver · Team · Points This Race · Total Points · Gap to Leader · Gap to Ahead · Max Deficit |
| **WCC Table** | Same structure but aggregated by Constructor |
| **Points Progression Chart** | Cumulative points line chart — each driver/team as a separate line, coloured by team |
| **Sprint Support** | Automatically detects sprint weekends and adds sprint points separately |
| **Driver Filtering** | Select up to 6 drivers/constructors to isolate on the progression chart |
| **Max Deficit Tracking** | Shows the largest points gap each entity faced at any point in the season |
| **Partial Points** | Handles half-points (e.g. 2021 Belgian GP) correctly — displayed as `12.5` not `12` |
| **Colour Coding** | `🟢 Green` = points scored this round · `💜 Purple` / team colour = driver/team name stripe |

---

## 🎨 Design System

PitWall uses a custom CSS theme applied globally via `main.py`.

### Colour Palette

| Token | Hex | Usage |
|---|---|---|
| `--bg` | `#0d0d0f` | App background |
| `--surface` | `#13131a` | Cards, panels |
| `--card` | `#1a1a24` | Metric containers |
| `--border` | `#2a2a38` | All borders |
| `--accent` | `#e8002d` | Primary red — buttons, highlights, section chips |
| `--accent2` | `#ff6b35` | Section sub-headers |
| `--muted` | `#555568` | Disabled / secondary text |
| `--text` | `#e8e8f0` | Primary text |
| `--text-dim` | `#8888a0` | Labels, captions |
| `--green` | `#00d47e` | Positive deltas, fastest times |
| `--yellow` | `#ffd700` | Warnings, session best sectors, leader |
| `--blue` | `#4db8ff` | Sector 2 on circuit map |

### Team Colour Palette

| Team | Hex | Swatch |
|---|---|---|
| Red Bull Racing | `#3671C6` | 🔵 |
| Ferrari | `#E8002D` | 🔴 |
| Mercedes | `#00D2BE` | 🩵 |
| McLaren | `#FF8000` | 🟠 |
| Aston Martin | `#229971` | 🟢 |
| Alpine | `#0093CC` | 🔵 |
| Williams | `#00A0DD` | 🔵 |
| Haas | `#B6BABD` | ⚪ |
| Kick Sauber | `#52E252` | 🟢 |
| RB | `#6692FF` | 🟣 |
| AlphaTauri | `#5E8FAA` | 🩵 |
| Alfa Romeo | `#C92D4B` | 🔴 |
| Renault | `#FFF500` | 🟡 |

### Typography

| Context | Font |
|---|---|
| All UI text | `Exo 2` (Google Fonts) — weights 300 / 400 / 600 / 700 / 900 |
| Numbers, timing, code | `JetBrains Mono` (Google Fonts) |
| Replay fallback | `system-ui` (no CDN required in iframe) |

---

## 📦 Dependencies

### Core

| Package | Version | Purpose |
|---|---|---|
| `streamlit` | `1.57.0` | Web framework & UI components |
| `fastf1` | `3.8.3` | Official F1 timing data API |
| `pandas` | `2.3.3` | All data manipulation |
| `numpy` | `2.4.6` | Numerical computation |
| `plotly` | `6.7.0` | All interactive charts |
| `matplotlib` | `3.10.9` | FastF1 internal dependency |

### Data & Caching

| Package | Version | Purpose |
|---|---|---|
| `requests-cache` | `1.3.2` | HTTP response caching (used by FastF1) |
| `pyarrow` | `24.0.0` | Parquet serialisation for FastF1 cache |
| `scipy` | `1.17.1` | Signal processing in FastF1 telemetry |
| `timple` | `0.1.8` | Timedelta formatting (FastF1 dependency) |
| `RapidFuzz` | `3.14.5` | Fuzzy string matching for event lookup |

### Infrastructure

| Package | Version | Purpose |
|---|---|---|
| `uvicorn` | `0.47.0` | ASGI server (Streamlit backend) |
| `watchdog` | `6.0.0` | File system watcher for hot-reload |
| `websockets` | `16.0` | Streamlit live connection |
| `signalrcore` | `1.0.2` | FastF1 live timing websocket |

> Full pinned list with all transitive dependencies is in `requirements.txt`.

---

## ⚙️ Configuration

### FastF1 Cache

FastF1 caches downloaded session data locally. The cache directory is created automatically:

```
pitwall-analytics/
└── f1_cache/        ← auto-created on first run
    ├── 2024/
    │   └── Bahrain Grand Prix/
    │       ├── Race/
    │       └── Qualifying/
    └── ...
```

**Cache location is set in `main.py`:**
```python
CACHE_DIR = "f1_cache"
fastf1.Cache.enable_cache(CACHE_DIR)
```

You can change this to an absolute path or an SSD location for better performance on large sessions.

### Streamlit Cache TTL

All data-loading functions use `@st.cache_data(ttl=86400)` — data is cached for **24 hours** per session. To force a refresh, clear Streamlit's cache from the top-right menu inside the app, or delete the `f1_cache/` directory.

---

## ⚠️ Known Limitations

### Data Availability

| Limitation | Detail |
|---|---|
| **Telemetry cutoff** | 20Hz telemetry (Driver Telemetry tab) is only available from **2018 onwards**. The app blocks these tabs for older seasons with a warning. |
| **GPS / pos_data** | Car position dots in the Race Replay require `pos_data`, which FastF1 provides for most sessions from **2019+**. Older sessions will show the track outline with no car dots — the timing tower still works. |
| **Live sessions** | FastF1 does not support truly live in-race streaming. Data for the current or most recent session becomes available 30–60 minutes after the session ends. |
| **Sprint data** | Sprint weekend formats changed across seasons. The Championship tracker detects format automatically, but older sprint formats (pre-2022) may not yield sprint points. |
| **Practice sessions** | FP sessions do not have Position data, so gap/interval calculations in the Replay tower will be empty for FP. |

### Performance

| Limitation | Detail |
|---|---|
| **First load time** | A full race session with telemetry can take **2–5 minutes** to download on the first load. All subsequent loads are instant from the local cache. |
| **Race Replay load** | The Replay engine loads lap data fast (`telemetry=False`) but then fetches the circuit outline via a single fastest-lap telemetry call — adds ~30s on first load. |
| **Championship tab** | Compiling a full season crawls ~24 races at ~1s each. The first load takes up to **30 seconds** — results are then cached for 1 hour. |
| **Replay without GPS** | If `pos_data` is unavailable, car dots are skipped but the timing tower and track outline render normally. |

### Browser / UI

| Limitation | Detail |
|---|---|
| **Race Replay CDN** | The replay engine uses pure HTML5 Canvas with **no external libraries** to avoid Streamlit iframe CDN restrictions. Plotly is not used in the replay. |
| **Replay payload size** | Large races (~80 laps, 20 drivers) produce a JSON payload of ~1–2 MB. This is within `components.html` limits but may be slow on very old hardware. |
| **Mobile** | The layout is designed for widescreen (1280px+). The app is technically usable on tablet but not optimised for mobile viewports. |

---

## 🛠️ Troubleshooting

### `DataNotLoadedError: pos_data`
FastF1's `pos_data` property raises an exception (not `AttributeError`) when telemetry is not loaded — `getattr` with a default won't catch it. This is handled in `replay.py` with an explicit `try/except` block. If you see this error in another module, wrap the access:
```python
try:
    pos_data = session.pos_data
except Exception:
    pos_data = {}
```

### `Plotly is not defined` in Replay
This was a Streamlit iframe CDN race condition. The Replay module uses **pure Canvas** — no Plotly — so this error should never appear. If it does, you are running an older version of `replay.py`.

### Session data not found
```
No lap time data found for this session.
```
This usually means the session hasn't been run yet, or FastF1 hasn't indexed it. Check [FastF1's data availability notes](https://docs.fastf1.dev/). For recent sessions, wait ~1 hour after the session ends.

### Cache corruption
If you get unexpected errors after a FastF1 update, clear the cache:
```bash
rm -rf f1_cache/
```

### Streamlit version mismatch
The app is built against **Streamlit 1.57.0**. Some UI elements (`st.fragment`, `st.html`, native tab styling) may not work on older versions. Always install from `requirements.txt`:
```bash
pip install -r requirements.txt --upgrade
```

---

## 📐 Architecture Overview

```
main.py  (entry point + global CSS + tab router)
    │
    ├── Tab 0 ──► race.py        (Results + Sector Matrix)
    ├── Tab 1 ──► plot.py        (Pace Trace)
    ├── Tab 2 ──► compare.py     (Head-to-Head)
    ├── Tab 3 ──► teammates.py ──► compare.py
    ├── Tab 4 ──► strategy.py    (Gantt + Undercut Analyser)
    ├── Tab 5 ──► engineer.py    (20Hz Telemetry)
    ├── Tab 6 ──► replay.py      (Canvas Replay + Tower)
    └── Tab 7 ──► champion.py   (WDC + WCC Standings)
              │
              └── All modules import from utils.py
                  (format_time, driver_color, safe_load_session,
                   filter_clean_laps, extract_pit_map, TYRE_COLORS,
                   PLOTLY_THEME, section_header, no_data_error)
```

**Data flow per module:**
```
FastF1 API → session.load() → session.laps / session.results / session.pos_data
    ↓
safe_load_session() → filter_clean_laps() → apply_tyre_labels()
    ↓
Plotly charts / Canvas map / HTML tables → Streamlit components
```

---

## 📜 License

MIT License — do whatever you want, don't blame me if your strategy call loses the race.

---

<div align="center">

**Built for the love of the sport.**
*Not affiliated with Formula 1, the FIA, or any constructor.*

`FastF1` data is sourced from the official F1 timing feed and is subject to F1's terms of use.

</div>
