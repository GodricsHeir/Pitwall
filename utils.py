"""
utils.py — Shared helpers for PitWall Analytics
"""
import pandas as pd
import streamlit as st
import fastf1

# ─────────────────────────────────────────────────────────────
#  TEAM COLOURS (Fallback palette for older seasons)
# ─────────────────────────────────────────────────────────────
TEAM_COLORS = {
    "Red Bull Racing":          "#3671C6",
    "Red Bull":                 "#3671C6",
    "Ferrari":                  "#E8002D",
    "Scuderia Ferrari":         "#E8002D",
    "Mercedes":                 "#00D2BE",
    "McLaren":                  "#FF8000",
    "Aston Martin":             "#229971",
    "Aston Martin F1 Team":     "#229971",
    "Alpine":                   "#0093CC",
    "Alpine F1 Team":           "#0093CC",
    "Williams":                 "#00A0DD",
    "Williams Racing":          "#00A0DD",
    "Haas":                     "#B6BABD",
    "Haas F1 Team":             "#B6BABD",
    "Kick Sauber":              "#52E252",
    "Sauber":                   "#52E252",
    "Alfa Romeo":               "#C92D4B",
    "RB":                       "#6692FF",
    "RB F1 Team":               "#6692FF",
    "AlphaTauri":               "#5E8FAA",
    "Scuderia AlphaTauri":      "#5E8FAA",
    "Toro Rosso":               "#469BFF",
    "Racing Point":             "#F596C8",
    "Force India":              "#F596C8",
    "Renault":                  "#FFF500",
}

# Driver → Team lookup fallback 
DRIVER_TEAMS = {
    "VER": "Red Bull Racing", "PER": "Red Bull Racing",
    "LEC": "Ferrari",         "SAI": "Ferrari",    "HAM": "Ferrari",
    "RUS": "Mercedes",        "ANT": "Mercedes",
    "NOR": "McLaren",         "PIA": "McLaren",
    "ALO": "Aston Martin",    "STR": "Aston Martin",
    "GAS": "Alpine",          "DOO": "Alpine",
    "ALB": "Williams",        "SAR": "Williams",   "COL": "Williams",
    "MAG": "Haas",            "BEA": "Haas",       "OCO": "Haas",
    "HUL": "Kick Sauber",     "BOR": "Kick Sauber",
    "TSU": "RB",              "LAW": "RB",
    "ZHO": "Kick Sauber",     "BOT": "Kick Sauber",
}

# Tyre colour map (universal)
TYRE_COLORS = {
    '🔴 SOFT':         '#e10600',
    '🟡 MEDIUM':       '#ffd700',
    '⚪ HARD':         '#d0d0d0',
    '🟢 INTERMEDIATE': '#43b02a',
    '🔵 WET':          '#0082fa',
    '💖 HYPERSOFT':    '#ffb3c6',
    '💜 ULTRASOFT':    '#b300b3',
    '❤️ SUPERSOFT':   '#ff4444',
    '❔ UNKNOWN':      '#888888',
}

TYRE_LABELS = {
    'SOFT': '🔴 SOFT', 'MEDIUM': '🟡 MEDIUM', 'HARD': '⚪ HARD',
    'INTERMEDIATE': '🟢 INTERMEDIATE', 'WET': '🔵 WET',
    'HYPERSOFT': '💖 HYPERSOFT', 'ULTRASOFT': '💜 ULTRASOFT',
    'SUPERSOFT': '❤️ SUPERSOFT', 'UNKNOWN': '❔ UNKNOWN',
}

# Master Plotly Theme Dictionary
PLOTLY_THEME = dict(
    template="plotly_dark",
    paper_bgcolor="#13131a",
    plot_bgcolor="#0d0d0f",
    font=dict(family="Exo 2, sans-serif", color="#e8e8f0", size=12),
    xaxis=dict(gridcolor="#2a2a38", linecolor="#2a2a38", zerolinecolor="#2a2a38"),
    yaxis=dict(gridcolor="#2a2a38", linecolor="#2a2a38", zerolinecolor="#2a2a38"),
    legend=dict(bgcolor="rgba(19,19,26,0.8)", bordercolor="#2a2a38", borderwidth=1),
    margin=dict(l=50, r=30, t=60, b=50),
)


# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────
def format_time(seconds):
    if pd.isna(seconds):
        return "N/A"
    try:
        minutes = int(seconds // 60)
        remaining = seconds % 60
        return f"{minutes:02d}:{remaining:06.3f}"
    except Exception:
        return "N/A"


def driver_color(driver_code: str, results_df=None) -> str:
    """Return hex colour for a driver, using team palette."""
    # Try to look up team from live results first
    if results_df is not None and not results_df.empty:
        row = results_df[results_df['Abbreviation'] == driver_code]
        if not row.empty:
            team = row.iloc[0].get('TeamName', '')
            for k, v in TEAM_COLORS.items():
                if k.lower() in str(team).lower():
                    return v
    # Fallback to static map
    team = DRIVER_TEAMS.get(driver_code, '')
    return TEAM_COLORS.get(team, '#888888')


def apply_tyre_labels(df):
    df = df.copy()
    df['Compound'] = df['Compound'].fillna('UNKNOWN').astype(str)
    df['Tyre'] = df['Compound'].map(TYRE_LABELS).fillna('❔ UNKNOWN')
    return df


def delta_str(val, reference=0.0, inverse=False):
    """Format a delta in seconds. inverse=True means higher = worse."""
    d = val - reference
    if abs(d) < 0.001:
        return "–"
    sign = "+" if d > 0 else ""
    return f"{sign}{d:.3f}s"


def safe_load_session(year, race, session_id, **kwargs):
    """Load a FastF1 session, returning (session, laps, error_msg)."""
    default_kwargs = dict(telemetry=False, weather=False, messages=False)
    default_kwargs.update(kwargs)
    try:
        session = fastf1.get_session(year, race, session_id)
        session.load(**default_kwargs)
        laps = session.laps
        laps['LapTime_s'] = laps['LapTime'].dt.total_seconds()
        laps = laps.dropna(subset=['LapTime_s'])
        if laps.empty:
            return session, None, "No lap time data found for this session."
        return session, laps, None
    except Exception as e:
        return None, None, str(e)


def filter_clean_laps(laps, threshold=1.15):
    """Remove extremely slow laps (pit stops, SC) using a generous per-driver threshold."""
    if laps is None or laps.empty:
        return laps
        
    clean_laps = []
    # Calculate cutoff dynamically per driver to account for car pace differences
    for driver in laps['Driver'].unique():
        d_laps = laps[laps['Driver'] == driver]
        d_fastest = d_laps['LapTime_s'].min()
        
        if pd.notna(d_fastest):
            # Keep laps faster than their personal best * 1.15
            d_clean = d_laps[d_laps['LapTime_s'] < (d_fastest * threshold)]
            clean_laps.append(d_clean)
            
    if not clean_laps:
        return laps
        
    return pd.concat(clean_laps).sort_index()


def extract_pit_map(laps):
    """Extract pit-in lap numbers per driver/stint before any filtering."""
    laps = laps.copy()
    laps['Stint'] = laps['Stint'].fillna(0).astype(int)
    pit = laps[laps['PitInTime'].notnull()][['Driver', 'Stint', 'LapNumber']].copy()
    pit = pit.rename(columns={'LapNumber': 'Pit Lap'})
    return pit


def section_header(label: str, title: str):
    st.markdown(f'<div class="pw-section-label">{label}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="pw-section-title">{title}</div>', unsafe_allow_html=True)


def no_data_error(msg="No data available for the selected parameters."):
    st.error(f"⚠️ {msg}")


def apply_plotly_theme(fig):
    """Apply global dark theme to any Plotly figure."""
    fig.update_layout(**PLOTLY_THEME, height=580)
    return fig