"""
champion.py — Championship Tracker module for PitWall Analytics
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import fastf1

from utils import section_header, no_data_error, driver_color, PLOTLY_THEME

# ─────────────────────────────────────────────────────────────
#  UTILITY & FORMATTING
# ─────────────────────────────────────────────────────────────
def get_gp_abbr(event_name, location, country):
    """Generates a clean 3-letter abbreviation for the X-axis."""
    name = str(event_name).upper()
    loc = str(location).upper()
    
    if 'MIAMI' in name or 'MIAMI' in loc: return 'MIA'
    if 'VEGAS' in name or 'VEGAS' in loc: return 'LVG'
    if 'UNITED STATES' in name and 'AUSTIN' in loc: return 'USA'
    if 'EMILIA' in name or 'IMOLA' in loc: return 'EMI'
    if 'BRITISH' in name or 'SILVERSTONE' in loc: return 'GBR'
    if 'SAUDI' in name: return 'SAU'
    if 'ABU DHABI' in name: return 'ABU'
    if 'MEXIC' in name: return 'MEX'
    if 'NETHERLANDS' in name or 'DUTCH' in name: return 'NED'
    if 'SAO PAULO' in name or 'BRAZIL' in name: return 'BRA'
    if 'AZERBAIJAN' in name: return 'AZE'
    
    return str(country)[:3].upper()

def format_pts(p):
    """Safely formats points, preserving .5 for partial point races like Spa 2021."""
    if pd.isna(p): return "0"
    return str(int(p)) if float(p) % 1 == 0 else f"{float(p):.1f}"

def format_delta(d):
    """Formats position changes with arrows."""
    if d == 0: return "–"
    if d > 0: return f"↑ {int(d)}"
    return f"↓ {abs(int(d))}"

def get_safe_team_color(team_name, results_df):
    """Fetches the official team color or falls back to their lead driver's color."""
    try:
        return fastf1.plotting.team_color(team_name)
    except Exception:
        if results_df is not None:
            match = results_df[results_df['TeamName'] == team_name]
            if not match.empty:
                drv = match.iloc[0].get('Abbreviation')
                if drv: return driver_color(drv, results_df)
    return '#888888'

def extract_safe_driver_name(row):
    """Coalesces across columns to handle missing names in pre-2005 databases."""
    for col in ['Abbreviation', 'LastName', 'FullName', 'BroadcastName', 'TeamName']:
        val = row.get(col)
        if pd.notna(val):
            val_str = str(val).strip()
            # The critical fix: ignoring pandas string-casted 'nan' values
            if val_str and val_str.lower() not in ['nan', 'none', 'nat', '<na>']:
                return val_str
    return "Unknown"


# ─────────────────────────────────────────────────────────────
#  CORE DATA AGGREGATOR
# ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=3600)
def compile_championship_data(year, max_round):
    """
    Crawls through the season up to `max_round` and extracts all points 
    from standard Races and Sprint events.
    """
    schedule = fastf1.get_event_schedule(year)
    schedule = schedule[schedule['EventFormat'] != 'testing'].copy()
    schedule['Abbr'] = schedule.apply(lambda r: get_gp_abbr(r['EventName'], r['Location'], r['Country']), axis=1)
    all_rounds = schedule[['RoundNumber', 'Abbr', 'EventName']].to_dict('records')
    
    records = []
    
    for rnd in range(1, max_round + 1):
        # 1. Fetch Main Race Points
        try:
            session = fastf1.get_session(year, rnd, 'R')
            session.load(telemetry=False, weather=False, messages=False)
            for _, row in session.results.iterrows():
                drv = extract_safe_driver_name(row)
                team = row.get('TeamName', 'Unknown')
                pts = float(row.get('Points', 0.0))
                records.append({'Round': rnd, 'Driver': drv, 'Team': team, 'Points': pts})
        except Exception:
            pass
            
        # 2. Fetch Sprint Points (if applicable)
        evt = schedule[schedule['RoundNumber'] == rnd]
        if not evt.empty and evt.iloc[0]['EventFormat'] in ['sprint', 'sprint_shootout', 'sprint_qualifying']:
            try:
                session_s = fastf1.get_session(year, rnd, 'S')
                session_s.load(telemetry=False, weather=False, messages=False)
                for _, row in session_s.results.iterrows():
                    drv = extract_safe_driver_name(row)
                    team = row.get('TeamName', 'Unknown')
                    pts = float(row.get('Points', 0.0))
                    records.append({'Round': rnd, 'Driver': drv, 'Team': team, 'Points': pts})
            except Exception:
                pass
                
    return pd.DataFrame(records), all_rounds


# ─────────────────────────────────────────────────────────────
#  CALCULATION ENGINE (WDC & WCC)
# ─────────────────────────────────────────────────────────────
def _build_standings_df(cum_df, pivot_df, current_round, entity_col):
    """Calculates deltas, gaps, and sorts the championship table."""
    standings = []
    
    # ── MAX DEFICIT MATH ENGINE ──
    # 1. Find the points of the championship leader at EVERY historical round
    leader_pts_per_round = cum_df.max(axis=0)
    # 2. Subtract every entity's historical points from the leader's points at that specific round
    deficits = cum_df.rsub(leader_pts_per_round, axis=1)
    # 3. Find the maximum point deficit the entity faced at any point in the season
    max_deficits = deficits.max(axis=1)
    
    for idx, row in cum_df.iterrows():
        if isinstance(idx, tuple):
            entity, team = idx[0], idx[1]
        else:
            entity, team = idx, idx
            
        total_pts = row.get(current_round, 0)
        prev_pts = row.get(current_round - 1, 0)
        
        try: round_pts = pivot_df.loc[idx, current_round]
        except KeyError: round_pts = 0
            
        standings.append({
            entity_col: entity,
            'Team': team,
            'Total Points': total_pts,
            'Prev Points': prev_pts,
            'Round Points': round_pts,
            'Max Deficit': max_deficits.loc[idx]
        })
        
    st_df = pd.DataFrame(standings)
    if st_df.empty: return pd.DataFrame()
    
    # Sort for current round
    st_df = st_df.sort_values(['Total Points', 'Round Points'], ascending=[False, False]).reset_index(drop=True)
    st_df['Pos'] = st_df.index + 1
    
    # Sort for previous round to calculate Position Delta
    prev_st = st_df.sort_values(['Prev Points'], ascending=False).reset_index(drop=True)
    prev_st['Prev Pos'] = prev_st.index + 1
    st_df = st_df.merge(prev_st[[entity_col, 'Prev Pos']], on=entity_col)
    
    st_df['Pos Δ'] = st_df['Prev Pos'] - st_df['Pos']
    
    # Calculate Current Gaps
    leader_pts = st_df['Total Points'].iloc[0]
    st_df['Gap to Leader'] = leader_pts - st_df['Total Points']
    st_df['Gap to Next'] = st_df['Total Points'].shift(1) - st_df['Total Points']
    st_df['Gap to Next'] = st_df['Gap to Next'].fillna(0)
    
    return st_df

def _format_display_table(st_df, entity_col):
    """Formats the raw numbers into strings for the UI."""
    disp = pd.DataFrame()
    disp['Pos'] = st_df['Pos'].astype(str)
    disp['Pos Δ'] = st_df['Pos Δ'].apply(format_delta)
    disp[entity_col] = st_df[entity_col]
    if entity_col == 'Driver': disp['Team'] = st_df['Team']
    
    disp['Points'] = st_df['Total Points'].apply(format_pts)
    disp['Points This Race'] = "+" + st_df['Round Points'].apply(format_pts)
    disp['Gap to Leader'] = "-" + st_df['Gap to Leader'].apply(format_pts)
    disp['Gap to Next'] = "-" + st_df['Gap to Next'].apply(format_pts)
    disp['Max Deficit'] = st_df['Max Deficit'].apply(lambda x: "0" if x == 0 else "-" + format_pts(x))
    
    disp.loc[0, 'Gap to Leader'] = "LEADER"
    disp.loc[0, 'Gap to Next'] = "–"
    
    return disp


# ─────────────────────────────────────────────────────────────
#  PLOTLY GRAPHING ENGINE
# ─────────────────────────────────────────────────────────────
def _plot_championship_density(cum_df, all_rounds, current_round, entity_col, results_df):
    """Renders the line progression chart with future races empty on the X-axis."""
    fig = go.Figure()
    
    x_all = [r['RoundNumber'] for r in all_rounds]
    x_labels = [r['Abbr'] for r in all_rounds]
    
    driver_dash = {}
    if entity_col == 'Driver':
        # Group drivers by team to assign Solid vs Dashed lines for teammates
        teams = cum_df.index.get_level_values('Team').unique()
        for t in teams:
            drvs = cum_df.xs(t, level='Team')
            if current_round in drvs.columns:
                sorted_drvs = drvs[current_round].sort_values(ascending=False).index.tolist()
            else:
                sorted_drvs = drvs.index.tolist()
                
            for i, d in enumerate(sorted_drvs):
                driver_dash[d] = 'solid' if i == 0 else 'dash' if i == 1 else 'dot'
    
    for idx, row in cum_df.iterrows():
        if entity_col == 'Team':
            name = idx
            dash = 'solid'
            color = get_safe_team_color(name, results_df)
        else:
            name = idx[0]
            dash = driver_dash.get(name, 'solid')
            color = driver_color(name, results_df)
            
        # Extract X and Y purely for rounds that have been calculated
        y_vals, x_vals = [], []
        for r in range(1, current_round + 1):
            if r in row:
                y_vals.append(row[r])
                x_vals.append(r)
                
        # Fill zero up to current round to prevent lines from cutting off early if they DNF'd round 1
        if 1 not in x_vals: 
            x_vals.insert(0, 1); y_vals.insert(0, 0)
                
        fig.add_trace(go.Scatter(
            x=x_vals, y=y_vals, mode='lines+markers',
            name=name,
            line=dict(color=color, dash=dash, width=2.5),
            marker=dict(size=6, line=dict(width=1, color='#13131a')),
            hovertemplate=f"<b>{name}</b><br>Round %{{x}}: %{{y}} pts<extra></extra>"
        ))
        
    fig.update_layout(
        title=f"Campaign Progression ({'WDC' if entity_col == 'Driver' else 'WCC'})",
        xaxis_title="Grand Prix", yaxis_title="Cumulative Points",
        hovermode="x unified",
        **PLOTLY_THEME, height=550
    )
    
    fig.update_xaxes(
        tickmode='array', tickvals=x_all, ticktext=x_labels,
        range=[0.8, len(x_all) + 0.2], showgrid=False
    )
    
    return fig


# ─────────────────────────────────────────────────────────────
#  PUBLIC RENDER ENTRY POINT
# ─────────────────────────────────────────────────────────────
def render_championship(year, race, session_id, session_name):
    section_header("SEASON CAMPAIGN", f"{year} Championship Standings up to {race}")
    
    # Load current event to get the RoundNumber upper bound
    try:
        current_event = fastf1.get_event(year, race)
        current_round = current_event['RoundNumber']
        dummy_session = fastf1.get_session(year, race, 'R')
        dummy_session.load(telemetry=False, weather=False, messages=False)
        results_df = dummy_session.results
    except Exception as e:
        no_data_error(f"Failed to establish championship timeline context: {e}")
        return

    with st.spinner(f"Compiling Championship Standings up to Round {current_round}... (This aggregates ~1s per historic race)"):
        raw_pts_df, all_rounds = compile_championship_data(year, current_round)

    if raw_pts_df.empty:
        no_data_error("No points data found. This season may not have started yet.")
        return

    # ── WDC MATH ──
    wdc_round_pts = raw_pts_df.groupby(['Round', 'Driver', 'Team'])['Points'].sum().reset_index()
    wdc_pivot = wdc_round_pts.pivot_table(index=['Driver', 'Team'], columns='Round', values='Points', aggfunc='sum').fillna(0)
    wdc_cum = wdc_pivot.cumsum(axis=1)
    
    wdc_stats = _build_standings_df(wdc_cum, wdc_pivot, current_round, 'Driver')
    wdc_display = _format_display_table(wdc_stats, 'Driver')
    
    # ── INJECT GRID & RACE POSITIONS FOR WDC ──
    grid_pos_map = {}
    race_pos_map = {}
    if results_df is not None and not results_df.empty:
        for _, r in results_df.iterrows():
            d_name = extract_safe_driver_name(r)
            gp = pd.to_numeric(r.get('GridPosition'), errors='coerce')
            rp = pd.to_numeric(r.get('Position'), errors='coerce')
            grid_pos_map[d_name] = str(int(gp)) if pd.notna(gp) and gp > 0 else "PIT"
            race_pos_map[d_name] = str(int(rp)) if pd.notna(rp) else "NC"

    if not wdc_display.empty and 'Team' in wdc_display.columns:
        team_idx = wdc_display.columns.get_loc('Team')
        wdc_display.insert(team_idx + 1, 'Grid Position', wdc_display['Driver'].map(lambda x: grid_pos_map.get(x, '—')))
        wdc_display.insert(team_idx + 2, 'Race Position', wdc_display['Driver'].map(lambda x: race_pos_map.get(x, '—')))
    
    # ── WCC MATH ──
    wcc_round_pts = raw_pts_df.groupby(['Round', 'Team'])['Points'].sum().reset_index()
    wcc_pivot = wcc_round_pts.pivot_table(index='Team', columns='Round', values='Points', aggfunc='sum').fillna(0)
    wcc_cum = wcc_pivot.cumsum(axis=1)
    
    wcc_stats = _build_standings_df(wcc_cum, wcc_pivot, current_round, 'Team')
    wcc_display = _format_display_table(wcc_stats, 'Team')

    # ── PANDAS STYLER ──
    def style_standings(df, entity_col):
        def apply_row(row):
            styles = [''] * len(row)
            
            i_pd = df.columns.get_loc('Pos Δ')
            if '↑' in row['Pos Δ']: styles[i_pd] = 'color: #00d47e; font-weight: bold;'
            elif '↓' in row['Pos Δ']: styles[i_pd] = 'color: #e8002d; font-weight: bold;'
            
            i_ent = df.columns.get_loc(entity_col)
            name = row.iloc[i_ent]
            color = driver_color(name, results_df) if entity_col == 'Driver' else get_safe_team_color(name, results_df)
            styles[i_ent] = f'border-left: 4px solid {color}; font-weight: bold; color: {color}; background-color: {color}15;'
            
            i_scr = df.columns.get_loc('Points This Race')
            if row['Points This Race'] not in ['+0', '+0.0']: 
                styles[i_scr] = 'color: #00d47e;'
                
            return styles
        return df.style.apply(apply_row, axis=1)

    # ── UI TABS ──
    tab1, tab2 = st.tabs(["🏆 Drivers' Championship", "🏎️ Constructors' Championship"])
    
    with tab1:
        # ── FORM-BASED DRIVER SELECTION (Prevents jitter on click) ──
        with st.form("wdc_filter_form"):
            st.markdown('<div style="font-size: 0.85rem; color: #8888a0; margin-bottom: 8px;">Select Drivers to Compare (Max 6) — <i>If none are selected, all drivers are shown.</i></div>', unsafe_allow_html=True)
            all_drivers = sorted(list(set([idx[0] for idx in wdc_cum.index])))
            
            sel_drv = []
            cols = st.columns(6)
            for i, drv in enumerate(all_drivers):
                with cols[i % 6]:
                    if st.checkbox(drv, key=f"wdc_chk_{drv}"):
                        sel_drv.append(drv)
                        
            st.divider()
            st.form_submit_button("▶  UPDATE WDC CHART", type="primary", use_container_width=True)
                    
        # Apply filter
        if not sel_drv:
            plot_wdc = wdc_cum
        else:
            if len(sel_drv) > 6:
                st.warning("Maximum of 6 drivers can be compared at once. Displaying the first 6 selections.")
                sel_drv = sel_drv[:6]
            plot_wdc = wdc_cum[wdc_cum.index.get_level_values('Driver').isin(sel_drv)]
            
        st.plotly_chart(_plot_championship_density(plot_wdc, all_rounds, current_round, 'Driver', results_df), use_container_width=True)
        st.markdown(f"#### WDC Standings after Round {current_round}")
        st.dataframe(style_standings(wdc_display, 'Driver'), use_container_width=True, hide_index=True)
        
    with tab2:
        # ── FORM-BASED TEAM SELECTION (Prevents jitter on click) ──
        with st.form("wcc_filter_form"):
            st.markdown('<div style="font-size: 0.85rem; color: #8888a0; margin-bottom: 8px;">Select Constructors to Compare (Max 6) — <i>If none are selected, all teams are shown.</i></div>', unsafe_allow_html=True)
            all_teams = sorted(list(wcc_cum.index))
            
            sel_team = []
            cols = st.columns(6)
            for i, team in enumerate(all_teams):
                with cols[i % 6]:
                    if st.checkbox(team, key=f"wcc_chk_{team}"):
                        sel_team.append(team)
            
            st.divider()
            st.form_submit_button("▶  UPDATE WCC CHART", type="primary", use_container_width=True)
                    
        # Apply filter
        if not sel_team:
            plot_wcc = wcc_cum
        else:
            if len(sel_team) > 6:
                st.warning("Maximum of 6 constructors can be compared at once. Displaying the first 6 selections.")
                sel_team = sel_team[:6]
            plot_wcc = wcc_cum[wcc_cum.index.isin(sel_team)]
            
        st.plotly_chart(_plot_championship_density(plot_wcc, all_rounds, current_round, 'Team', results_df), use_container_width=True)
        st.markdown(f"#### WCC Standings after Round {current_round}")
        st.dataframe(style_standings(wcc_display, 'Team'), use_container_width=True, hide_index=True)