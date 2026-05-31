"""
plot.py — Advanced Pace Trace module for PitWall Analytics
"""
import streamlit as st
import pandas as pd
import numpy as np
import fastf1
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils import (
    format_time, apply_tyre_labels, extract_pit_map,
    filter_clean_laps, safe_load_session, TYRE_COLORS,
    PLOTLY_THEME, section_header, no_data_error, delta_str
)

def get_accurate_driver_color(drv, results_df=None):
    """Safely extracts valid hex colors directly from official timing data."""
    try:
        if results_df is not None and not results_df.empty:
            c = results_df.loc[results_df['Abbreviation'] == drv, 'TeamColor'].values[0]
            if pd.notna(c) and str(c).strip() != "": 
                return f"#{c}" if not str(c).startswith('#') else str(c)
    except: pass
    try:
        c = fastf1.plotting.driver_color(drv)
        return f"#{c}" if not str(c).startswith('#') else str(c)
    except: return "#ffffff"

def render_plot(year, race, session_id, session_name, selected_driver, available_drivers, show_annotations=True):
    section_header("PACE TRACE", f"{year} {race}  ·  {session_name}")

    # ── 1. LOAD DATA & WEATHER ───────────────────────────
    session, laps, err = safe_load_session(year, race, session_id, messages=True, weather=True)
    if err:
        no_data_error(err)
        return

    results_df = getattr(session, 'results', pd.DataFrame())

    # ── 1.5 MERGE WEATHER DATA SAFELY ────────────────────
    if not laps.empty:
        try:
            weather_df = laps.get_weather_data()
            for col in weather_df.columns:
                if col not in laps.columns:
                    laps[col] = weather_df[col].values
        except Exception:
            pass # Failsafe if meteorological data is missing

    # ── 1.6 LIVE TIMING SECTOR ENGINE (Purple/Green) ─────
    laps_sorted = laps.dropna(subset=['Time']).sort_values('Time').copy()
    
    for col in ['Sector1Time', 'Sector2Time', 'Sector3Time']:
        s_col = f"{col[:7]}_s"
        laps_sorted[s_col] = laps_sorted[col].dt.total_seconds()
        
    # Calculate Session Bests (Cumulative)
    laps_sorted['Session_S1'] = laps_sorted['Sector1_s'].cummin()
    laps_sorted['Session_S2'] = laps_sorted['Sector2_s'].cummin()
    laps_sorted['Session_S3'] = laps_sorted['Sector3_s'].cummin()
    
    # Calculate Personal Bests (Cumulative)
    laps_sorted['PB_S1'] = laps_sorted.groupby('Driver')['Sector1_s'].cummin()
    laps_sorted['PB_S2'] = laps_sorted.groupby('Driver')['Sector2_s'].cummin()
    laps_sorted['PB_S3'] = laps_sorted.groupby('Driver')['Sector3_s'].cummin()

    # Calculate Gap to Ahead (Dirty Air)
    laps_sorted['GapToAhead'] = laps_sorted['Time'].diff().dt.total_seconds()
    laps_sorted['Is_Dirty_Air'] = laps_sorted['GapToAhead'] < 2.0

    laps = laps_sorted.sort_index()
    pit_map = extract_pit_map(laps)
    laps['Stint'] = laps['Stint'].fillna(0).astype(int)
    fastest_overall = laps['LapTime_s'].min()
    
    clean = filter_clean_laps(laps)
    clean = apply_tyre_labels(clean)
    clean['LapTime_str'] = clean['LapTime_s'].apply(format_time)

    if selected_driver != "ALL":
        plot_laps = clean[clean['Driver'] == selected_driver].copy()
    else:
        plot_laps = clean.copy()

    if plot_laps.empty:
        no_data_error("No valid lap data for selected driver.")
        return

    is_race = session_id in ['R', 'S', 'SQ']

    # ── 2. TOP METRICS ────────────────────────────────────
    if selected_driver != "ALL":
        _render_driver_metrics(plot_laps, fastest_overall, session, selected_driver, results_df)
    else:
        _render_grid_metrics(clean, fastest_overall, session, results_df)

    st.divider()

    # ── 3. CHART ──────────────────────────────────────────
    if is_race:
        fig = _race_trace_advanced(plot_laps, selected_driver, session_name, show_annotations, pit_map, session, results_df)
    else:
        fig = _quali_scatter_advanced(plot_laps, selected_driver, session_name, show_annotations, session, results_df)

    fig.update_layout(**PLOTLY_THEME)
    st.plotly_chart(fig, use_container_width=True)

    # ── 4. STINT TABLE ────────────────────────────────────
    st.divider()
    section_header("ANALYTICS", "Stint Breakdown")
    _render_stint_table(plot_laps, pit_map, fastest_overall)

    # ── 5. LAP DELTA WATERFALL (single driver) ────────────
    if selected_driver != "ALL" and is_race:
        st.divider()
        section_header("ANALYTICS", "Lap Delta vs Session Best")
        _render_delta_chart(plot_laps, fastest_overall)


# ─────────────────────────────────────────────────────────────
#  ADVANCED RACE TRACE
# ─────────────────────────────────────────────────────────────
def _race_trace_advanced(plot_laps, selected_driver, session_name, show_annotations, pit_map, session, results_df):
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

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.04, row_heights=[0.8, 0.2],
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
    )

    if selected_driver != "ALL":
        for stint in plot_laps['Stint'].unique():
            df_s = plot_laps[plot_laps['Stint'] == stint]
            color = TYRE_COLORS.get(df_s['Tyre'].iloc[0], '#ffffff')
            fig.add_trace(go.Scatter(
                x=df_s['LapNumber'], y=df_s['LapTime_s'], mode='lines+markers',
                marker=dict(size=6), line=dict(color=color, width=2),
                name=f"Stint {stint} ({df_s['Tyre'].iloc[0]})",
                text=df_s['HoverText'], hovertemplate="%{text}<extra></extra>"
            ), row=1, col=1)
    else:
        for drv in plot_laps['Driver'].unique():
            df_d = plot_laps[plot_laps['Driver'] == drv]
            color = get_accurate_driver_color(drv, results_df)
            fig.add_trace(go.Scatter(
                x=df_d['LapNumber'], y=df_d['LapTime_s'], mode='lines+markers',
                marker=dict(size=4), line=dict(color=color, width=1.5),
                name=drv, text=df_d['HoverText'], hovertemplate="%{text}<extra></extra>"
            ), row=1, col=1)
            
    if 'TrackTemp' in plot_laps.columns:
        env_df = plot_laps.groupby('LapNumber').agg({'TrackTemp': 'mean', 'W_Level': 'max', 'W_Desc': 'first'}).reset_index()
        fig.add_trace(go.Scatter(
            x=env_df['LapNumber'], y=env_df['TrackTemp'], mode='lines',
            line=dict(color='rgba(255, 107, 53, 0.35)', width=2, dash='dot'),
            name='Track Temp', hoverinfo='skip'
        ), row=1, col=1, secondary_y=True)
    else:
        env_df = plot_laps.groupby('LapNumber').agg({'W_Level': 'max', 'W_Desc': 'first'}).reset_index()

    weather_color_map = {
        1: 'rgba(255, 215, 0, 0.7)',    
        2: 'rgba(150, 150, 150, 0.7)',  
        3: 'rgba(77, 184, 255, 0.8)',   
        4: 'rgba(0, 85, 255, 0.9)'      
    }
    w_colors = env_df['W_Level'].map(weather_color_map).tolist()

    fig.add_trace(go.Bar(
        x=env_df['LapNumber'], y=env_df['W_Level'],
        marker_color=w_colors, marker_line_width=0, width=1,
        customdata=env_df['W_Desc'],
        hovertemplate="Lap %{x}<br>Weather: <b>%{customdata}</b><extra></extra>",
        showlegend=False
    ), row=2, col=1)

    unique_w_levels = env_df['W_Level'].unique()
    if 1 in unique_w_levels: fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(255, 215, 0, 0.7)", size=12, symbol="square"), name="Clear / Dry"))
    if 2 in unique_w_levels: fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(150, 150, 150, 0.7)", size=12, symbol="square"), name="Cool / Overcast"))
    if 3 in unique_w_levels: fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(77, 184, 255, 0.8)", size=12, symbol="square"), name="Wet / Damp"))
    if 4 in unique_w_levels: fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(0, 85, 255, 0.9)", size=12, symbol="square"), name="Heavy Rain"))

    if show_annotations:
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
                ref_laps = session.laps.pick_driver(selected_driver if selected_driver != "ALL" else results_df.iloc[0]['Abbreviation'])
                ref_laps = ref_laps.sort_values('LapStartDate').dropna(subset=['LapStartDate', 'LapNumber'])
                
                for _, msg in rcm.iterrows():
                    text = str(msg['Message']).upper()
                    if "PENALTY" in text or "BLACK AND WHITE" in text:
                        if selected_driver != "ALL" and selected_driver not in text: continue
                        
                        idx = ref_laps['LapStartDate'].searchsorted(msg['Time'])
                        if 0 < idx < len(ref_laps):
                            lap_num = ref_laps.iloc[idx]['LapNumber']
                            color = "#e8002d" if "PENALTY" in text else "#ffffff"
                            fig.add_vline(x=lap_num, line=dict(color=color, width=1.5, dash='dashdot'),
                                          annotation_text=text.replace("TIME PENALTY", "PENALTY").replace("CAR ", ""),
                                          annotation_font=dict(size=9, color=color), annotation_textangle=-90, row=1, col=1)
                                          
        # Draw Pit Stops with distinct driver colors and no text
        for _, row in pit_map.iterrows():
            if selected_driver != "ALL" and row['Driver'] != selected_driver:
                continue
            color = get_accurate_driver_color(row['Driver'], results_df)
            fig.add_vline(x=row['Pit Lap'], line=dict(color=color, width=2.5, dash='dot'), row=1, col=1)

    title = f"Race Pace Trace & Environmental Data · {selected_driver if selected_driver != 'ALL' else session_name}"
    
    fig.update_layout(title=title, hovermode="x unified", height=700, bargap=0)
    fig.update_yaxes(title_text="Lap Time (s)", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Track Temp (°C)", row=1, col=1, secondary_y=True, showgrid=False)
    fig.update_yaxes(tickvals=[1, 2, 3, 4], ticktext=["Clear", "Overcast", "Wet", "Red/Heavy"], row=2, col=1)
    fig.update_xaxes(title_text="Lap", row=2, col=1)
    
    return fig


# ─────────────────────────────────────────────────────────────
#  ADVANCED QUALIFYING TRACE
# ─────────────────────────────────────────────────────────────
def _quali_scatter_advanced(plot_laps, selected_driver, session_name, show_annotations, session, results_df):
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

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.04, row_heights=[0.8, 0.2],
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
    )

    # Scatter plot for Qualifying
    if selected_driver != "ALL":
        for tyre in plot_laps['Tyre'].unique():
            df_t = plot_laps[plot_laps['Tyre'] == tyre]
            color = TYRE_COLORS.get(tyre, '#ffffff')
            fig.add_trace(go.Scatter(
                x=df_t['LapNumber'], y=df_t['LapTime_s'], mode='markers',
                marker=dict(size=11, line=dict(width=1, color='rgba(255,255,255,0.2)'), color=color),
                name=tyre, text=df_t['HoverText'], hovertemplate="%{text}<extra></extra>"
            ), row=1, col=1)
    else:
        for drv in plot_laps['Driver'].unique():
            df_d = plot_laps[plot_laps['Driver'] == drv]
            color = get_accurate_driver_color(drv, results_df)
            fig.add_trace(go.Scatter(
                x=df_d['LapNumber'], y=df_d['LapTime_s'], mode='markers',
                marker=dict(size=9, line=dict(width=1, color='rgba(255,255,255,0.2)'), color=color),
                name=drv, text=df_d['HoverText'], hovertemplate="%{text}<extra></extra>"
            ), row=1, col=1)
            
    # Dirty Air Overlay
    dirty_laps = plot_laps[plot_laps['Is_Dirty_Air'] == True]
    if not dirty_laps.empty:
        fig.add_trace(go.Scatter(
            x=dirty_laps['LapNumber'], y=dirty_laps['LapTime_s'], mode='markers',
            marker=dict(size=14, color='rgba(150, 150, 150, 0.4)', line=dict(width=1.5, color='white')),
            name='Traffic / Dirty Air', hoverinfo='skip'
        ), row=1, col=1)

    if 'TrackTemp' in plot_laps.columns:
        env_df = plot_laps.groupby('LapNumber').agg({'TrackTemp': 'mean', 'W_Level': 'max', 'W_Desc': 'first'}).reset_index()
        fig.add_trace(go.Scatter(
            x=env_df['LapNumber'], y=env_df['TrackTemp'], mode='lines',
            line=dict(color='rgba(255, 107, 53, 0.35)', width=2, dash='dot'),
            name='Track Temp', hoverinfo='skip'
        ), row=1, col=1, secondary_y=True)
    else:
        env_df = plot_laps.groupby('LapNumber').agg({'W_Level': 'max', 'W_Desc': 'first'}).reset_index()

    weather_color_map = {
        1: 'rgba(255, 215, 0, 0.7)',    
        2: 'rgba(150, 150, 150, 0.7)',  
        3: 'rgba(77, 184, 255, 0.8)',   
        4: 'rgba(0, 85, 255, 0.9)'      
    }
    w_colors = env_df['W_Level'].map(weather_color_map).tolist()

    fig.add_trace(go.Bar(
        x=env_df['LapNumber'], y=env_df['W_Level'],
        marker_color=w_colors, marker_line_width=0, width=1,
        customdata=env_df['W_Desc'], hovertemplate="Lap %{x}<br>Weather: <b>%{customdata}</b><extra></extra>",
        showlegend=False
    ), row=2, col=1)

    unique_w_levels = env_df['W_Level'].unique()
    if 1 in unique_w_levels: fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(255, 215, 0, 0.7)", size=12, symbol="square"), name="Clear / Dry"))
    if 2 in unique_w_levels: fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(150, 150, 150, 0.7)", size=12, symbol="square"), name="Cool / Overcast"))
    if 3 in unique_w_levels: fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(77, 184, 255, 0.8)", size=12, symbol="square"), name="Wet / Damp"))
    if 4 in unique_w_levels: fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(0, 85, 255, 0.9)", size=12, symbol="square"), name="Heavy Rain"))

    if show_annotations:
        all_laps = session.laps
        has_red = False
        
        # Red flags are most critical in Qualifying
        for lap in all_laps['LapNumber'].dropna().unique():
            stat = "".join(all_laps[all_laps['LapNumber'] == lap]['TrackStatus'].dropna().astype(str).tolist())
            if '5' in stat: 
                has_red = True
                fig.add_vrect(x0=lap-0.5, x1=lap+0.5, fillcolor="rgba(232, 0, 45, 0.2)", layer="below", line_width=0, row=1, col=1)
        
        if has_red: fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(232, 0, 45, 0.4)", size=12, symbol="square"), name="Red Flag"))
        
        if hasattr(session, 'race_control_messages'):
            rcm = session.race_control_messages
            if rcm is not None and not rcm.empty:
                ref_laps = session.laps.pick_driver(selected_driver if selected_driver != "ALL" else results_df.iloc[0]['Abbreviation'])
                ref_laps = ref_laps.sort_values('LapStartDate').dropna(subset=['LapStartDate', 'LapNumber'])
                
                for _, msg in rcm.iterrows():
                    text = str(msg['Message']).upper()
                    # Included 'DELETED' specifically for Track Limits violations in Quali
                    if "PENALTY" in text or "DELETED" in text or "BLACK AND WHITE" in text:
                        if selected_driver != "ALL" and selected_driver not in text: continue
                        
                        idx = ref_laps['LapStartDate'].searchsorted(msg['Time'])
                        if 0 < idx < len(ref_laps):
                            lap_num = ref_laps.iloc[idx]['LapNumber']
                            color = "#e8002d" if ("PENALTY" in text or "DELETED" in text) else "#ffffff"
                            clean_text = text.replace("TIME PENALTY", "PENALTY").replace("CAR ", "").replace("LAP TIME DELETED", "DELETED")
                            
                            fig.add_vline(x=lap_num, line=dict(color=color, width=1.5, dash='dashdot'),
                                          annotation_text=clean_text,
                                          annotation_font=dict(size=9, color=color), annotation_textangle=-90, row=1, col=1)

    title = f"Qualifying Trace & Environmental Data · {selected_driver if selected_driver != 'ALL' else session_name}"
    
    fig.update_layout(title=title, hovermode="x unified", height=700, bargap=0)
    fig.update_yaxes(title_text="Lap Time (s)", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Track Temp (°C)", row=1, col=1, secondary_y=True, showgrid=False)
    fig.update_yaxes(tickvals=[1, 2, 3, 4], ticktext=["Clear", "Overcast", "Wet", "Red/Heavy"], row=2, col=1)
    fig.update_xaxes(title_text="Lap", row=2, col=1)
    
    return fig


# ─────────────────────────────────────────────────────────────
#  METRIC CARDS & DISTRIBUTION (Unchanged below)
# ─────────────────────────────────────────────────────────────
def _render_driver_metrics(laps, fastest_overall, session, driver, results_df):
    best = laps['LapTime_s'].min()
    avg  = laps['LapTime_s'].mean()
    std  = laps['LapTime_s'].std()
    total_laps = len(laps)
    num_stints = laps['Stint'].nunique()

    pos = None
    try:
        row = session.results[session.results['Abbreviation'] == driver]
        if not row.empty:
            pos = row.iloc[0].get('Position', None)
            pos = int(pos) if pd.notna(pos) else None
    except Exception:
        pass

    cols = st.columns(5)
    metrics = [
        ("Best Lap",       format_time(best),    delta_str(best, fastest_overall), True),
        ("Avg Pace",       format_time(avg),      delta_str(avg, fastest_overall),  True),
        ("Consistency σ",  f"{std:.3f}s",         None,                             None),
        ("Total Laps",     str(total_laps),       None,                             None),
        ("Stints",         str(num_stints),        None,                             None),
    ]
    if pos is not None:
        metrics[-1] = ("Finish Pos.", f"P{pos}", None, None)

    for i, (label, val, delta, inv) in enumerate(metrics):
        with cols[i]:
            if delta and delta != "–":
                st.metric(label, val, delta, delta_color="inverse" if inv else "normal")
            else:
                st.metric(label, val)

def _render_grid_metrics(clean, fastest_overall, session, results_df):
    total_drivers = clean['Driver'].nunique()
    total_laps    = len(clean)
    fastest_drv   = clean.loc[clean['LapTime_s'].idxmin(), 'Driver']
    compounds     = clean['Compound'].nunique()

    cols = st.columns(5)
    with cols[0]: st.metric("Drivers Tracked", str(total_drivers))
    with cols[1]: st.metric("Clean Laps", str(total_laps))
    with cols[2]: st.metric("Fastest Driver", fastest_drv)
    with cols[3]: st.metric("Session Best", format_time(fastest_overall))
    with cols[4]: st.metric("Compounds Used", str(compounds))

def _render_stint_table(plot_laps, pit_map, fastest_overall):
    stats = (plot_laps.groupby(['Driver', 'Tyre', 'Stint'])
             .agg(Laps=('LapNumber', 'count'), Best_s=('LapTime_s', 'min'),
                  Avg_s=('LapTime_s', 'mean'), Std_s=('LapTime_s', 'std'),
                  Min_Lap=('LapNumber', 'min'), Max_Lap=('LapNumber', 'max'))
             .reset_index())

    stats['Best Lap'] = stats['Best_s'].apply(format_time)
    stats['Avg Pace'] = stats['Avg_s'].apply(format_time)
    stats['Consistency σ'] = stats['Std_s'].round(3).astype(str) + ' s'
    stats['Δ Best'] = (stats['Best_s'] - fastest_overall).round(3).astype(str) + ' s'
    stats['Δ Avg'] = (stats['Avg_s'] - fastest_overall).round(3).astype(str) + ' s'
    stats['Lap Range'] = stats['Min_Lap'].astype(str) + '–' + stats['Max_Lap'].astype(str)
    stats['Deg Rate'] = ((stats['Avg_s'] - stats['Best_s']) / stats['Laps'].clip(lower=1)).round(3).astype(str) + ' s/lap'

    stats = stats.merge(pit_map, on=['Driver', 'Stint'], how='left')
    stats['Pit Lap'] = stats['Pit Lap'].apply(lambda x: str(int(x)) if pd.notna(x) else 'Final Stint')
    stats = stats.sort_values(['Stint', 'Avg_s'])

    display = stats[['Driver', 'Tyre', 'Stint', 'Lap Range', 'Laps', 'Best Lap', 'Avg Pace', 'Consistency σ', 'Deg Rate', 'Δ Best', 'Δ Avg', 'Pit Lap']]
    st.dataframe(display, use_container_width=True, hide_index=True)

def _render_delta_chart(plot_laps, fastest_overall):
    df = plot_laps.copy().sort_values('LapNumber')
    df['Delta'] = df['LapTime_s'] - fastest_overall
    colors = ['#e8002d' if d > 2.0 else '#ff6b35' if d > 0.5 else '#00d47e' for d in df['Delta']]

    fig = go.Figure(go.Bar(
        x=df['LapNumber'], y=df['Delta'], marker_color=colors,
        text=[f"+{d:.2f}s" if d > 0 else f"{d:.2f}s" for d in df['Delta']], textposition='outside', textfont=dict(size=9),
        hovertemplate="Lap %{x}<br>Delta: +%{y:.3f}s<extra></extra>",
    ))
    fig.add_hline(y=0, line=dict(color='rgba(255,255,255,0.3)', width=1))
    fig.update_layout(**PLOTLY_THEME, height=540, title="Per-Lap Delta vs Session Best", xaxis_title="Lap", yaxis_title="Delta (s)", bargap=0.15)
    st.plotly_chart(fig, use_container_width=True)