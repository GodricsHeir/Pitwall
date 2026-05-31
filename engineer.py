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
    section_header, no_data_error, PLOTLY_THEME, format_time, TYRE_LABELS
)

# ─────────────────────────────────────────────────────────────
#  ROBUST DRIVER COLOR ENGINE
# ─────────────────────────────────────────────────────────────
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

def _to_rgba(hex_color, alpha=0.15):
    """Converts a hex color string to an rgba string for Plotly fills."""
    try:
        c = str(hex_color).strip().lower()
        if c.startswith('#'):
            c = c.lstrip('#')
            if len(c) == 6:
                r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
                return f"rgba({r}, {g}, {b}, {alpha})"
    except Exception:
        pass
    return f"rgba(255, 255, 255, {alpha})"

def enrich_telemetry(telemetry_df):
    """Adds RPM handling and calculates Longitudinal & Lateral G-Force safely."""
    if telemetry_df is None or telemetry_df.empty:
        return telemetry_df
        
    try:
        telemetry_df['RPM'] = pd.to_numeric(telemetry_df.get('RPM', 0), errors='coerce').fillna(0)
        speed = pd.to_numeric(telemetry_df.get('Speed', 0), errors='coerce').fillna(0)
        telemetry_df['Speed_ms'] = speed / 3.6
        
        if 'Time' in telemetry_df.columns:
            telemetry_df['Time_s'] = telemetry_df['Time'].dt.total_seconds()
            telemetry_df = telemetry_df.drop_duplicates(subset=['Time_s']).copy()
            
            if len(telemetry_df) > 2:
                # Longitudinal G-Force
                accel = np.gradient(telemetry_df['Speed_ms'], telemetry_df['Time_s'])
                telemetry_df['Long_G'] = (accel / 9.81)
                telemetry_df['Long_G'] = telemetry_df['Long_G'].rolling(window=3, min_periods=1).mean()
                
                # Lateral G-Force
                if 'X' in telemetry_df.columns and 'Y' in telemetry_df.columns:
                    dx_s = telemetry_df['X'].rolling(5, center=True).mean().diff()
                    dy_s = telemetry_df['Y'].rolling(5, center=True).mean().diff()
                    ddx = dx_s.diff()
                    ddy = dy_s.diff()
                    curvature = (dx_s * ddy - dy_s * ddx) / ((dx_s**2 + dy_s**2)**1.5 + 1e-6)
                    lat_g = ((telemetry_df['Speed_ms']**2) * curvature) / 9.81
                    telemetry_df['Lat_G'] = lat_g.clip(-5.5, 5.5).rolling(5, center=True).mean().fillna(0)
                else:
                    telemetry_df['Lat_G'] = 0
            else:
                telemetry_df['Long_G'] = 0
                telemetry_df['Lat_G'] = 0
        else:
            telemetry_df['Long_G'] = 0
            telemetry_df['Lat_G'] = 0
            
    except Exception:
        telemetry_df['Long_G'] = 0
        telemetry_df['Lat_G'] = 0
        
    return telemetry_df

def _render_status_bubble(lap_data, weather_data=None):
    """Generates a bold, high-contrast status bar for a specific lap."""
    track_status = str(lap_data.get('TrackStatus', '1'))
    is_sc = '4' in track_status or '6' in track_status or '7' in track_status
    is_yellow = '2' in track_status
    is_dirty = lap_data.get('Is_Dirty_Air', False)
    
    if is_sc: status_text, status_color = "SC/VSC ACTIVE", "#ffd700"
    elif is_yellow: status_text, status_color = "YELLOW SECTOR", "#ffeb3b"
    else: status_text, status_color = ("DIRTY AIR", "#e8002d") if is_dirty else ("CLEAN AIR", "#00d47e")
    
    comp = str(lap_data.get('Compound', 'UNKNOWN')).upper()
    age = int(lap_data.get('TyreLife')) if pd.notna(lap_data.get('TyreLife')) else 0
    
    if 'SOFT' in comp: t_color = '#e8002d'       
    elif 'MEDIUM' in comp: t_color = '#ffd700'   
    elif 'HARD' in comp: t_color = '#e8e8f0'     
    elif 'INTER' in comp: t_color = '#00d47e'    
    elif 'WET' in comp: t_color = '#4db8ff'      
    else: t_color = '#ffffff'                    
    
    is_wet = False
    track_temp = None
    if weather_data is not None and not weather_data.empty:
        lap_time = lap_data.get('Time')
        if pd.notna(lap_time):
            try:
                idx = (weather_data['Time'] - lap_time).abs().idxmin()
                closest_weather = weather_data.loc[idx]
                is_wet = closest_weather.get('Rainfall', False)
                track_temp = closest_weather.get('TrackTemp')
            except Exception: pass

    weather = "🌧️ WET" if is_wet else "☀️ DRY"
    temp_html = f'<span style="color:#ffffff; font-size:0.95rem; align-self:center; font-weight:800; margin-left:8px;">TRACK: {track_temp:.1f}°C</span>' if pd.notna(track_temp) else ""
    
    return f"""
    <div style="display:flex; flex-wrap:wrap; gap:12px; margin-bottom:15px; font-family:'JetBrains Mono',monospace;">
        <span style="color:{status_color}; border:2px solid {status_color}; padding:6px 14px; border-radius:6px; font-size:0.9rem; font-weight:800; background:{status_color}25;">{status_text}</span>
        <span style="color:#4db8ff; border:2px solid #4db8ff; padding:6px 14px; border-radius:6px; font-size:0.9rem; font-weight:800; background:rgba(77,184,255,0.15);">{weather}</span>
        <span style="color:{t_color}; border:2px solid {t_color}; padding:6px 14px; border-radius:6px; font-size:0.9rem; font-weight:800; background:{t_color}25;">{comp} (L{age})</span>
        {temp_html}
    </div>
    """

def _apply_strong_axes(fig):
    """Utility to make chart gridlines highly visible."""
    fig.update_xaxes(showgrid=True, gridcolor="rgba(255,255,255,0.08)", zerolinecolor="rgba(255,255,255,0.2)", zerolinewidth=1.5)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.08)", zerolinecolor="rgba(255,255,255,0.2)", zerolinewidth=1.5)
    return fig

def _plot_single_telemetry(tel_fast, tel_target, fastest_lap, target_lap, selected_lap_num, eng_driver, session, d_color):
    """Generates the single-driver 7-panel telemetry chart with neon multi-colored traces."""
    fig = make_subplots(
        rows=7, cols=1, shared_xaxes=True, vertical_spacing=0.025,
        row_heights=[0.18, 0.12, 0.12, 0.12, 0.12, 0.17, 0.17]
    )
    
    fastest_lap_num = int(fastest_lap['LapNumber'])

    def add_tel_traces(row_num, col_name, is_fastest=False, is_step=False):
        if is_fastest:
            color, width, dash = 'rgba(255, 255, 255, 0.65)', 2.5, 'dash'
            trace_name, tel_data = f"<b>Best</b> (Lap {fastest_lap_num})", tel_fast
            fill_mode = None
        else:
            if col_name == 'Speed': color = '#00e5ff'      
            elif col_name == 'Throttle': color = '#00d47e' 
            elif col_name == 'Brake': color = '#e8002d'    
            elif col_name == 'nGear': color = '#ffd700'    
            elif col_name == 'RPM': color = '#df4bff'      
            elif col_name == 'Long_G': color = '#ff6b35'   
            elif col_name == 'Lat_G': color = '#4db8ff'    
            else: color = '#ffffff'
            
            width, dash = 3.0, 'solid'
            trace_name, tel_data = f"<b>Target</b> (Lap {selected_lap_num})", tel_target
            fill_mode = 'tozeroy'

        line_opts = dict(color=color, width=width, dash=dash)
        if is_step: line_opts['shape'] = 'hv'

        y_data = tel_data.get(col_name, pd.Series(np.nan, index=tel_data.index))
        x_data = tel_data.get('Distance', tel_data.index)

        kwargs = dict(x=x_data, y=y_data, name=trace_name, line=line_opts, legendgroup=trace_name, showlegend=(row_num == 1))
        
        if fill_mode:
            kwargs['fill'] = fill_mode
            kwargs['fillcolor'] = _to_rgba(color, 0.2)

        fig.add_trace(go.Scatter(**kwargs), row=row_num, col=1)

        if col_name == 'Speed' and 'DRS' in tel_data.columns:
            drs_active = tel_data.get('DRS', 0) >= 10
            if drs_active.any():
                drs_speed = tel_data['Speed'].copy()
                drs_speed.loc[~drs_active] = np.nan
                fig.add_trace(go.Scatter(
                    x=x_data, y=drs_speed, mode='lines',
                    line=dict(color='#00d47e', width=width + 2, dash=dash),
                    name=f"{trace_name} (DRS Open)", legendgroup=trace_name,
                    showlegend=False, hoverinfo='skip'
                ), row=row_num, col=1)

    add_tel_traces(1, 'Speed', is_fastest=True)
    add_tel_traces(1, 'Speed')
    add_tel_traces(2, 'Throttle', is_fastest=True)
    add_tel_traces(2, 'Throttle')
    add_tel_traces(3, 'Brake', is_fastest=True)
    add_tel_traces(3, 'Brake')
    add_tel_traces(4, 'nGear', is_fastest=True, is_step=True)
    add_tel_traces(4, 'nGear', is_step=True)
    add_tel_traces(5, 'RPM', is_fastest=True)
    add_tel_traces(5, 'RPM')
    add_tel_traces(6, 'Long_G', is_fastest=True)
    add_tel_traces(6, 'Long_G')
    add_tel_traces(7, 'Lat_G', is_fastest=True)
    add_tel_traces(7, 'Lat_G')

    fig.add_hline(y=0, line_dash="solid", line_color="rgba(255, 255, 255, 0.4)", line_width=2, row=6, col=1)
    fig.add_hline(y=0, line_dash="solid", line_color="rgba(255, 255, 255, 0.4)", line_width=2, row=7, col=1)

    # ── SECTOR SHADING & CORNER ANNOTATIONS ──
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
            
            fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(232, 0, 45, 0.5)", size=12, symbol="square"), name="Sector 1", showlegend=True), row=1, col=1)
            fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(63, 182, 220, 0.5)", size=12, symbol="square"), name="Sector 2", showlegend=True), row=1, col=1)
            fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(255, 215, 0, 0.5)", size=12, symbol="square"), name="Sector 3", showlegend=True), row=1, col=1)
    except Exception: pass

    try:
        circuit_info = session.get_circuit_info()
        if circuit_info is not None and not circuit_info.corners.empty:
            for _, corner in circuit_info.corners.iterrows():
                dist = corner['Distance']
                num = str(corner['Number'])
                fig.add_vline(x=dist, line_width=2, line_dash="dot", line_color="rgba(255, 255, 255, 0.45)")
                fig.add_annotation(
                    x=dist, y=1.0, yref="paper", text=f"<b>{num}</b>",
                    showarrow=False, xanchor="left", yanchor="bottom",
                    font=dict(size=14, color="rgba(255,255,255,1)")
                )
    except Exception: pass

    fig.update_layout(
        **PLOTLY_THEME, height=1300, title=f"<b>Telemetry Comparison: Lap {selected_lap_num} vs Fastest Lap ({fastest_lap_num})</b>",
        hovermode="x unified", margin=dict(t=110),
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="right", x=1, bgcolor="rgba(19, 19, 26, 0.95)", bordercolor="rgba(255,255,255,0.4)", borderwidth=1, font=dict(size=14, color="white"))
    )
    
    fig = _apply_strong_axes(fig)
    fig.update_yaxes(title_text="<b>Speed (km/h)</b>", row=1, col=1)
    fig.update_yaxes(title_text="<b>Throttle %</b>", row=2, col=1, range=[-5, 105])
    fig.update_yaxes(title_text="<b>Brake</b>", row=3, col=1, range=[-0.1, 1.2], tickvals=[0, 1])
    fig.update_yaxes(title_text="<b>Gear</b>", row=4, col=1, range=[0, 9], tickvals=[1,2,3,4,5,6,7,8])
    fig.update_yaxes(title_text="<b>RPM</b>", row=5, col=1)
    fig.update_yaxes(title_text="<b>Long. G</b>", row=6, col=1, range=[-6, 3])
    fig.update_yaxes(title_text="<b>Lat. G</b>", row=7, col=1, range=[-5.5, 5.5])
    fig.update_xaxes(title_text="<b>Track Distance (m)</b>", row=7, col=1)

    return fig

def _plot_multi_telemetry(session, target_laps_dict, results_df, ref_lap, ref_tel):
    """Generates the multi-driver overlaid 7-panel telemetry chart."""
    fig = make_subplots(
        rows=7, cols=1, shared_xaxes=True, vertical_spacing=0.025,
        row_heights=[0.18, 0.12, 0.12, 0.12, 0.12, 0.17, 0.17]
    )
    
    for drv, lap_obj in target_laps_dict.items():
        try:
            tel = lap_obj.get_telemetry()
            tel = enrich_telemetry(tel)
            color = get_accurate_driver_color(drv, results_df)
            lap_num = int(lap_obj['LapNumber'])
            trace_name = f"<b>{drv}</b> (L{lap_num})"
            
            x_data = tel.get('Distance', tel.index)
            
            def add_multi_trace(row_num, col_name, is_step=False):
                y_data = tel.get(col_name, pd.Series(np.nan, index=tel.index))
                line_opts = dict(color=color, width=2.5, dash='solid')
                if is_step: line_opts['shape'] = 'hv'
                
                fig.add_trace(go.Scatter(
                    x=x_data, y=y_data, name=trace_name, line=line_opts, 
                    legendgroup=drv, showlegend=(row_num == 1),
                    fill='tozeroy', fillcolor=_to_rgba(color, 0.1)
                ), row=row_num, col=1)
                
                if col_name == 'Speed' and 'DRS' in tel.columns:
                    drs_active = tel.get('DRS', 0) >= 10
                    if drs_active.any():
                        drs_speed = tel['Speed'].copy()
                        drs_speed.loc[~drs_active] = np.nan
                        fig.add_trace(go.Scatter(
                            x=x_data, y=drs_speed, mode='lines',
                            line=dict(color='#00d47e', width=4, dash='solid'),
                            name=f"{trace_name} (DRS)", legendgroup=drv,
                            showlegend=False, hoverinfo='skip'
                        ), row=row_num, col=1)
            
            add_multi_trace(1, 'Speed')
            add_multi_trace(2, 'Throttle')
            add_multi_trace(3, 'Brake')
            add_multi_trace(4, 'nGear', is_step=True)
            add_multi_trace(5, 'RPM')
            add_multi_trace(6, 'Long_G')
            add_multi_trace(7, 'Lat_G')
            
        except Exception:
            continue

    fig.add_hline(y=0, line_dash="solid", line_color="rgba(255, 255, 255, 0.4)", line_width=2, row=6, col=1)
    fig.add_hline(y=0, line_dash="solid", line_color="rgba(255, 255, 255, 0.4)", line_width=2, row=7, col=1)

    # ── SECTOR SHADING & CORNER ANNOTATIONS ──
    try:
        if not ref_tel.empty:
            time_col = 'SessionTime' if 'SessionTime' in ref_tel.columns else 'Time'
            s1_time = ref_lap.get('Sector1SessionTime')
            s2_time = ref_lap.get('Sector2SessionTime')
            ref_s1 = ref_tel.loc[ref_tel[time_col] <= s1_time, 'Distance'].max() if pd.notna(s1_time) else None
            ref_s2 = ref_tel.loc[ref_tel[time_col] <= s2_time, 'Distance'].max() if pd.notna(s2_time) else None
            max_dist = ref_tel['Distance'].max()
            
            if ref_s1 and ref_s2 and max_dist:
                fig.add_vrect(x0=0, x1=ref_s1, fillcolor="rgba(232, 0, 45, 0.08)", layer="below", line_width=0)
                fig.add_vrect(x0=ref_s1, x1=ref_s2, fillcolor="rgba(63, 182, 220, 0.08)", layer="below", line_width=0)
                fig.add_vrect(x0=ref_s2, x1=max_dist, fillcolor="rgba(255, 215, 0, 0.06)", layer="below", line_width=0)
                
                fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(232, 0, 45, 0.5)", size=12, symbol="square"), name="Sector 1", showlegend=True), row=1, col=1)
                fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(63, 182, 220, 0.5)", size=12, symbol="square"), name="Sector 2", showlegend=True), row=1, col=1)
                fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(color="rgba(255, 215, 0, 0.5)", size=12, symbol="square"), name="Sector 3", showlegend=True), row=1, col=1)
    except Exception: pass

    try:
        circuit_info = session.get_circuit_info()
        if circuit_info is not None and not circuit_info.corners.empty:
            for _, corner in circuit_info.corners.iterrows():
                dist = corner['Distance']
                num = str(corner['Number'])
                fig.add_vline(x=dist, line_width=2, line_dash="dot", line_color="rgba(255, 255, 255, 0.45)")
                fig.add_annotation(
                    x=dist, y=1.0, yref="paper", text=f"<b>{num}</b>",
                    showarrow=False, xanchor="left", yanchor="bottom",
                    font=dict(size=14, color="rgba(255,255,255,1)")
                )
    except Exception: pass

    fig.update_layout(
        **PLOTLY_THEME, height=1300, title=f"<b>Multi-Driver Telemetry Overlay</b>",
        hovermode="x unified", margin=dict(t=110),
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="right", x=1, bgcolor="rgba(19, 19, 26, 0.95)", bordercolor="rgba(255,255,255,0.4)", borderwidth=1, font=dict(size=14, color="white"))
    )
    
    fig = _apply_strong_axes(fig)
    fig.update_yaxes(title_text="<b>Speed (km/h)</b>", row=1, col=1)
    fig.update_yaxes(title_text="<b>Throttle %</b>", row=2, col=1, range=[-5, 105])
    fig.update_yaxes(title_text="<b>Brake</b>", row=3, col=1, range=[-0.1, 1.2], tickvals=[0, 1])
    fig.update_yaxes(title_text="<b>Gear</b>", row=4, col=1, range=[0, 9], tickvals=[1,2,3,4,5,6,7,8])
    fig.update_yaxes(title_text="<b>RPM</b>", row=5, col=1)
    fig.update_yaxes(title_text="<b>Long. G</b>", row=6, col=1, range=[-6, 3])
    fig.update_yaxes(title_text="<b>Lat. G</b>", row=7, col=1, range=[-5.5, 5.5])
    fig.update_xaxes(title_text="<b>Track Distance (m)</b>", row=7, col=1)

    return fig

def render_engineer(year, race, session_id, session_name, available_drivers):
    section_header("DRIVER TELEMETRY", f"{year} {race}  ·  {session_name}")

    try:
        session = fastf1.get_session(year, race, session_id)
        session.load(telemetry=True, weather=True, messages=False)
        laps = session.laps
        weather_data = session.weather_data
    except Exception as e:
        no_data_error(f"Failed to load telemetry: {e}")
        return

    if laps.empty:
        no_data_error("No lap data found in this session.")
        return

    available_drivers = sorted(session.results['Abbreviation'].dropna().tolist())
    if not available_drivers:
        no_data_error("No valid drivers found.")
        return

    st.markdown('<div class="pw-section-label">Analysis Mode</div>', unsafe_allow_html=True)
    mode = st.selectbox("Telemetry Mode", ["Single Driver Deep Dive", "Multi-Driver Comparison (Up to 4)"], label_visibility="collapsed")
    st.markdown("<br>", unsafe_allow_html=True)

    # ═════════════════════════════════════════════════════
    #  SINGLE DRIVER MODE
    # ═════════════════════════════════════════════════════
    if mode == "Single Driver Deep Dive":
        
        col1, _ = st.columns([2, 2])
        with col1:
            eng_driver = st.selectbox("Select Driver", available_drivers, key="single_drv_sel")
            
        st.divider()
        d_color = get_accurate_driver_color(eng_driver, session.results)
        st.markdown(f"#### Telemetry Deep Dive: <span style='color:{d_color}'>{eng_driver}</span>", unsafe_allow_html=True)
        
        driver_laps = laps[laps['Driver'] == eng_driver].copy()
        if driver_laps.empty:
            no_data_error(f"No lap data found for {eng_driver}.")
            return

        fastest_lap = driver_laps.loc[driver_laps['LapTime'].idxmin()]
        fastest_lap_num = int(fastest_lap['LapNumber'])

        st.markdown("<h5 style='color: #ffffff; font-weight: 800;'>Lap Selection</h5>", unsafe_allow_html=True)
        col1, col2 = st.columns([1, 3])
        with col1:
            lap_options = driver_laps['LapNumber'].dropna().astype(int).tolist()
            selected_lap_num = st.selectbox(
                "Select Target Lap", 
                lap_options, 
                index=lap_options.index(fastest_lap_num) if fastest_lap_num in lap_options else 0
            )

        target_lap = driver_laps[driver_laps['LapNumber'] == selected_lap_num].iloc[0]

        st.markdown(_render_status_bubble(target_lap, weather_data), unsafe_allow_html=True)

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

        with st.spinner("Extracting 20Hz Telemetry..."):
            try:
                tel_fast = fastest_lap.get_telemetry()
                tel_target = target_lap.get_telemetry()
                tel_fast = enrich_telemetry(tel_fast)
                tel_target = enrich_telemetry(tel_target)
            except Exception as e:
                no_data_error(f"Raw telemetry data is corrupted for the selected laps. Debug info: {e}")
                return

        fig = _plot_single_telemetry(tel_fast, tel_target, fastest_lap, target_lap, selected_lap_num, eng_driver, session, d_color)
        st.plotly_chart(fig, use_container_width=True)

        st.divider()
        section_header("LAP HISTORY", f"{eng_driver} Session Log")
        with st.spinner("Processing live-timing cumulative sector data..."):
            _render_lap_history(session, laps, eng_driver, selected_lap_num)

    # ═════════════════════════════════════════════════════
    #  MULTI-DRIVER MODE
    # ═════════════════════════════════════════════════════
    else:
        st.markdown(f"#### Multi-Driver Telemetry Overlay")
        
        with st.form("multi_driver_form"):
            st.markdown('<div style="font-size: 1.0rem; color: #ffffff; font-weight: 700; margin-bottom: 12px;">Select Drivers to Compare (Max 4)</div>', unsafe_allow_html=True)
            
            selected_drivers = []
            cols = st.columns(6)
            for i, drv in enumerate(available_drivers):
                with cols[i % 6]:
                    if st.checkbox(drv, value=(i == 0), key=f"eng_chk_{drv}"):
                        selected_drivers.append(drv)
            
            st.divider()
            submitted = st.form_submit_button("▶  UPDATE DRIVERS", type="primary", use_container_width=True)

        if not selected_drivers:
            st.info("Please select at least one driver to begin the comparison.")
            return
            
        if len(selected_drivers) > 4:
            st.warning("Maximum of 4 drivers can be compared at once. Displaying the first 4 selections.")
            selected_drivers = selected_drivers[:4]
            
        sync_mode = st.checkbox("⚡ Sync Laps (Apply same lap number to all drivers)", value=False)
        st.markdown("<br>", unsafe_allow_html=True)
        
        cols = st.columns(len(selected_drivers))
        target_laps = {}
        overall_best_s = laps['LapTime'].dt.total_seconds().min()
        
        sync_lap_num = None
        if sync_mode:
            ref_drv = selected_drivers[0]
            ref_laps = laps[laps['Driver'] == ref_drv]['LapNumber'].dropna().astype(int).tolist()
            if ref_laps:
                sync_lap_num = st.selectbox("Select Synchronized Lap", ref_laps)
            else:
                st.error("No valid laps found for synchronization.")
                return
        
        for i, drv in enumerate(selected_drivers):
            with cols[i]:
                drv_laps = laps[laps['Driver'] == drv].copy()
                st.markdown(f"##### <span style='color:{get_accurate_driver_color(drv, session.results)}; font-weight:900;'>{drv}</span>", unsafe_allow_html=True)
                
                if drv_laps.empty:
                    st.error("No data")
                    continue
                    
                drv_opts = drv_laps['LapNumber'].dropna().astype(int).tolist()
                
                if sync_mode:
                    if sync_lap_num in drv_opts:
                        sel_lap = sync_lap_num
                    else:
                        st.error(f"Lap {sync_lap_num} unavailable")
                        continue
                else:
                    drv_fastest = int(drv_laps.loc[drv_laps['LapTime'].idxmin()]['LapNumber']) if not drv_laps.empty else 1
                    sel_lap = st.selectbox("Select Lap", drv_opts, index=drv_opts.index(drv_fastest) if drv_fastest in drv_opts else 0, key=f"lap_{drv}")
                    
                lap_obj = drv_laps[drv_laps['LapNumber'] == sel_lap].iloc[0]
                target_laps[drv] = lap_obj
                
                st.markdown(_render_status_bubble(lap_obj, weather_data), unsafe_allow_html=True)
                
                lt_s = lap_obj['LapTime'].total_seconds() if pd.notna(lap_obj['LapTime']) else None
                lt_str = format_time(lt_s) if lt_s else "NO TIME"
                delta_s = (lt_s - overall_best_s) if lt_s and pd.notna(overall_best_s) else None
                delta_str = f"+{delta_s:.3f}s" if delta_s and delta_s > 0 else "Session Best" if delta_s is not None else ""
                
                st.metric(f"Lap {sel_lap} Time", lt_str, delta_str, delta_color="inverse" if delta_s and delta_s > 0 else "normal")

        if target_laps:
            with st.spinner("Extracting Multi-Driver Telemetry Overlay..."):
                ref_lap_obj = target_laps[selected_drivers[0]]
                try:
                    ref_tel = ref_lap_obj.get_telemetry()
                except Exception:
                    ref_tel = pd.DataFrame()
                
                fig = _plot_multi_telemetry(session, target_laps, session.results, ref_lap_obj, ref_tel)
                st.plotly_chart(fig, use_container_width=True)
                
        st.divider()
        section_header("LAP HISTORY", "Session Logs")
        history_tabs = st.tabs([f"{d} Session Log" for d in selected_drivers])
        
        for d, tab in zip(selected_drivers, history_tabs):
            with tab:
                if d in target_laps:
                    _render_lap_history(session, laps, d, int(target_laps[d]['LapNumber']))
                else:
                    st.info(f"No lap selected for {d}.")


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
        if pd.isna(val) or val <= 0: return "color: #ffffff;"
        if abs(val - session_best) < 0.001:
            return "color: #df4bff; font-weight: 900;" 
        elif abs(val - personal_best) < 0.001:
            return "color: #00d47e; font-weight: 800;" 
        else:
            return "color: #ffd700; font-weight: 600;" 

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
        base_css = "background-color: rgba(255, 255, 255, 0.1); border-left: 4px solid #ff6b35;" if is_selected else ""
        
        display_data.append({
            'Lap': lap_str,
            'Tyre': TYRE_LABELS.get(comp, comp),
            'Lap Time': format_time(lt),
            'Sector 1': f"{s1:.3f}" if pd.notna(s1) else "N/A",
            'Sector 2': f"{s2:.3f}" if pd.notna(s2) else "N/A",
            'Sector 3': f"{s3:.3f}" if pd.notna(s3) else "N/A",
        })
        css_data.append({
            'Lap': base_css + ("color: #888;" if is_pit else "color: #ffffff; font-weight: 800;"), 
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