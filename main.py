import streamlit as st
import fastf1
import os

st.set_page_config(
    page_title="PitWall Analytics",
    page_icon="🏁",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─────────────────────────────────────────────
#  GLOBAL CSS  — Sleek Matte Dark Theme
# ─────────────────────────────────────────────
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Exo+2:ital,wght@0,300;0,400;0,600;0,700;0,900;1,400&family=JetBrains+Mono:wght@400;600&display=swap');

:root {
    --bg:        #0d0d0f;
    --surface:   #13131a;
    --card:      #1a1a24;
    --border:    #2a2a38;
    --accent:    #e8002d;
    --accent2:   #ff6b35;
    --muted:     #555568;
    --text:      #e8e8f0;
    --text-dim:  #8888a0;
    --green:     #00d47e;
    --yellow:    #ffd700;
    --blue:      #4db8ff;
}

/* ── Base ── */
html, body, [class*="css"] { font-family: 'Exo 2', sans-serif !important; }
.stApp { background-color: var(--bg) !important; color: var(--text) !important; }
.main .block-container { padding: 1.5rem 2.5rem 3rem; max-width: 1600px; }

/* ── Header Banner ── */
.pw-banner {
    display: flex; align-items: center; justify-content: space-between;
    padding: 1.4rem 2rem 1.2rem;
    background: linear-gradient(135deg, #0d0d0f 0%, #13131a 60%, #1a0a12 100%);
    border-bottom: 2px solid var(--accent);
    margin: -1.5rem -2.5rem 2rem;
    position: relative; overflow: hidden;
}
.pw-banner::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
    background: repeating-linear-gradient(
        90deg, transparent, transparent 39px,
        rgba(232,0,45,0.04) 39px, rgba(232,0,45,0.04) 40px
    );
    pointer-events: none;
}
.pw-logo { display: flex; flex-direction: column; gap: 2px; }
.pw-logo-title {
    font-size: 2.2rem; font-weight: 900; letter-spacing: 0.15em;
    text-transform: uppercase; color: var(--text);
    line-height: 1;
}
.pw-logo-title span { color: var(--accent); }
.pw-logo-sub {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem; letter-spacing: 0.3em; color: var(--muted);
    text-transform: uppercase;
}
.pw-badge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem; padding: 4px 10px;
    border: 1px solid var(--accent); border-radius: 2px;
    color: var(--accent); letter-spacing: 0.15em;
    text-transform: uppercase;
}

/* ── NATIVE STREAMLIT TABS STYLING (Replaces Custom HTML Tabs) ── */
div[data-testid="stTabs"] > div > div > div > button[role="tab"] {
    padding: 10px 22px !important; background: transparent !important;
    border: none !important; border-bottom: 3px solid transparent !important;
    color: var(--text-dim) !important; font-family: 'Exo 2', sans-serif !important;
    font-size: 0.85rem !important; font-weight: 600 !important; letter-spacing: 0.08em !important;
    text-transform: uppercase !important; cursor: pointer !important;
    transition: all .2s !important; white-space: nowrap !important;
}
div[data-testid="stTabs"] > div > div > div > button[role="tab"]:hover {
    color: var(--text) !important; border-bottom-color: var(--muted) !important;
}
div[data-testid="stTabs"] > div > div > div > button[role="tab"][aria-selected="true"] {
    color: var(--accent) !important; border-bottom-color: var(--accent) !important; background: transparent !important;
}
/* Hide the default gray bottom border of the tab list */
div[data-testid="stTabs"] > div > div { gap: 8px !important; border-bottom: 1px solid var(--border) !important; padding-bottom: 0 !important; }

/* ── Config Row ── */
.pw-config {
    background: var(--card);
    border: 1px solid var(--border);
    border-top: 2px solid var(--accent);
    border-radius: 0 0 6px 6px;
    padding: 1.2rem 1.5rem 1rem;
    margin-bottom: 1.5rem;
}

/* ── Selector overrides ── */
div[data-testid="stSelectbox"] > label,
div[data-testid="stMultiSelect"] > label,
div[data-testid="stCheckbox"] > label { color: var(--text-dim) !important; font-size: 0.75rem !important; letter-spacing: 0.1em !important; text-transform: uppercase !important; font-weight: 600 !important; }

div[data-baseweb="select"] > div:first-child,
div[data-baseweb="input"] > div { background-color: #0f0f18 !important; border-color: var(--border) !important; border-radius: 4px !important; }
div[data-baseweb="select"]:focus-within > div:first-child { border-color: var(--accent) !important; }
div[data-baseweb="popover"] { background: var(--surface) !important; border: 1px solid var(--border) !important; }
li[role="option"]:hover { background: #1e1e2e !important; }
li[role="option"][aria-selected="true"] { background: rgba(232,0,45,0.15) !important; }

/* ── Primary Button ── */
div.stButton > button[kind="primary"] {
    background: var(--accent) !important;
    color: white !important; border: none !important;
    font-family: 'Exo 2', sans-serif !important; font-weight: 700 !important;
    letter-spacing: 0.1em !important; text-transform: uppercase !important;
    border-radius: 4px !important; padding: 0.6rem 1.5rem !important;
    transition: all .2s !important;
}
div.stButton > button[kind="primary"]:hover {
    background: #c8001f !important; transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(232,0,45,0.4) !important;
}
div.stButton > button[kind="secondary"] {
    background: transparent !important; color: var(--text) !important;
    border: 1px solid var(--border) !important;
    font-family: 'Exo 2', sans-serif !important; font-weight: 600 !important;
    letter-spacing: 0.08em !important; text-transform: uppercase !important;
    border-radius: 4px !important;
}
div.stButton > button[kind="secondary"]:hover { border-color: var(--accent) !important; color: var(--accent) !important; }

/* ── Metrics ── */
div[data-testid="metric-container"] {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important; padding: 1rem 1.2rem !important;
}
div[data-testid="metric-container"] label { color: var(--text-dim) !important; font-size: 0.7rem !important; letter-spacing: 0.12em !important; text-transform: uppercase !important; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] { color: var(--text) !important; font-family: 'JetBrains Mono', monospace !important; font-size: 1.1rem !important; }
div[data-testid="metric-container"] [data-testid="stMetricDelta"] { font-size: 0.75rem !important; font-family: 'JetBrains Mono', monospace !important; }

/* ── Dataframe ── */
div[data-testid="stDataFrame"] { border: 1px solid var(--border) !important; border-radius: 6px !important; overflow: hidden !important; }
div[data-testid="stDataFrame"] table { background: var(--card) !important; }
div[data-testid="stDataFrame"] th { background: #0f0f18 !important; color: var(--text-dim) !important; font-size: 0.7rem !important; letter-spacing: 0.1em !important; text-transform: uppercase !important; border-bottom: 1px solid var(--accent) !important; }
div[data-testid="stDataFrame"] td { border-color: var(--border) !important; color: var(--text) !important; font-family: 'JetBrains Mono', monospace !important; font-size: 0.8rem !important; }
div[data-testid="stDataFrame"] tr:hover td { background: rgba(232,0,45,0.05) !important; }

/* ── Divider ── */
hr { border-color: var(--border) !important; margin: 1.5rem 0 !important; }

/* ── Section headers ── */
h1, h2, h3 { font-family: 'Exo 2', sans-serif !important; font-weight: 700 !important; letter-spacing: 0.06em !important; text-transform: uppercase !important; }
h1 { color: var(--text) !important; }
h2 { color: var(--text) !important; font-size: 1.3rem !important; }
h3 { color: var(--accent2) !important; font-size: 1rem !important; }

/* ── Section label chip ── */
.pw-section-label {
    display: inline-block; font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem; letter-spacing: 0.2em; text-transform: uppercase;
    color: var(--accent); border: 1px solid rgba(232,0,45,0.3);
    padding: 3px 10px; border-radius: 2px; margin-bottom: 0.6rem;
    background: rgba(232,0,45,0.06);
}
.pw-section-title {
    font-family: 'Exo 2', sans-serif; font-size: 1.1rem; font-weight: 700;
    letter-spacing: 0.06em; text-transform: uppercase; color: var(--text);
    margin-bottom: 1rem;
}

/* ── Driver card grid ── */
.pw-driver-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 1rem; }
.pw-driver-card {
    border: 1px solid var(--border); border-radius: 4px;
    background: var(--card); padding: 10px 12px;
    cursor: pointer; transition: all .15s; text-align: center;
    font-weight: 600; font-size: 0.85rem; letter-spacing: 0.05em;
    color: var(--text-dim);
}
.pw-driver-card:hover { border-color: var(--accent); color: var(--text); }
.pw-driver-card.selected { border-color: var(--accent); background: rgba(232,0,45,0.12); color: var(--text); }

/* ── Checkbox styling ── */
div[data-testid="stCheckbox"] { background: var(--card); border: 1px solid var(--border); border-radius: 4px; padding: 8px 12px; transition: border-color .15s; }
div[data-testid="stCheckbox"]:hover { border-color: var(--muted); }

/* ── Info / warning / error boxes ── */
div[data-testid="stAlert"] { border-radius: 4px !important; border-left-width: 3px !important; }

/* ── Spinner ── */
div[data-testid="stSpinner"] { color: var(--accent) !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--surface); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--muted); }

/* ── Radio override (hide default) ── */
div[data-testid="stRadio"] { display: none !important; }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  FASTF1 CACHE SETUP
# ─────────────────────────────────────────────
CACHE_DIR = "f1_cache"
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

# ─────────────────────────────────────────────
#  HEADER BANNER
# ─────────────────────────────────────────────
st.markdown("""
<div class="pw-banner">
  <div class="pw-logo">
    <div class="pw-logo-title">PIT<span>WALL</span></div>
    <div class="pw-logo-sub">F1 Strategy & Telemetry Analytics · 1950 – 2026</div>
  </div>
  <div class="pw-badge">LIVE DATA</div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  DATA HELPERS
# ─────────────────────────────────────────────
@st.cache_data(ttl=86400, show_spinner=False)
def get_schedule(year):
    try:
        schedule = fastf1.get_event_schedule(year)
        return schedule[schedule['EventFormat'] != 'testing']['EventName'].tolist()
    except Exception:
        return []

@st.cache_data(ttl=86400, show_spinner=False)
def get_drivers_for_session(year, grand_prix, session_identifier):
    try:
        session = fastf1.get_session(year, grand_prix, session_identifier)
        session.load(telemetry=False, weather=False, messages=False, laps=False)
        return sorted(session.results['Abbreviation'].dropna().tolist())
    except Exception:
        return []

# ─────────────────────────────────────────────
#  SESSION SELECTOR CONFIG PANEL
# ─────────────────────────────────────────────
st.markdown('<div class="pw-config">', unsafe_allow_html=True)

col1, col2, col3, col_gap = st.columns([1, 2, 1.5, 0.1])
with col1:
    year = st.selectbox("Season", list(range(1950, 2027))[::-1])
with col2:
    schedule = get_schedule(year)
    race = st.selectbox("Grand Prix", schedule if schedule else ["— no data —"])
with col3:
    SESSION_MAP = {
        "Race": "R", "Qualifying": "Q",
        "Sprint Race": "S", "Sprint Shootout": "SQ",
        "FP1": "FP1", "FP2": "FP2", "FP3": "FP3"
    }
    session_name = st.selectbox("Session", list(SESSION_MAP.keys()))
    session_id = SESSION_MAP[session_name]

st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  DRIVER LOADING (cached)
# ─────────────────────────────────────────────
available_drivers = []
if schedule:
    with st.spinner("Loading driver list…"):
        available_drivers = get_drivers_for_session(year, race, session_id)

# ─────────────────────────────────────────────
#  ROUTE TO MODULE
# ─────────────────────────────────────────────
if not schedule:
    st.error("⚠️ Schedule data unavailable for this season.")
    st.stop()

# Helper for Telemetry Guard
def check_telemetry_support():
    if int(year) < 2018:
        st.warning(f"🏛️ **Historical Archive Limit:** High-density telemetry analytics are only available from the 2018 season onwards. Please use the **RESULTS** or **STANDINGS** tabs for {year} data.")
        return False
    return True

# ─────────────────────────────────────────────
#  NATIVE TAB ROUTING (Maintains State)
# ─────────────────────────────────────────────
MODES = [
    ("RESULTS",          "results"),
    ("PACE TRACE",       "pace"),
    ("HEAD-TO-HEAD",     "h2h"),
    ("TEAMMATE DUEL",    "teammate"),
    ("STRATEGY BOARD",   "strategy"),
    ("DRIVER TELEMETRY", "engineer"),
    ("RACE REPLAY",      "replay"),
    ("STANDINGS",        "champion")
]

tabs = st.tabs([label for label, _ in MODES])

# ── OVERALL RESULTS ─────────────────────────
with tabs[0]: 
    st.markdown('<div class="pw-section-label">Session Classification</div>', unsafe_allow_html=True)
    if not available_drivers:
        st.warning("No driver data found for this session.")
    else:
        import race as race_tab
        race_tab.render_race_results(year, race, session_id, session_name)

# ── PACE TRACE ──────────────────────────────
with tabs[1]:
    st.markdown('<div class="pw-section-label">Single Driver / Grid</div>', unsafe_allow_html=True)
    if check_telemetry_support():
        driver_options = ["ALL"] + available_drivers
        pc1, pc2 = st.columns([2, 1])
        with pc1:
            selected_driver = st.selectbox("Driver", driver_options, key="pace_drv")
        with pc2:
            show_annotations = st.checkbox("Annotate pit laps", value=True, key="pace_anno")
        if st.button("▶  Generate Pace Trace", type="primary", use_container_width=True, key="pace_btn"):
            if not available_drivers:
                st.warning("No driver data found for this session.")
            else:
                with st.spinner("Loading telemetry…"):
                    import plot
                    plot.render_plot(year, race, session_id, session_name,
                                     selected_driver, available_drivers, show_annotations)

# ── HEAD-TO-HEAD ────────────────────────────
with tabs[2]:
    st.markdown('<div class="pw-section-label">Multi-Driver Comparison</div>', unsafe_allow_html=True)
    if check_telemetry_support():
        if not available_drivers:
            st.warning("No driver data available.")
        else:
            winner_id = None
            if session_id in ['R', 'S']:
                try:
                    sw = fastf1.get_session(year, race, session_id)
                    sw.load(telemetry=False, weather=False, messages=False, laps=False)
                    winner_id = sw.results.sort_values('Position').iloc[0]['Abbreviation']
                except Exception:
                    pass

            include_winner = False
            if winner_id:
                include_winner = st.checkbox(f"🏆 Auto-include winner ({winner_id})", value=False, key="h2h_win")

            st.markdown("**Select drivers to compare (2–6)**")
            valid_drivers = available_drivers
            selected_drivers = []
            cols = st.columns(5)
            for idx, drv in enumerate(valid_drivers):
                with cols[idx % 5]:
                    if st.checkbox(drv, key=f"h2h_{drv}"):
                        selected_drivers.append(drv)

            st.divider()
            if st.button("▶  Generate Comparison", type="primary", use_container_width=True, key="h2h_btn"):
                final_drivers = list(selected_drivers)
                if include_winner and winner_id and winner_id not in final_drivers:
                    final_drivers.append(winner_id)
                if len(final_drivers) < 2:
                    st.error("Select at least 2 drivers.")
                elif len(final_drivers) > 6:
                    st.error("Maximum 6 drivers.")
                else:
                    with st.spinner("Loading comparison…"):
                        import compare
                        compare.render_comparison(year, race, session_id, session_name, final_drivers)

# ── TEAMMATE DUEL ───────────────────────────
with tabs[3]:
    st.markdown('<div class="pw-section-label">Teammate Head-to-Head</div>', unsafe_allow_html=True)
    if check_telemetry_support():
        if not available_drivers:
            st.warning("No driver data available.")
        else:
            import teammates
            teammates.render_teammate_selector(year, race, session_id, session_name, available_drivers)

# ── STRATEGY BOARD ──────────────────────────
with tabs[4]:
    st.markdown('<div class="pw-section-label">Race Strategy Overview</div>', unsafe_allow_html=True)
    if check_telemetry_support():
        if not available_drivers:
            st.warning("No driver data available.")
        else:
            if st.button("▶  Load Strategy Board", type="primary", use_container_width=True, key="strat_btn"):
                with st.spinner("Crunching strategy data…"):
                    import strategy
                    strategy.render_strategy(year, race, session_id, session_name)

# ── RACE ENGINEER ───────────────────────────
with tabs[5]:
    st.markdown('<div class="pw-section-label">Race Engineer Dashboard</div>', unsafe_allow_html=True)
    if check_telemetry_support():
        if not available_drivers:
            st.warning("No driver data available.")
        else:
            pc1, _ = st.columns([2, 2])
            with pc1:
                eng_driver = st.selectbox("Select Driver", available_drivers, key="eng_drv")
            
            st.divider()
            with st.spinner("Loading race engineer data…"):
                import engineer
                engineer.render_engineer(year, race, session_id, session_name, eng_driver)

# ── RACE REPLAY ─────────────────────────────
with tabs[6]:
    st.markdown('<div class="pw-section-label">Race Replay Engine</div>', unsafe_allow_html=True)
    if check_telemetry_support():
        if not available_drivers:
            st.warning("No driver data available.")
        else:
            st.divider()
            import replay
            replay.render_replay(year, race, session_id, session_name)

# ── CHAMPIONSHIP STANDINGS ──────────────────
with tabs[7]:
    st.markdown('<div class="pw-section-label">Championship Tracker</div>', unsafe_allow_html=True)
    import champion
    champion.render_championship(year, race, session_id, session_name)