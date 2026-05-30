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

**PitWall Analytics** is a full-stack Formula 1 data application that replicates the kind of analysis used by real F1 strategy teams. It pulls live and historical session data directly from the official F1 timing feed via the [FastF1](https://github.com/theOehrly/Fast-F1) library and presents it in a sleek, matte dark dashboard across **9 analysis modules**.

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
├── ⚪  race.py          — Session Results & Sector timing matrix
├── ⚪  champion.py      — Championship Standings tracker (WDC + WCC)
├── ⚪  plot.py          — Pace Trace module
├── ⚪  compare.py       — Head-to-Head comparison module
├── ⚪  teammates.py     — Teammate Duel module
├── ⚪  strategy.py      — Strategy Board + Risk Profile + Undercut analyser
├── ⚪  engineer.py      — Driver Telemetry deep-dive (20Hz)
├── ⚪  replay.py        — Race Replay engine (canvas map + timing tower)
├── ⚪  circuit.py       — Track Map, Action Zones, and 3D Topography
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
| --- | --- |
| **Classification Table** | Full finishing order with gap-to-leader, interval-to-car-ahead, grid position, points scored |
| **Grid Delta** | `↑` green / `↓` red arrows showing positions gained or lost vs starting grid |
| **Fastest Lap** | `💜 Purple` highlight for the session's fastest lap holder |
| **Sector Matrix** | Per-driver fastest lap broken into Sector 1 / 2 / 3 with live-timing colour coding |
| **Ideal Lap** | Theoretical combined best sectors across all drivers — the lap no one actually set |
| **Colour Coding** | `💜 Purple` = session best · `🟢 Green` = personal best · `🟡 Yellow` = faster than average |

---

### `TAB 2` — 🏅 Championship Standings

> **File:** `champion.py`

Full WDC and WCC standings tracker that crawls the season up to the currently selected round.

| Feature | Detail |
| --- | --- |
| **WDC & WCC Tables** | Pos · Pos Δ · Driver/Team · Points This Race · Total Points · Gap to Leader · Gap to Ahead · Max Deficit |
| **Points Progression** | Cumulative points line chart — each driver/team as a separate line, coloured by team |
| **Sprint Support** | Automatically detects sprint weekends and adds sprint points separately |
| **Driver Filtering** | Select up to 6 drivers/constructors to isolate on the progression chart |
| **Max Deficit Tracking** | Shows the largest points gap each entity faced at any point in the season |

---

### `TAB 3` — 📈 Pace Trace

> **File:** `plot.py`

Lap-by-lap pace visualisation for a single driver or the entire grid.

| Feature | Detail |
| --- | --- |
| **Race Trace** | Continuous line chart with tyre compound colouring, split by stint |
| **Quali Scatter** | Lap-by-lap scatter with tyre colour coding |
| **Driver Metrics** | Best lap · Avg pace · Consistency σ · Total laps · Stints · Finish position |
| **Stint Table** | Lap range · Laps · Best lap · Avg pace · Σ consistency · Deg rate · Δ vs session best · Pit lap |
| **Delta Waterfall** | Per-lap bar chart showing gap to session best (green = close, red = slow) |

---

### `TAB 4` — ⚔️ Head-to-Head

> **File:** `compare.py`

Side-by-side driver comparison with overlaid pace traces, distribution plots, and a direct delta chart.

| Feature | Detail |
| --- | --- |
| **Driver Cards** | Per-driver metric cards with team colour stripe, best lap delta, avg pace delta, consistency σ |
| **Race Pace Overlay** | Multi-driver line chart, tyre-coloured, pit laps filtered out |
| **Lap Delta Bar Chart** | Lap-by-lap `DriverA minus DriverB` delta — coloured by who is faster each lap |
| **Violin Distribution** | Full lap-time distribution with box plot and outliers per driver |

---

### `TAB 5` — 🤝 Teammate Duel

> **File:** `teammates.py` → routes to `compare.py`

Automatically extracts all intra-team pairings for the selected session and fires the full Head-to-Head engine.

| Feature | Detail |
| --- | --- |
| **Dynamic Extraction** | Reads the official `TeamName` field — works for mid-season driver swaps |
| **Pair Selector** | Dropdown showing all valid pairs e.g. `McLaren: NOR vs PIA` |

---

### `TAB 6` — 🧠 Strategy Board

> **File:** `strategy.py`

Deep-dive session strategy, historical incident probabilities, and pit-stop sequence analysis.

| Feature | Detail |
| --- | --- |
| **Historical Risk Profile** | Aggregates all sessions of the same type from **2018–present** for the selected circuit. Calculates absolute probabilities for Yellow, SC, VSC, and Red Flags using strict `TrackStatus` binaries. |
| **Incident Density** | Bar chart showing the average occurrences of each flag type per session, with hover tooltips detailing the specific years they occurred. |
| **Gantt Chart** | Horizontal bar chart — every driver's stints laid out by lap number, tyre-coloured, sorted by finish order |
| **Undercut / Overcut** | Select two drivers and two pit stops — get immediate, stint-end, and race-finish position deltas |
| **Auto-Match Mode** | Toggle to automatically find the driver who gained the most positions from a pit cycle |
| **Phase Breakdown** | Grouped bar — in-lap time vs out-lap time for each driver to show *where* the time was won |

---

### `TAB 7` — 🔬 Driver Telemetry

> **File:** `engineer.py`

Raw 20Hz telemetry overlaid across any two laps — the closest thing to actual race engineer data.

| Feature | Detail |
| --- | --- |
| **4-Panel Telemetry** | Speed · Throttle · Brake · Gear — all on shared x-axis (track distance) |
| **Benchmark Overlay** | Fastest lap shown as a dashed white reference on every panel |
| **DRS Detection** | DRS-open sections highlighted in `🟢 green` on the speed trace |
| **Lap History Table** | Full session log with colour-coded sector times (Purple/Green/Yellow) |

---

### `TAB 8` — 🎬 Race Replay

> **File:** `replay.py`

Lap-by-lap circuit map replay with a live timing tower — rendered fully in-browser.

| Feature | Detail |
| --- | --- |
| **Circuit Map** | Pure HTML5 Canvas — sector-coloured track outline with S/F flag marker |
| **Car Dots** | GPS position dots coloured by team, with driver labels |
| **Live Timing Tower** | Position · Driver · Grid Δ · Interval · Tyre history · Tyre age |
| **Playback Controls** | Play / Pause · Reset · Lap slider · Speed selector (0.5× / 1× / 2× / 4×) |

---

### `TAB 9` — 📐 Circuit Analysis

> **File:** `circuit.py`

Comprehensive Track Walk mapping layout geometry, overtaking hotspots, and lap-by-lap telemetry.

| Feature | Detail |
| --- | --- |
| **Static Track Map** | Clean map rendering Sector 1/2/3 colors, solid green DRS zones, yellow DRS detection dots, and the Speed Trap. |
| **Action Zones** | High-density spatial scatter plot mapping exact overtake coordinates mathematically tied to heavy braking zones, with pure-red density mapping and hover details. |
| **Widescreen JS Table** | Zero-latency lap-by-lap telemetry table with real-time F1 broadcast color coding (Purple = Session Best, Green = PB). |
| **Velocity Heatmap** | High-density GPS scatter plot of the circuit colored by absolute speed (km/h). |
| **Engineering Desk** | 3D Topography mapping, gearshift modality, severity index (longitudinal braking Gs), and G-G Friction Circle. |

---

## 🎨 Design System

PitWall uses a custom CSS theme applied globally via `main.py`.

### Colour Palette

| Token | Hex | Usage |
| --- | --- | --- |
| `--bg` | `#0d0d0f` | App background |
| `--surface` | `#13131a` | Cards, panels |
| `--card` | `#1a1a24` | Metric containers |
| `--border` | `#2a2a38` | All borders |
| `--accent` | `#e8002d` | Primary red — buttons, highlights, section chips |
| `--accent2` | `#ff6b35` | Section sub-headers |
| `--green` | `#00d47e` | Positive deltas, personal bests |
| `--yellow` | `#ffd700` | Warnings, session best sectors |
| `--blue` | `#4db8ff` | Sector 2 / Wet conditions |

---

## 📦 Dependencies

### Core

| Package | Version | Purpose |
| --- | --- | --- |
| `streamlit` | `1.57.0` | Web framework & UI components |
| `fastf1` | `3.8.3` | Official F1 timing data API |
| `pandas` | `2.3.3` | All data manipulation |
| `numpy` | `2.4.6` | Numerical computation |
| `plotly` | `6.7.0` | All interactive charts |

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

### Streamlit Cache TTL

All data-loading functions use `@st.cache_data(ttl=86400)` or `@st.cache_resource` for complex FastF1 telemetry objects. Data is cached for **24 hours** per session. To force a refresh, clear Streamlit's cache from the top-right menu inside the app, or delete the `f1_cache/` directory.

---

## ⚠️ Known Limitations

| Limitation | Detail |
| --- | --- |
| **Telemetry cutoff** | 20Hz telemetry (Driver Telemetry tab) is only available from **2018 onwards**. The app blocks these tabs for older seasons with a warning. |
| **GPS / pos_data** | Car position dots in the Race Replay require `pos_data`, which FastF1 provides for most sessions from **2019+**. Older sessions will show the track outline with no car dots — the timing tower still works. |
| **First load time** | A full race session with telemetry can take **2–5 minutes** to download on the first load. All subsequent loads are instant from the local cache. |

---

## 🛠️ Troubleshooting

### `UnhashableParamError`

If you encounter caching errors regarding `fastf1.core.Telemetry` or `Laps`, this indicates you are running an older codebase. The current architecture strictly utilizes `@st.cache_resource` and underscore-prefixed arguments (e.g., `_tel`) to safely bypass Streamlit's hashing engine.

### `DataNotLoadedError: pos_data`

FastF1's `pos_data` property raises an exception (not `AttributeError`) when telemetry is not loaded. This is safely handled natively, but if modifying code, ensure you wrap accesses in a `try/except` block.

### Session data not found

This usually means the session hasn't been run yet, or FastF1 hasn't indexed it. Check [FastF1's data availability notes](https://docs.fastf1.dev/). For recent sessions, wait ~1 hour after the session ends.

---

## 📜 License

MIT License — do whatever you want, don't blame me if your strategy call loses the race.

---

**Built for the love of the sport.**  
*Not affiliated with Formula 1, the FIA, or any constructor.*

`FastF1` data is sourced from the official F1 timing feed and is subject to F1's terms of use.