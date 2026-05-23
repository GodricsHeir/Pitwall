"""
engineer.py — Raw Telemetry Deep Dive for PitWall Analytics
"""
import streamlit as st
import fastf1
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from utils import (
    section_header, no_data_error, PLOTLY_THEME, driver_color, format_time, TYRE_LABELS
)

def enrich_telemetry(telemetry_df):
    """Adds RPM handling and calculates Longitudinal G-Force safely, bypassing 2018 data quirks."""
    if telemetry_df is None or telemetry_df.empty:
        return telemetry_df
        
    try:
        # Safely extract channels, defaulting to 0 if missing in older datasets
        telemetry_df['RPM'] = pd.to_numeric(telemetry_df.get('RPM', 0), errors='coerce').fillna(0)
        speed = pd.to_numeric(telemetry_df.get('Speed', 0), errors='coerce').fillna(0)
        telemetry_df['Speed_ms'] = speed / 3.6
        
        if 'Time' in telemetry_df.columns:
            telemetry_df['Time_s'] = telemetry_df['Time'].dt.total_seconds()
            
            # CRITICAL 2018 FIX: Drop duplicate timestamps to prevent divide-by-zero in np.gradient
            telemetry_df = telemetry_df.drop_duplicates(subset=['Time_s']).copy()
            
            if len(telemetry_df) > 2:
                accel = np.gradient(telemetry_df['Speed_ms'], telemetry_df['Time_s'])
                telemetry_df['Long_G'] = (accel / 9.81)
                telemetry_df['Long_G'] = telemetry_df['Long_G'].rolling(window=3, min_periods=1).mean()
            else:
                telemetry_df['Long_G'] = 0
        else:
            telemetry_df['Long_G'] = 0
            
    except Exception as e:
        # Fallback if math fails entirely
        telemetry_df['Long_G'] = 0
        
    return telemetry_df

def _render_status_bubble(lap_data, weather_data=None):
    """Generates a color-coded status bar for a specific lap."""
    
    # 1. Track Status (SC/VSC/Yellow)
    track_status = str(lap_data.get('TrackStatus', '1'))
    is_sc = '4' in track_status or '6' in track_status or '7' in track_status
    is_yellow = '2' in track_status
    
    # Air Status (Defaults to Clean unless explicitly calculated in the DataFrame)
    is_dirty = lap_data.get('Is_Dirty_Air', False)
    
    if is_sc:
        status_text, status_color = "SC/VSC ACTIVE", "#ffd700"
    elif is_yellow:
        status_text, status_color = "YELLOW SECTOR", "#ffeb3b"
    else:
        status_text = "DIRTY AIR" if is_dirty else "CLEAN AIR"
        status_color = "#00d47e" if not is_dirty else "#e8002d"
    
    # 2. Tyre Data & Color Coding
    comp = str(lap_data.get('Compound', 'UNKNOWN')).upper()
    tyre_life = lap_data.get('TyreLife')
    age = int(tyre_life) if pd.notna(tyre_life) else 0
    
    # Dynamic Pirelli colors
    if 'SOFT' in comp: t_color = '#e8002d'       # Red
    elif 'MEDIUM' in comp: t_color = '#ffd700'   # Yellow
    elif 'HARD' in comp: t_color = '#e8e8f0'     # White
    elif 'INTER' in comp: t_color = '#00d47e'    # Green
    elif 'WET' in comp: t_color = '#4db8ff'      # Blue
    else: t_color = '#8888a0'                    # Fallback grey
    
    # 3. Environment (Match lap time to closest session weather reading)
    is_wet = False
    track_temp = None
    if weather_data is not None and not weather_data.empty:
        lap_time = lap_data.get('Time')
        if pd.notna(lap_time):
            try:
                # Find the weather timestamp closest to when this lap occurred
                idx = (weather_data['Time'] - lap_time).abs().idxmin()
                closest_weather = weather_data.loc[idx]
                is_wet = closest_weather.get('Rainfall', False)
                track_temp = closest_weather.get('TrackTemp')
            except Exception:
                pass

    weather = "🌧️ WET" if is_wet else "☀️ DRY"
    temp_html = f'<span style="color:#bbb; font-size:0.75rem; align-self:center;">TRACK TEMP: {track_temp:.1f}°C</span>' if pd.notna(track_temp) else ""
    
    # 4. Render HTML
    return f"""
    <div style="display:flex; flex-wrap:wrap; gap:12px; margin-bottom:20px; font-family:'JetBrains Mono',monospace;">
        <span style="color:{status_color}; border:1px solid {status_color}; padding:4px 10px; border-radius:4px; font-size:0.75rem; font-weight:700; background:{status_color}15;">{status_text}</span>
        <span style="color:#4db8ff; border:1px solid #4db8ff; padding:4px 10px; border-radius:4px; font-size:0.75rem; font-weight:700; background:rgba(77,184,255,0.1);">{weather}</span>
        <span style="color:{t_color}; border:1px solid {t_color}; padding:4px 10px; border-radius:4px; font-size:0.75rem; font-weight:700; background:{t_color}15;">{comp} (AGE: {age})</span>
        {temp_html}
    </div>
    """

def render_engineer(year, race, session_id, session_name, eng_driver):
    section_header("DRIVER TELEMETRY", f"{year} {race}  ·  {session_name}")
    st.markdown(f"#### Telemetry Deep Dive: {eng_driver}")

    # ── 1. LOAD WITH TELEMETRY ───────────────────────────
    try:
        session = fastf1.get_session(year, race, session_id)
        # Ensure weather=True is enabled to fetch track temperatures
        session.load(telemetry=True, weather=True, messages=False)
        laps = session.laps
        weather_data = session.weather_data
    except Exception as e:
        no_data_error(f"Failed to load telemetry: {e}")
        return

    # Filter to specific driver and drop laps that don't have telemetry
    driver_laps = laps[laps['Driver'] == eng_driver].copy()
    if driver_laps.empty:
        no_data_error(f"No lap data found for {eng_driver}.")
        return

    # ── 2. LAP SELECTION ─────────────────────────────────
    fastest_lap = driver_laps.loc[driver_laps['LapTime'].idxmin()]
    fastest_lap_num = int(fastest_lap['LapNumber'])

    st.markdown("##### Lap Selection")
    col1, col2 = st.columns([1, 3])
    with col1:
        lap_options = driver_laps['LapNumber'].dropna().astype(int).tolist()
        if not lap_options:
            no_data_error("No valid lap numbers found.")
            return
            
        selected_lap_num = st.selectbox(
            "Select Target Lap", 
            lap_options, 
            index=lap_options.index(fastest_lap_num) if fastest_lap_num in lap_options else 0
        )

    target_lap = driver_laps[driver_laps['LapNumber'] == selected_lap_num].iloc[0]

    # Render Context Bubble here
    st.markdown(_render_status_bubble(target_lap, weather_data), unsafe_allow_html=True)

    # ── 3. LAP METRICS & PIT TAGS ────────────────────────
    is_pit_out = pd.notna(target_lap['PitOutTime'])
    is_pit_in = pd.notna(target_lap['PitInTime'])

    pit_tags = []
    if is_pit_out: pit_tags.append("🟢 OUT LAP")
    if is_pit_in: pit_tags.append("🛑 PIT IN")
    pit_tag_str = " · ".join(pit_tags) if pit_tags else "🏁 FLYING LAP"

    t_time = format_time(target_lap['LapTime'].total_seconds()) if pd.notna(target_lap['LapTime']) else "INCOMPLETE"
    f_time = format_time(fastest_lap['LapTime'].total_seconds())

    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        st.metric("Target Lap (Selected)", f"Lap {selected_lap_num}", t_time)
        st.markdown(f"**Status:** {pit_tag_str}")
    with mc2:
        st.metric("Benchmark (Fastest)", f"Lap {fastest_lap_num}", f_time)
        st.markdown(f"**Compound:** {target_lap['Compound']}")
    with mc3:
        if pd.notna(target_lap['LapTime']) and pd.notna(fastest_lap['LapTime']):
            delta_s = target_lap['LapTime'].total_seconds() - fastest_lap['LapTime'].total_seconds()
            st.metric("Delta to Best", f"+{delta_s:.3f} s" if delta_s > 0 else f"{delta_s:.3f} s", delta_color="inverse")
        else:
            st.metric("Delta to Best", "N/A")

    if is_pit_in or is_pit_out:
        st.warning("⚠️ **Pit Lap Detected:** Track distance alignment will diverge from the benchmark lap due to the pit lane routing.")

    # ── 4. EXTRACT TELEMETRY ─────────────────────────────
    with st.spinner("Extracting 20Hz Telemetry..."):
        try:
            tel_fast = fastest_lap.get_telemetry()
            tel_target = target_lap.get_telemetry()
            
            # Enrich with RPM and G-Force safely
            tel_fast = enrich_telemetry(tel_fast)
            tel_target = enrich_telemetry(tel_target)
        except Exception as e:
            # Expose the specific error for debugging if it fully crashes
            no_data_error(f"Raw telemetry data is corrupted for the selected laps. Debug info: {e}")
            return

    d_color = driver_color(eng_driver, session.results)

    # ── 5. BUILD SUBPLOTS ────────────────────────────────
    fig = make_subplots(
        rows=6, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.25, 0.15, 0.15, 0.15, 0.15, 0.15]
    )

    def add_tel_traces(row_num, col_name, is_fastest=False, is_fill=False, is_step=False):
        if is_fastest:
            color = 'rgba(255, 255, 255, 0.35)'
            width = 1.5
            dash = 'dash'
            trace_name = f"<b>Best</b> (Lap {fastest_lap_num})"
            tel_data = tel_fast
        else:
            color = d_color if col_name != 'Brake' else '#e8002d'
            if col_name == 'Throttle': color = '#00d47e'
            if col_name == 'nGear': color = '#ffd700'
            width = 2
            dash = 'solid'
            trace_name = f"<b>Target</b> (Lap {selected_lap_num})"
            tel_data = tel_target

        line_opts = dict(color=color, width=width, dash=dash)
        if is_step: line_opts['shape'] = 'hv'

        # Safely GET channels so 2018 missing data doesn't crash Plotly
        y_data = tel_data.get(col_name, pd.Series(np.nan, index=tel_data.index))
        x_data = tel_data.get('Distance', tel_data.index)

        kwargs = dict(
            x=x_data,
            y=y_data,
            name=trace_name,
            line=line_opts,
            legendgroup=trace_name,
            showlegend=(row_num == 1) 
        )

        if is_fill and not is_fastest:
            kwargs['fill'] = 'tozeroy'
            kwargs['fillcolor'] = 'rgba(232,0,45,0.2)'

        fig.add_trace(go.Scatter(**kwargs), row=row_num, col=1)

        # ── OVERLAY: DRS ACTIVE HIGHLIGHT (SPEED ONLY) ──
        if col_name == 'Speed' and 'DRS' in tel_data.columns:
            drs_active = tel_data.get('DRS', 0) >= 10
            if drs_active.any():
                drs_speed = tel_data['Speed'].copy()
                drs_speed.loc[~drs_active] = np.nan
                
                fig.add_trace(go.Scatter(
                    x=x_data, y=drs_speed, mode='lines',
                    line=dict(color='#00d47e', width=width + 1.5, dash=dash),
                    name=f"{trace_name} (DRS Open)", legendgroup=trace_name,
                    showlegend=False, hoverinfo='skip'
                ), row=row_num, col=1)

    add_tel_traces(1, 'Speed', is_fastest=True)
    add_tel_traces(1, 'Speed')
    
    add_tel_traces(2, 'Throttle', is_fastest=True)
    add_tel_traces(2, 'Throttle')
    
    add_tel_traces(3, 'Brake', is_fastest=True)
    add_tel_traces(3, 'Brake', is_fill=True)
    
    add_tel_traces(4, 'nGear', is_fastest=True, is_step=True)
    add_tel_traces(4, 'nGear', is_step=True)
    
    add_tel_traces(5, 'RPM', is_fastest=True)
    add_tel_traces(5, 'RPM')
    
    add_tel_traces(6, 'Long_G', is_fastest=True)
    add_tel_traces(6, 'Long_G')

    # Add zero-line to G-force
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(255, 255, 255, 0.4)", row=6, col=1)

    # ── OVERLAY: SECTOR SHADING & LEGEND ICONS ──
    try:
        time_col = 'SessionTime' if 'SessionTime' in tel_fast.columns else 'Time'
        s1_time = fastest_lap.get('Sector1SessionTime')
        s2_time = fastest_lap.get('Sector2SessionTime')
        ref_s1 = tel_fast.loc[tel_fast[time_col] <= s1_time, 'Distance'].max() if pd.notna(s1_time) else None
        ref_s2 = tel_fast.loc[tel_fast[time_col] <= s2_time, 'Distance'].max() if pd.notna(s2_time) else None
        max_dist = tel_fast['Distance'].max()
        
        if ref_s1 and ref_s2 and max_dist:
            fig.add_vrect(x0=0, x1=ref_s1, fillcolor="rgba(232, 0, 45, 0.08)", layer="below", line_width=0)
            fig.add_vrect(x0=ref_s1, x1=ref_s2, fillcolor="rgba(63, 182, 220, 0.08)", layer="below", line_width=0)
            fig.add_vrect(x0=ref_s2, x1=max_dist, fillcolor="rgba(255, 215, 0, 0.06)", layer="below", line_width=0)
            
            # Sector Legend Traces
            fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(232, 0, 45, 0.5)", size=12, symbol="square"), name="Sector 1", showlegend=True), row=1, col=1)
            fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(63, 182, 220, 0.5)", size=12, symbol="square"), name="Sector 2", showlegend=True), row=1, col=1)
            fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(255, 215, 0, 0.5)", size=12, symbol="square"), name="Sector 3", showlegend=True), row=1, col=1)
    except Exception:
        pass

    # ── OVERLAY: CORNER NUMBERS & SEPARATORS ──
    try:
        circuit_info = session.get_circuit_info()
        if circuit_info is not None and not circuit_info.corners.empty:
            for _, corner in circuit_info.corners.iterrows():
                dist = corner['Distance']
                num = str(corner['Number'])
                fig.add_vline(x=dist, line_width=1.5, line_dash="dot", line_color="rgba(255, 255, 255, 0.35)")
                fig.add_annotation(
                    x=dist, y=1.0, yref="paper", text=f"<b>{num}</b>",
                    showarrow=False, xanchor="left", yanchor="bottom",
                    font=dict(size=14, color="rgba(255,255,255,0.95)")
                )
    except Exception:
        pass

    # ── 6. FORMATTING ────────────────────────────────────
    fig.update_layout(
        **PLOTLY_THEME,
        height=1100,
        title=f"<b>Telemetry Comparison: Lap {selected_lap_num} vs Fastest Lap ({fastest_lap_num})</b>",
        hovermode="x unified",
        margin=dict(t=110)
    )

    fig.update_layout(legend=dict(
        orientation="h", yanchor="bottom", y=1.04, xanchor="right", x=1,
        bgcolor="rgba(19, 19, 26, 0.95)", bordercolor="rgba(255,255,255,0.2)", borderwidth=1, font=dict(size=14)
    ))

    # Bold Axes labels
    fig.update_yaxes(title_text="<b>Speed (km/h)</b>", row=1, col=1)
    fig.update_yaxes(title_text="<b>Throttle %</b>", row=2, col=1, range=[-5, 105])
    fig.update_yaxes(title_text="<b>Brake</b>", row=3, col=1, range=[-0.1, 1.2], tickvals=[0, 1])
    fig.update_yaxes(title_text="<b>Gear</b>", row=4, col=1, range=[0, 9], tickvals=[1,2,3,4,5,6,7,8])
    fig.update_yaxes(title_text="<b>RPM</b>", row=5, col=1)
    fig.update_yaxes(title_text="<b>Long. G</b>", row=6, col=1, range=[-6, 3])
    fig.update_xaxes(title_text="<b>Track Distance (m)</b>", row=6, col=1)

    st.plotly_chart(fig, use_container_width=True)

    # ── 7. LAP HISTORY & SECTOR TIMES (LIVE TIMING ENGINE) ──
    st.divider()
    section_header("LAP HISTORY", f"{eng_driver} Session Log")
    
    with st.spinner("Processing live-timing cumulative sector data..."):
        _render_lap_history(session, laps, eng_driver, selected_lap_num)

def _render_lap_history(session, all_laps, eng_driver, selected_lap_num):
    all_laps = all_laps.copy()
    
    for col in ['LapTime', 'Sector1Time', 'Sector2Time', 'Sector3Time']:
        if col in all_laps.columns:
            all_laps[f'{col}_s'] = all_laps[col].dt.total_seconds()
        else:
            all_laps[f'{col}_s'] = np.nan

    all_laps_sorted = all_laps.dropna(subset=['Time']).sort_values('Time')
    all_laps_sorted['session_best_s1'] = all_laps_sorted['Sector1Time_s'].cummin()
    all_laps_sorted['session_best_s2'] = all_laps_sorted['Sector2Time_s'].cummin()
    all_laps_sorted['session_best_s3'] = all_laps_sorted['Sector3Time_s'].cummin()

    drv_laps = all_laps_sorted[all_laps_sorted['Driver'] == eng_driver].copy()
    if drv_laps.empty: return
    
    drv_laps = drv_laps.sort_values('LapNumber')
    drv_laps['pb_s1'] = drv_laps['Sector1Time_s'].cummin()
    drv_laps['pb_s2'] = drv_laps['Sector2Time_s'].cummin()
    drv_laps['pb_s3'] = drv_laps['Sector3Time_s'].cummin()
    
    overall_session_best_lap = all_laps['LapTime_s'].min()
    overall_personal_best_lap = drv_laps['LapTime_s'].min()

    display_data = []
    css_data = []

    def get_color(val, session_best, personal_best):
        if pd.isna(val) or val <= 0: return ""
        if abs(val - session_best) < 0.001:
            return "color: #df4bff; font-weight: 900;" 
        elif abs(val - personal_best) < 0.001:
            return "color: #00d47e; font-weight: 700;" 
        else:
            return "color: #ffd700;" 

    # ── AUTO-CALCULATE AND APPEND THEORETICAL IDEAL LAP FIRST ──
    overall_min_s1 = all_laps['Sector1Time_s'].min()
    overall_min_s2 = all_laps['Sector2Time_s'].min()
    overall_min_s3 = all_laps['Sector3Time_s'].min()
    
    pb_s1_ideal = drv_laps['Sector1Time_s'].min()
    pb_s2_ideal = drv_laps['Sector2Time_s'].min()
    pb_s3_ideal = drv_laps['Sector3Time_s'].min()
    theo_lap = pb_s1_ideal + pb_s2_ideal + pb_s3_ideal
    
    c_lt_ideal = get_color(theo_lap, overall_session_best_lap, theo_lap)
    c_s1_ideal = get_color(pb_s1_ideal, overall_min_s1, pb_s1_ideal)
    c_s2_ideal = get_color(pb_s2_ideal, overall_min_s2, pb_s2_ideal)
    c_s3_ideal = get_color(pb_s3_ideal, overall_min_s3, pb_s3_ideal)
    
    display_data.append({
        'Lap': "IDEAL",
        'Tyre': "—",
        'Lap Time': format_time(theo_lap) if pd.notna(theo_lap) else "N/A",
        'Sector 1': f"{pb_s1_ideal:.3f}" if pd.notna(pb_s1_ideal) else "N/A",
        'Sector 2': f"{pb_s2_ideal:.3f}" if pd.notna(pb_s2_ideal) else "N/A",
        'Sector 3': f"{pb_s3_ideal:.3f}" if pd.notna(pb_s3_ideal) else "N/A",
    })
    css_data.append({
        'Lap': "color: #df4bff; font-weight: bold; background-color: rgba(223, 75, 255, 0.1);", 
        'Tyre': "background-color: rgba(223, 75, 255, 0.1);",
        'Lap Time': f"background-color: rgba(223, 75, 255, 0.1); {c_lt_ideal}", 
        'Sector 1': f"background-color: rgba(223, 75, 255, 0.1); {c_s1_ideal}", 
        'Sector 2': f"background-color: rgba(223, 75, 255, 0.1); {c_s2_ideal}", 
        'Sector 3': f"background-color: rgba(223, 75, 255, 0.1); {c_s3_ideal}"
    })

    # ── APPEND ALL ACTUAL DRIVER LAPS ──
    for _, row in drv_laps.iterrows():
        lap_num = int(row['LapNumber'])
        comp = row.get('Compound', 'UNKNOWN')
        if pd.isna(comp): comp = 'UNKNOWN'
        
        lt = row['LapTime_s']
        s1 = row['Sector1Time_s']
        s2 = row['Sector2Time_s']
        s3 = row['Sector3Time_s']
        
        c_lt = get_color(lt, overall_session_best_lap, overall_personal_best_lap)
        c_s1 = get_color(s1, row['session_best_s1'], row['pb_s1'])
        c_s2 = get_color(s2, row['session_best_s2'], row['pb_s2'])
        c_s3 = get_color(s3, row['session_best_s3'], row['pb_s3'])
        
        is_pit = pd.notna(row.get('PitInTime')) or pd.notna(row.get('PitOutTime'))
        lap_str = str(lap_num) + (" (PIT)" if is_pit else "")
        
        is_selected = (lap_num == selected_lap_num)
        base_css = "background-color: rgba(255, 255, 255, 0.08); border-left: 3px solid #ff6b35;" if is_selected else ""
        
        display_data.append({
            'Lap': lap_str,
            'Tyre': TYRE_LABELS.get(comp, comp),
            'Lap Time': format_time(lt),
            'Sector 1': f"{s1:.3f}" if pd.notna(s1) else "N/A",
            'Sector 2': f"{s2:.3f}" if pd.notna(s2) else "N/A",
            'Sector 3': f"{s3:.3f}" if pd.notna(s3) else "N/A",
        })
        css_data.append({
            'Lap': base_css + ("color: #888;" if is_pit else "font-weight: bold;"), 
            'Tyre': base_css,
            'Lap Time': f"{base_css} {c_lt}", 
            'Sector 1': f"{base_css} {c_s1}", 
            'Sector 2': f"{base_css} {c_s2}", 
            'Sector 3': f"{base_css} {c_s3}"
        })

    if display_data:
        df_display = pd.DataFrame(display_data)
        df_css = pd.DataFrame(css_data)
        styled_table = df_display.style.apply(lambda _: df_css, axis=None)
        st.dataframe(styled_table, use_container_width=True, hide_index=True)
    else:
        st.info("No valid lap data available to build history table.")