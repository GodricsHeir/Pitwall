"""
compare.py — Head-to-Head comparison module for PitWall Analytics
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils import (
    format_time, apply_tyre_labels, extract_pit_map,
    filter_clean_laps, safe_load_session,
    TYRE_COLORS, PLOTLY_THEME,
    section_header, no_data_error, driver_color, delta_str
)

def enrich_telemetry(telemetry_df):
    """Adds RPM handling and calculates Longitudinal G-Force for overlays."""
    telemetry_df['RPM'] = pd.to_numeric(telemetry_df['RPM'], errors='coerce').fillna(0)
    telemetry_df['Time_s'] = telemetry_df['Time'].dt.total_seconds()
    telemetry_df['Speed_ms'] = telemetry_df['Speed'] / 3.6
    
    # Calculate G-Force safely
    dt = telemetry_df['Time_s'].diff().fillna(0)
    dv = telemetry_df['Speed_ms'].diff().fillna(0)
    accel = np.zeros(len(telemetry_df))
    valid_mask = dt > 0
    accel[valid_mask] = dv[valid_mask] / dt[valid_mask]
    
    telemetry_df['Long_G'] = (accel / 9.81)
    telemetry_df['Long_G'] = telemetry_df['Long_G'].rolling(window=3, min_periods=1).mean().fillna(0)
    
    return telemetry_df

def _get_distinct_colors(drivers, results_df):
    """Ensures teammates have distinct colors to avoid messy dashed lines."""
    used = set()
    colors = {}
    fallbacks = ['#ffffff', '#df4bff', '#00d47e', '#ff6b35', '#ffd700', '#4db8ff']
    for d in drivers:
        c = str(driver_color(d, results_df)).lower()
        if c in used or c == '#888888':
            for fb in fallbacks:
                if fb not in used:
                    c = fb
                    break
        used.add(c)
        colors[d] = c
    return colors

def render_comparison(year, race, session_id, session_name, selected_drivers):
    title_str = "  ·  ".join(selected_drivers)
    section_header("HEAD-TO-HEAD", f"{year} {race}  ·  {session_name}")
    st.markdown(f"#### {title_str}")

    # ── 1. LOAD DATA & WEATHER ───────────────────────────
    session, laps, err = safe_load_session(year, race, session_id, telemetry=True, weather=True, messages=True)
    if err:
        no_data_error(err)
        return

    results_df = getattr(session, 'results', pd.DataFrame())
    drv_colors = _get_distinct_colors(selected_drivers, results_df)

    # ── 1.5 MERGE WEATHER DATA SAFELY ────────────────────
    if not laps.empty:
        try:
            weather_df = laps.get_weather_data()
            for col in weather_df.columns:
                if col not in laps.columns:
                    laps[col] = weather_df[col].values
        except Exception:
            pass 

    # ── 1.6 LIVE TIMING & DIRTY AIR ENGINE ───────────────
    laps_sorted = laps.dropna(subset=['Time']).sort_values('Time').copy()
    
    for col in ['Sector1Time', 'Sector2Time', 'Sector3Time']:
        s_col = f"{col[:7]}_s"
        laps_sorted[s_col] = laps_sorted[col].dt.total_seconds()
        
    laps_sorted['Session_S1'] = laps_sorted['Sector1_s'].cummin()
    laps_sorted['Session_S2'] = laps_sorted['Sector2_s'].cummin()
    laps_sorted['Session_S3'] = laps_sorted['Sector3_s'].cummin()
    
    laps_sorted['PB_S1'] = laps_sorted.groupby('Driver')['Sector1_s'].cummin()
    laps_sorted['PB_S2'] = laps_sorted.groupby('Driver')['Sector2_s'].cummin()
    laps_sorted['PB_S3'] = laps_sorted.groupby('Driver')['Sector3_s'].cummin()

    laps_sorted['GapToAhead'] = laps_sorted['Time'].diff().dt.total_seconds()
    laps_sorted['Is_Dirty_Air'] = laps_sorted['GapToAhead'] < 2.0

    laps = laps_sorted.sort_index()
    pit_map = extract_pit_map(laps)
    laps['Stint'] = laps['Stint'].fillna(0).astype(int)
    fastest_overall = laps['LapTime_s'].min()
    
    clean = filter_clean_laps(laps)
    clean = apply_tyre_labels(clean)
    clean['Is_Pit_Lap'] = (~pd.isna(clean['PitInTime'])) | (~pd.isna(clean['PitOutTime']))
    
    comp = clean[clean['Driver'].isin(selected_drivers)].copy()
    comp['LapTime_str'] = comp['LapTime_s'].apply(format_time)

    if comp.empty:
        no_data_error("No valid lap data for selected drivers.")
        return

    # ── 2. METRIC CARDS ──────────────────────────────────
    _render_driver_cards(comp, fastest_overall, session, selected_drivers, drv_colors, results_df)
    st.divider()

    # ── 3. CHARTS ────────────────────────────────────────
    comp_pure = comp[~comp['Is_Pit_Lap']].copy()
    is_race = session_id in ['R', 'S', 'SQ']

    if is_race:
        section_header("CHARTS", "Head-to-Head Pace Trace & Conditions")
        fig = _race_comparison_chart(comp_pure, selected_drivers, session, drv_colors, results_df, pit_map)
    else:
        section_header("CHARTS", "Qualifying Evolution & Conditions")
        fig = _quali_comparison_chart(comp_pure, selected_drivers, session, drv_colors, results_df, pit_map)

    fig.update_layout(**PLOTLY_THEME)
    st.plotly_chart(fig, use_container_width=True)

    # ── 4. SIDE-BY-SIDE DISTRIBUTION ─────────────────────
    if is_race:
        st.divider()
        section_header("DISTRIBUTION", "Lap Time Distribution by Driver")
        _render_distribution(comp_pure, selected_drivers, drv_colors)

    # ── 5. LAP-BY-LAP DELTA ──────────────────────────────
    if is_race and len(selected_drivers) == 2:
        st.divider()
        section_header("DELTA", f"{selected_drivers[0]} vs {selected_drivers[1]} — Lap Delta")
        _render_lap_delta(comp_pure, selected_drivers, drv_colors)

    # ── 6. STINT TABLE ───────────────────────────────────
    st.divider()
    section_header("ANALYTICS", "Direct Stint Comparison")
    _render_stint_table(comp_pure, pit_map, fastest_overall)

    # ── 7. FASTEST LAP TELEMETRY COMPARISON ──────────────
    st.divider()
    section_header("TELEMETRY", "Fastest Lap Comparison")
    with st.spinner("Extracting multi-driver telemetry..."):
        _render_telemetry_comparison(session, selected_drivers, drv_colors)

    # ── 8. MINISECTOR TRACK MAP COMPARISON ───────────────
    st.divider()
    section_header("TRACK MAP", "Mini-Sector Dominance Circuit Layout")
    with st.spinner("Generating spatial mini-sector tracking..."):
        _render_trackmap_comparison(session, selected_drivers, drv_colors)


# ─────────────────────────────────────────────────────────────
#  ADVANCED COMPARISON CHARTS (WEATHER + INCIDENTS)
# ─────────────────────────────────────────────────────────────
def _create_hover_text(plot_laps):
    def get_weather_state(row):
        rain = row.get('Rainfall', False)
        temp = row.get('TrackTemp', 30.0)
        status = str(row.get('TrackStatus', '1'))
        if rain:
            if '4' in status or '5' in status: return 4, "Heavy Rain / SC"
            return 3, "Wet"
        else:
            if temp < 25.0: return 2, "Cool / Overcast"
            return 1, "Clear / Dry"

    weather_res = plot_laps.apply(get_weather_state, axis=1)
    plot_laps['W_Level'] = [x[0] for x in weather_res]
    plot_laps['W_Desc'] = [x[1] for x in weather_res]
    
    def create_hover(row):
        def c(val, sb, pb):
            if pd.isna(val) or val <= 0: return "⚪"
            if abs(val - sb) < 0.001: return "🟣"
            if abs(val - pb) < 0.001: return "🟢"
            return "🟡"
            
        s1 = c(row['Sector1_s'], row['Session_S1'], row['PB_S1'])
        s2 = c(row['Sector2_s'], row['Session_S2'], row['PB_S2'])
        s3 = c(row['Sector3_s'], row['Session_S3'], row['PB_S3'])
        
        t1 = f"{row['Sector1_s']:.3f}" if pd.notna(row['Sector1_s']) else "N/A"
        t2 = f"{row['Sector2_s']:.3f}" if pd.notna(row['Sector2_s']) else "N/A"
        t3 = f"{row['Sector3_s']:.3f}" if pd.notna(row['Sector3_s']) else "N/A"
        tt = f"{row.get('TrackTemp', 'N/A')}°C"
        
        return (f"<b>{row['Driver']}</b> - Lap {int(row['LapNumber'])}<br>"
                f"Time: <b>{row['LapTime_str']}</b><br>"
                f"Tyre: {row['Tyre']}<br><br>"
                f"S1: {t1} {s1}<br>"
                f"S2: {t2} {s2}<br>"
                f"S3: {t3} {s3}<br><br>"
                f"Track Temp: {tt}")

    plot_laps['HoverText'] = plot_laps.apply(create_hover, axis=1)
    return plot_laps

def _race_comparison_chart(comp, drivers, session, drv_colors, results_df, pit_map):
    comp = _create_hover_text(comp.copy())
    
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.04, row_heights=[0.8, 0.2],
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
    )

    symbols = ['circle', 'square', 'diamond', 'cross', 'x', 'triangle-up']
    
    for i, drv in enumerate(drivers):
        drv_sym = symbols[i % len(symbols)]
        drv_df = comp[comp['Driver'] == drv]
        
        for stint in drv_df['Stint'].unique():
            df_s = drv_df[drv_df['Stint'] == stint]
            tyre = df_s['Tyre'].iloc[0]
            color = drv_colors[drv]
            
            fig.add_trace(go.Scatter(
                x=df_s['LapNumber'], y=df_s['LapTime_s'], mode='lines+markers',
                line=dict(color=color, width=2.5, dash='solid'),
                marker=dict(symbol=drv_sym, size=8, color=color, line=dict(width=1, color='rgba(255,255,255,0.4)')),
                name=f"{drv} ({tyre})", text=df_s['HoverText'], hovertemplate="%{text}<extra></extra>", legendgroup=drv
            ), row=1, col=1)

    dirty_laps = comp[comp['Is_Dirty_Air'] == True]
    if not dirty_laps.empty:
        fig.add_trace(go.Scatter(
            x=dirty_laps['LapNumber'], y=dirty_laps['LapTime_s'], mode='markers',
            marker=dict(size=12, color='rgba(150, 150, 150, 0.6)', line=dict(width=1.5, color='white')),
            name='Traffic / Dirty Air', hoverinfo='skip'
        ), row=1, col=1)

    if 'TrackTemp' in comp.columns:
        env_df = comp.groupby('LapNumber').agg({'TrackTemp': 'mean', 'W_Level': 'max', 'W_Desc': 'first'}).reset_index()
        fig.add_trace(go.Scatter(
            x=env_df['LapNumber'], y=env_df['TrackTemp'], mode='lines',
            line=dict(color='rgba(255, 107, 53, 0.35)', width=2, dash='dot'),
            name='Track Temp', hoverinfo='skip'
        ), row=1, col=1, secondary_y=True)
    else:
        env_df = comp.groupby('LapNumber').agg({'W_Level': 'max', 'W_Desc': 'first'}).reset_index()

    weather_color_map = {1: 'rgba(255, 215, 0, 0.7)', 2: 'rgba(150, 150, 150, 0.7)', 3: 'rgba(77, 184, 255, 0.8)', 4: 'rgba(0, 85, 255, 0.9)'}
    w_colors = env_df['W_Level'].map(weather_color_map).tolist()

    fig.add_trace(go.Bar(
        x=env_df['LapNumber'], y=env_df['W_Level'],
        marker_color=w_colors, marker_line_width=0, width=1,
        customdata=env_df['W_Desc'], hovertemplate="Lap %{x}<br>Weather: <b>%{customdata}</b><extra></extra>",
        showlegend=False
    ), row=2, col=1)

    all_laps = session.laps
    has_sc, has_vsc, has_red = False, False, False
    
    for lap in all_laps['LapNumber'].dropna().unique():
        stat = "".join(all_laps[all_laps['LapNumber'] == lap]['TrackStatus'].dropna().astype(str).tolist())
        if '4' in stat: 
            has_sc = True
            fig.add_vrect(x0=lap-0.5, x1=lap+0.5, fillcolor="rgba(255, 215, 0, 0.12)", layer="below", line_width=0, row=1, col=1)
        elif '6' in stat: 
            has_vsc = True
            fig.add_vrect(x0=lap-0.5, x1=lap+0.5, fillcolor="rgba(255, 165, 0, 0.15)", layer="below", line_width=0, row=1, col=1)
        elif '5' in stat: 
            has_red = True
            fig.add_vrect(x0=lap-0.5, x1=lap+0.5, fillcolor="rgba(232, 0, 45, 0.2)", layer="below", line_width=0, row=1, col=1)
            
    if has_sc: fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(255, 215, 0, 0.4)", size=12, symbol="square"), name="Safety Car"))
    if has_vsc: fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(255, 165, 0, 0.4)", size=12, symbol="square"), name="Virtual SC"))
    if has_red: fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(232, 0, 45, 0.4)", size=12, symbol="square"), name="Red Flag"))
    
    if hasattr(session, 'race_control_messages'):
        rcm = session.race_control_messages
        if rcm is not None and not rcm.empty:
            ref_laps = session.laps.pick_driver(drivers[0] if drivers else results_df.iloc[0]['Abbreviation'])
            ref_laps = ref_laps.sort_values('LapStartDate').dropna(subset=['LapStartDate', 'LapNumber'])
            
            for _, msg in rcm.iterrows():
                text = str(msg['Message']).upper()
                if "PENALTY" in text or "BLACK AND WHITE" in text:
                    if not any(d in text for d in drivers): continue
                    idx = ref_laps['LapStartDate'].searchsorted(msg['Time'])
                    if 0 < idx < len(ref_laps):
                        lap_num = ref_laps.iloc[idx]['LapNumber']
                        color = "#e8002d" if "PENALTY" in text else "#ffffff"
                        fig.add_vline(x=lap_num, line=dict(color=color, width=1.5, dash='dashdot'),
                                      annotation_text=text.replace("TIME PENALTY", "PENALTY").replace("CAR ", ""),
                                      annotation_font=dict(size=9, color=color), annotation_textangle=-90, row=1, col=1)
                                      
    for _, row in pit_map[pit_map['Driver'].isin(drivers)].iterrows():
        fig.add_vline(x=row['Pit Lap'], line=dict(color='rgba(255,107,53,0.6)', width=1.5, dash='dot'),
                      annotation_text=f"PIT {row['Driver']}", annotation_font=dict(size=8, color='#ff6b35'), row=1, col=1)

    fig.update_layout(
        title="Head-to-Head Race Pace", hovermode="x unified", height=700, bargap=0, margin=dict(t=100),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.04, xanchor="center", x=0.5,
            bgcolor="rgba(19, 19, 26, 0.9)", bordercolor="rgba(255,255,255,0.1)", borderwidth=1, font=dict(size=12)
        )
    )
    fig.update_yaxes(title_text="Lap Time (s)", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Track Temp (°C)", row=1, col=1, secondary_y=True, showgrid=False)
    fig.update_yaxes(tickvals=[1, 2, 3, 4], ticktext=["Clear", "Overcast", "Wet", "Red/Heavy"], row=2, col=1)
    fig.update_xaxes(title_text="Lap", row=2, col=1)
    
    return fig


def _quali_comparison_chart(comp, drivers, session, drv_colors, results_df, pit_map):
    comp = _create_hover_text(comp.copy())
    
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.04, row_heights=[0.8, 0.2],
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
    )

    symbols = ['circle', 'square', 'diamond', 'cross', 'x', 'triangle-up']
    
    for i, drv in enumerate(drivers):
        drv_sym = symbols[i % len(symbols)]
        drv_df = comp[comp['Driver'] == drv]
        
        for tyre in drv_df['Tyre'].unique():
            df_t = drv_df[drv_df['Tyre'] == tyre]
            color = drv_colors[drv]
            
            fig.add_trace(go.Scatter(
                x=df_t['LapNumber'], y=df_t['LapTime_s'], mode='markers',
                marker=dict(symbol=drv_sym, size=12, color=color, line=dict(width=1, color='rgba(255,255,255,0.4)')),
                name=f"{drv} ({tyre})", text=df_t['HoverText'], hovertemplate="%{text}<extra></extra>", legendgroup=drv
            ), row=1, col=1)

    dirty_laps = comp[comp['Is_Dirty_Air'] == True]
    if not dirty_laps.empty:
        fig.add_trace(go.Scatter(
            x=dirty_laps['LapNumber'], y=dirty_laps['LapTime_s'], mode='markers',
            marker=dict(size=15, color='rgba(150, 150, 150, 0.4)', line=dict(width=1.5, color='white')),
            name='Traffic / Dirty Air', hoverinfo='skip'
        ), row=1, col=1)

    if 'TrackTemp' in comp.columns:
        env_df = comp.groupby('LapNumber').agg({'TrackTemp': 'mean', 'W_Level': 'max', 'W_Desc': 'first'}).reset_index()
        fig.add_trace(go.Scatter(
            x=env_df['LapNumber'], y=env_df['TrackTemp'], mode='lines',
            line=dict(color='rgba(255, 107, 53, 0.35)', width=2, dash='dot'),
            name='Track Temp', hoverinfo='skip'
        ), row=1, col=1, secondary_y=True)
    else:
        env_df = comp.groupby('LapNumber').agg({'W_Level': 'max', 'W_Desc': 'first'}).reset_index()

    weather_color_map = {1: 'rgba(255, 215, 0, 0.7)', 2: 'rgba(150, 150, 150, 0.7)', 3: 'rgba(77, 184, 255, 0.8)', 4: 'rgba(0, 85, 255, 0.9)'}
    w_colors = env_df['W_Level'].map(weather_color_map).tolist()

    fig.add_trace(go.Bar(
        x=env_df['LapNumber'], y=env_df['W_Level'],
        marker_color=w_colors, marker_line_width=0, width=1,
        customdata=env_df['W_Desc'], hovertemplate="Lap %{x}<br>Weather: <b>%{customdata}</b><extra></extra>",
        showlegend=False
    ), row=2, col=1)

    all_laps = session.laps
    has_red = False
    
    for lap in all_laps['LapNumber'].dropna().unique():
        stat = "".join(all_laps[all_laps['LapNumber'] == lap]['TrackStatus'].dropna().astype(str).tolist())
        if '5' in stat: 
            has_red = True
            fig.add_vrect(x0=lap-0.5, x1=lap+0.5, fillcolor="rgba(232, 0, 45, 0.2)", layer="below", line_width=0, row=1, col=1)
            
    if has_red: fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(232, 0, 45, 0.4)", size=12, symbol="square"), name="Red Flag"))
    
    if hasattr(session, 'race_control_messages'):
        rcm = session.race_control_messages
        if rcm is not None and not rcm.empty:
            ref_laps = session.laps.pick_driver(drivers[0] if drivers else results_df.iloc[0]['Abbreviation'])
            ref_laps = ref_laps.sort_values('LapStartDate').dropna(subset=['LapStartDate', 'LapNumber'])
            
            for _, msg in rcm.iterrows():
                text = str(msg['Message']).upper()
                if "PENALTY" in text or "DELETED" in text or "BLACK AND WHITE" in text:
                    if not any(d in text for d in drivers): continue
                    idx = ref_laps['LapStartDate'].searchsorted(msg['Time'])
                    if 0 < idx < len(ref_laps):
                        lap_num = ref_laps.iloc[idx]['LapNumber']
                        color = "#e8002d" if ("PENALTY" in text or "DELETED" in text) else "#ffffff"
                        clean_text = text.replace("TIME PENALTY", "PENALTY").replace("CAR ", "").replace("LAP TIME DELETED", "DELETED")
                        
                        fig.add_vline(x=lap_num, line=dict(color=color, width=1.5, dash='dashdot'),
                                      annotation_text=clean_text,
                                      annotation_font=dict(size=9, color=color), annotation_textangle=-90, row=1, col=1)

    fig.update_layout(
        title="Head-to-Head Qualifying Trace", hovermode="x unified", height=700, bargap=0, margin=dict(t=100),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.04, xanchor="center", x=0.5,
            bgcolor="rgba(19, 19, 26, 0.9)", bordercolor="rgba(255,255,255,0.1)", borderwidth=1, font=dict(size=12)
        )
    )
    fig.update_yaxes(title_text="Lap Time (s)", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Track Temp (°C)", row=1, col=1, secondary_y=True, showgrid=False)
    fig.update_yaxes(tickvals=[1, 2, 3, 4], ticktext=["Clear", "Overcast", "Wet", "Red/Heavy"], row=2, col=1)
    fig.update_xaxes(title_text="Lap", row=2, col=1)
    
    return fig


# ─────────────────────────────────────────────────────────────
#  METRIC CARDS & TELEMETRY
# ─────────────────────────────────────────────────────────────
def _render_driver_cards(comp, fastest_overall, session, drivers, drv_colors, results_df):
    group_best = comp['LapTime_s'].min()
    group_avg  = comp.groupby('Driver')['LapTime_s'].mean().min()

    winner_id = None
    try:
        winner_id = session.results.sort_values('Position').iloc[0]['Abbreviation']
    except Exception:
        pass

    cols = st.columns(len(drivers))
    for i, drv in enumerate(drivers):
        d_laps = comp[comp['Driver'] == drv]
        color  = drv_colors[drv]
        trophy = "🏆 " if drv == winner_id else ""

        with cols[i]:
            st.markdown(
                f'<div style="border-left: 4px solid {color}; padding: 6px 12px; '
                f'background: rgba(255,255,255,0.03); border-radius: 0 4px 4px 0; '
                f'margin-bottom: 12px;">'
                f'<span style="font-size:1.3rem; font-weight:700; letter-spacing:0.1em; color:{color};">'
                f'{trophy}{drv}</span></div>',
                unsafe_allow_html=True,
            )

            if d_laps.empty:
                st.write("No valid laps.")
                continue

            d_best = d_laps['LapTime_s'].min()
            d_avg  = d_laps['LapTime_s'].mean()
            d_std  = d_laps['LapTime_s'].std()
            d_laps_count = len(d_laps)

            pos_str = "–"
            try:
                row = session.results[session.results['Abbreviation'] == drv]
                if not row.empty:
                    p = row.iloc[0].get('Position', None)
                    pos_str = f"P{int(p)}" if pd.notna(p) else "–"
            except Exception:
                pass

            b_delta = d_best - group_best
            a_delta = d_avg  - group_avg

            st.metric("Best Lap",
                      format_time(d_best),
                      "Group Fastest" if abs(b_delta) < 0.001 else f"+{b_delta:.3f}s",
                      delta_color="normal" if abs(b_delta) < 0.001 else "inverse")

            st.metric("Avg Pace",
                      format_time(d_avg),
                      "Group Fastest" if abs(a_delta) < 0.001 else f"+{a_delta:.3f}s",
                      delta_color="normal" if abs(a_delta) < 0.001 else "inverse")

            st.metric("Consistency σ", f"{d_std:.3f}s")
            st.metric("Clean Laps",    str(d_laps_count))
            st.metric("Finish",        pos_str)

def _render_distribution(comp, drivers, drv_colors):
    traces = []
    for drv in drivers:
        d = comp[comp['Driver'] == drv]['LapTime_s'].dropna()
        d_datetime = pd.to_datetime(d, unit='s')
        color = drv_colors[drv]
        
        if color.startswith('#') and len(color) == 7:
            r = int(color[1:3], 16); g = int(color[3:5], 16); b = int(color[5:7], 16)
            fill_color = f'rgba({r},{g},{b},0.3)'
        else:
            fill_color = color

        traces.append(go.Violin(
            y=d_datetime, name=drv, box_visible=True, meanline_visible=True,
            fillcolor=fill_color, line_color=color, points='outliers', pointpos=0,
            text=comp[comp['Driver'] == drv]['LapTime_str']
        ))

    fig = go.Figure(data=traces)
    fig.update_layout(
        **PLOTLY_THEME, height=420,
        title="Lap Time Distribution (violin + box)",
        yaxis_title="Lap Time", showlegend=True,
    )
    fig.update_yaxes(tickformat="%M:%S.%L")
    st.plotly_chart(fig, use_container_width=True)

def _render_lap_delta(comp, drivers, drv_colors):
    d1, d2 = drivers[0], drivers[1]
    laps1 = (comp[comp['Driver'] == d1][['LapNumber', 'LapTime_s']]
             .set_index('LapNumber').sort_index())
    laps2 = (comp[comp['Driver'] == d2][['LapNumber', 'LapTime_s']]
             .set_index('LapNumber').sort_index())

    merged = laps1.join(laps2, how='inner', lsuffix='_d1', rsuffix='_d2')
    if merged.empty:
        st.info("Insufficient overlapping laps for delta chart.")
        return

    merged['Delta'] = merged['LapTime_s_d1'] - merged['LapTime_s_d2']
    merged = merged.reset_index()

    color1 = drv_colors[d1]
    color2 = drv_colors[d2]

    fig = go.Figure()
    fig.add_hline(y=0, line=dict(color='rgba(255,255,255,0.2)', width=1.5))
    fig.add_bar(
        x=merged['LapNumber'],
        y=merged['Delta'],
        marker_color=[color1 if v > 0 else color2 for v in merged['Delta']],
        hovertemplate=f"Lap %{{x}}<br>{d1} vs {d2}: %{{y:.3f}}s<extra></extra>",
    )
    fig.add_annotation(
        x=0.01, y=0.95, xref='paper', yref='paper',
        text=f"<b>{d1}</b> faster ↑ | <b>{d2}</b> faster ↓",
        showarrow=False,
        font=dict(size=11, color='#888'),
    )
    fig.update_layout(
        **PLOTLY_THEME, height=380,
        title=f"Per-Lap Delta: {d1} minus {d2}",
        xaxis_title="Lap", yaxis_title="Delta (s)",
        bargap=0.2,
    )
    st.plotly_chart(fig, use_container_width=True)

def _render_stint_table(comp, pit_map, fastest_overall):
    stats = (comp.groupby(['Driver', 'Tyre', 'Stint'])
             .agg(Laps=('LapNumber', 'count'),
                  Best_s=('LapTime_s', 'min'),
                  Avg_s=('LapTime_s', 'mean'),
                  Std_s=('LapTime_s', 'std'))
             .reset_index())

    stats['Best Lap']      = stats['Best_s'].apply(format_time)
    stats['Avg Pace']      = stats['Avg_s'].apply(format_time)
    stats['Consistency σ'] = stats['Std_s'].round(3).astype(str) + ' s'
    stats['Δ vs Best']     = (stats['Best_s'] - fastest_overall).round(3).astype(str) + ' s'
    stats['Δ Avg vs Best'] = (stats['Avg_s']  - fastest_overall).round(3).astype(str) + ' s'
    stats['Deg Rate']      = ((stats['Avg_s'] - stats['Best_s']) / stats['Laps'].clip(lower=1)).round(3).astype(str) + ' s/lap'

    stats = stats.merge(pit_map, on=['Driver', 'Stint'], how='left')
    stats['Pit Lap'] = stats['Pit Lap'].apply(
        lambda x: str(int(x)) if pd.notna(x) else 'Final Stint')

    if 'Avg_s' in stats.columns and 'Stint' in stats.columns:
        stats = stats.sort_values(['Stint', 'Avg_s'])

    display = stats[['Driver', 'Stint', 'Tyre', 'Laps',
                      'Best Lap', 'Avg Pace', 'Consistency σ', 'Deg Rate',
                      'Δ vs Best', 'Δ Avg vs Best', 'Pit Lap']]
                      
    st.dataframe(display, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────
#  TELEMETRY COMPARISON
# ─────────────────────────────────────────────────────────────
def _render_telemetry_comparison(session, drivers, drv_colors):
    fig = make_subplots(
        rows=6, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03,
        row_heights=[0.25, 0.15, 0.15, 0.15, 0.15, 0.15]
    )
    
    valid_traces = 0
    
    for drv in drivers:
        try:
            f1_lap = session.laps.pick_driver(drv).pick_fastest()
            if pd.isna(f1_lap['LapTime']): continue
            tel = f1_lap.get_telemetry()
            tel = enrich_telemetry(tel)
        except Exception:
            continue
            
        valid_traces += 1
        color = drv_colors[drv]
        lap_num = int(f1_lap['LapNumber'])
        name_lbl = f"{drv} (Lap {lap_num})"
        
        # Base Speed Trace (SOLID LINES)
        fig.add_trace(go.Scatter(
            x=tel['Distance'], y=tel['Speed'], name=name_lbl, 
            line=dict(color=color, width=2.5, dash='solid'), legendgroup=drv
        ), row=1, col=1)
        
        # ── OVERLAY: DRS ACTIVE HIGHLIGHT ──
        if 'DRS' in tel.columns:
            drs_active = tel['DRS'] >= 10
            if drs_active.any():
                drs_speed = tel['Speed'].copy()
                drs_speed.loc[~drs_active] = np.nan
                fig.add_trace(go.Scatter(
                    x=tel['Distance'], y=drs_speed, mode='lines',
                    line=dict(color='#00d47e', width=4, dash='dot'),
                    name=f"{name_lbl} (DRS)", legendgroup=drv, 
                    showlegend=False, hoverinfo='skip'
                ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=tel['Distance'], y=tel['Throttle'], name=name_lbl, 
            line=dict(color=color, width=2, dash='solid'), legendgroup=drv, showlegend=False
        ), row=2, col=1)
        
        fig.add_trace(go.Scatter(
            x=tel['Distance'], y=tel['Brake'], name=name_lbl, 
            line=dict(color=color, width=2, dash='solid'), legendgroup=drv, showlegend=False
        ), row=3, col=1)
        
        fig.add_trace(go.Scatter(
            x=tel['Distance'], y=tel['nGear'], name=name_lbl, 
            line=dict(color=color, width=2.5, shape='hv', dash='solid'), legendgroup=drv, showlegend=False
        ), row=4, col=1)
        
        fig.add_trace(go.Scatter(
            x=tel['Distance'], y=tel['RPM'], name=name_lbl, 
            line=dict(color=color, width=2, dash='solid'), legendgroup=drv, showlegend=False
        ), row=5, col=1)
        
        fig.add_trace(go.Scatter(
            x=tel['Distance'], y=tel['Long_G'], name=name_lbl, 
            line=dict(color=color, width=2, dash='solid'), legendgroup=drv, showlegend=False
        ), row=6, col=1)

    if valid_traces == 0:
        st.info("Telemetry data is not available for the selected drivers.")
        return
        
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(255, 255, 255, 0.3)", row=6, col=1)
        
    fig.update_layout(
        **PLOTLY_THEME, height=1100, title="Head-to-Head: Fastest Lap Telemetry", hovermode="x unified",
        margin=dict(t=100),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.03, xanchor="center", x=0.5,
            bgcolor="rgba(19, 19, 26, 0.9)", bordercolor="rgba(255,255,255,0.1)", borderwidth=1, font=dict(size=13)
        )
    )
    
    fig.update_yaxes(title_text="Speed", row=1, col=1)
    fig.update_yaxes(title_text="Throttle", row=2, col=1, range=[-5, 105])
    fig.update_yaxes(title_text="Brake", row=3, col=1, range=[-0.1, 1.2], tickvals=[0, 1])
    fig.update_yaxes(title_text="Gear", row=4, col=1, range=[0, 9], tickvals=[1,2,3,4,5,6,7,8])
    fig.update_yaxes(title_text="RPM", row=5, col=1)
    fig.update_yaxes(title_text="G-Force", row=6, col=1, range=[-6, 3])
    
    fig.update_xaxes(title_text="Track Distance (m)", row=6, col=1)
    
    st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────
#  MINISECTOR TRACK MAP COMPARISON
# ─────────────────────────────────────────────────────────────
def _render_trackmap_comparison(session, drivers, drv_colors):
    lap_data = {}
    ref_driver = None
    max_distance = 0
    
    for drv in drivers:
        try:
            f1_lap = session.laps.pick_driver(drv).pick_fastest()
            if pd.isna(f1_lap['LapTime']): continue
            tel = f1_lap.get_telemetry()
            if tel.empty or 'Distance' not in tel or 'X' not in tel: continue
            
            lap_data[drv] = tel
            if ref_driver is None or f1_lap['LapTime'] < session.laps.pick_driver(ref_driver).pick_fastest()['LapTime']:
                ref_driver = drv
                max_distance = tel['Distance'].max()
        except Exception:
            continue

    if not lap_data or ref_driver is None:
        st.info("Track layout telemetry is not available for the selected drivers.")
        return

    num_sectors = 25
    sector_edges = np.linspace(0, max_distance, num_sectors + 1)
    ref_tel = lap_data[ref_driver]
    
    dominance_counts = {drv: 0 for drv in drivers}
    sector_winners = []
    
    for s in range(num_sectors):
        start_dist = sector_edges[s]
        end_dist = sector_edges[s+1]
        best_speed = -1
        winner = None
        
        for drv, tel in lap_data.items():
            sector_pts = tel[(tel['Distance'] >= start_dist) & (tel['Distance'] < end_dist)]
            if not sector_pts.empty:
                avg_speed = sector_pts['Speed'].mean()
                if avg_speed > best_speed:
                    best_speed = avg_speed
                    winner = drv
        
        if winner:
            dominance_counts[winner] += 1
            sector_winners.append((winner, start_dist, end_dist, best_speed, s+1))
        else:
            sector_winners.append((ref_driver, start_dist, end_dist, 0, s+1))

    fig = go.Figure()
    
    # 1. Background Track Outline (Faint)
    fig.add_trace(go.Scatter(
        x=ref_tel['X'], y=ref_tel['Y'], mode='lines',
        line=dict(color='rgba(255, 255, 255, 0.15)', width=8),
        hoverinfo='skip', showlegend=False
    ))

    # 2. Add Dummy Traces for Clean Legend
    for drv in drivers:
        perc = (dominance_counts.get(drv, 0) / num_sectors) * 100
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='lines',
            line=dict(color=drv_colors[drv], width=5),
            name=f"{drv} ({perc:.0f}%)"
        ))

    # 3. Draw Solid Colored Minisectors Over Background
    for winner, start, end, speed, s_idx in sector_winners:
        geo_pts = ref_tel[(ref_tel['Distance'] >= start) & (ref_tel['Distance'] <= end)]
        if geo_pts.empty: continue
            
        color = drv_colors[winner]
        fig.add_trace(go.Scatter(
            x=geo_pts['X'], y=geo_pts['Y'], mode='lines',
            line=dict(color=color, width=5),
            hoverinfo='text',
            text=f"Mini-Sector {s_idx}<br>Dominating: {winner}<br>Avg Speed: {speed:.1f} km/h",
            showlegend=False
        ))

    # 4. Start/Finish Marker
    start_pt = ref_tel.iloc[0]
    fig.add_trace(go.Scatter(
        x=[start_pt['X']], y=[start_pt['Y']], mode='markers',
        marker=dict(symbol='diamond', size=14, color='#ffffff', line=dict(width=2, color='#13131a')),
        name='Start/Finish', hoverinfo='skip'
    ))

    fig.update_layout(
        **PLOTLY_THEME, height=750, title="Spatial Analysis: Track Map Mini-Sector Dominance", hovermode="closest",
        margin=dict(t=100, b=20, l=20, r=20),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
            bgcolor="rgba(19, 19, 26, 0.9)", bordercolor="rgba(255,255,255,0.1)", borderwidth=1, font=dict(size=13)
        )
    )
    
    fig.update_layout(
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x", scaleratio=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)