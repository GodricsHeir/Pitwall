"""
circuit.py — Unified Track Walk, Replay, and Analytics Dashboard
"""
import json
import math
import streamlit as st
import fastf1
import fastf1.plotting
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit.components.v1 as components

from utils import (
    safe_load_session, section_header, no_data_error, 
    PLOTLY_THEME, driver_color
)

# ─────────────────────────────────────────────────────────────
#  COLLOQUIAL CORNER DICTIONARY
# ─────────────────────────────────────────────────────────────
FAMOUS_CORNERS = {
    "Silverstone": {9: "Copse", 10: "Maggotts", 11: "Becketts", 12: "Chapel", 15: "Stowe", 16: "Vale", 18: "Club"},
    "Spa-Francorchamps": {1: "La Source", 3: "Eau Rouge", 4: "Raidillon", 7: "Les Combes", 10: "Pouhon", 18: "Blanchimont", 19: "Bus Stop"},
    "Monza": {1: "Rettifilo", 4: "Della Roggia", 6: "Lesmo 1", 7: "Lesmo 2", 8: "Ascari", 11: "Parabolica"},
    "Suzuka": {1: "First Curve", 3: "S Curves", 8: "Degner 1", 9: "Degner 2", 11: "Hairpin", 13: "Spoon", 15: "130R", 16: "Casio Triangle"},
    "Interlagos": {1: "Senna S", 4: "Descida do Lago", 8: "Macunaima", 10: "Bico de Pato", 12: "Junção"},
    "Albert Park": {1: "Brabham", 2: "Jones", 3: "Sports Centre", 14: "Ascari"},
    "Monaco": {1: "Sainte Devote", 3: "Massenet", 4: "Casino", 5: "Mirabeau", 6: "Hairpin", 8: "Portier", 9: "Tunnel", 10: "Nouvelle Chicane", 12: "Tabac", 15: "Swimming Pool", 17: "La Rascasse"},
    "Baku": {8: "The Castle", 15: "Downhill Fast", 16: "Blind Turn"},
    "Gilles-Villeneuve": {1: "Senna 'S'", 10: "L'Epingle", 13: "Wall of Champions"}
}

# ─────────────────────────────────────────────────────────────
#  UTILITIES & COLOR LOGIC
# ─────────────────────────────────────────────────────────────
def get_compass_arrow(wind_dir_deg):
    if pd.isna(wind_dir_deg): return ""
    blow_to = (wind_dir_deg + 180) % 360
    arrows = ['↓', '↙', '←', '↖', '↑', '↗', '→', '↘', '↓']
    idx = int(round(blow_to / 45.0))
    return arrows[idx]

def determine_wind_impact(car_heading, wind_dir):
    if pd.isna(car_heading) or pd.isna(wind_dir): return "Unknown"
    diff = abs((car_heading - wind_dir + 180) % 360 - 180)
    if diff < 45: return "Headwind"
    elif diff > 135: return "Tailwind"
    else: return "Crosswind"

def get_accurate_driver_color(drv, results_df=None):
    try:
        if results_df is not None and not results_df.empty:
            c = results_df.loc[results_df['Abbreviation'] == drv, 'TeamColor'].values[0]
            if pd.notna(c) and str(c).strip() != "": return f"#{c}"
    except: pass
    try:
        c = fastf1.plotting.driver_color(drv)
        return f"#{c}" if not c.startswith('#') else c
    except: return "#ffffff"

def get_gradient_color(val, vmin, vmax):
    if pd.isna(val) or val == 0 or vmax == vmin: return "transparent"
    pct = (val - vmin) / (vmax - vmin)
    pct = max(0, min(1, pct))
    if pct < 0.5:
        p = pct * 2
        r = int(68 + (33 - 68) * p)
        g = int(1 + (145 - 1) * p)
        b = int(84 + (140 - 84) * p)
    else:
        p = (pct - 0.5) * 2
        r = int(33 + (253 - 33) * p)
        g = int(145 + (231 - 145) * p)
        b = int(140 + (37 - 140) * p)
    return f"rgba({r}, {g}, {b}, 0.7)"

def parse_track_status(status_str):
    if pd.isna(status_str): return "Clear"
    s = str(status_str)
    if '5' in s: return "Red Flag"
    if '4' in s or '6' in s: return "SC/VSC"
    if '2' in s: return "Yellow"
    return "Clear"


# ─────────────────────────────────────────────────────────────
#  SPATIAL OVERTAKE ENGINE
# ─────────────────────────────────────────────────────────────
def get_spatial_overtakes(session, ref_tel, results_df):
    """Maps every overtake mathematically to the exact braking zone it occurred in."""
    braking = ref_tel[ref_tel['Long_G'] < -1.5].copy()
    if braking.empty: return pd.DataFrame(), {}
    
    braking['gap'] = braking['Distance'].diff() > 150
    braking['cluster'] = braking['gap'].cumsum()
    clusters = braking.groupby('cluster').agg({'X': 'mean', 'Y': 'mean', 'Distance': 'mean'}).reset_index()
    
    laps = session.laps.dropna(subset=['LapNumber', 'Position', 'Driver'])
    if laps.empty: return clusters, {}
    
    max_lap = int(laps['LapNumber'].max())
    ot_by_cluster = {int(c): [] for c in clusters['cluster']}
    
    for lap in range(2, max_lap + 1):
        prev = laps[laps['LapNumber'] == lap - 1][['Driver', 'Position']]
        curr = laps[laps['LapNumber'] == lap][['Driver', 'Position']]
        merged = prev.merge(curr, on='Driver', suffixes=('_prev', '_curr'))
        gained = merged[merged['Position_curr'] < merged['Position_prev']]
        
        for _, row in gained.iterrows():
            attacker = row['Driver']
            defender_rows = merged[merged['Position_prev'] == row['Position_curr']]
            if defender_rows.empty: continue
            
            try:
                att_lap = session.laps.pick_driver(attacker)
                att_lap = att_lap[att_lap['LapNumber'] == lap]
                if not att_lap.empty:
                    att_tel = att_lap.iloc[0].get_telemetry()
                    max_dist = att_tel.loc[att_tel['Speed'].idxmax(), 'Distance']
                else: max_dist = ref_tel.loc[ref_tel['Speed'].idxmax(), 'Distance']
            except:
                max_dist = ref_tel.loc[ref_tel['Speed'].idxmax(), 'Distance']
                
            dist_diff = clusters['Distance'] - max_dist
            valid_clusters = clusters[dist_diff > 0]
            c_id = int(clusters.iloc[0]['cluster']) if valid_clusters.empty else int(valid_clusters.iloc[0]['cluster'])
            
            att_color = get_accurate_driver_color(attacker, results_df)
            def_color = get_accurate_driver_color(defender_rows['Driver'].values[0], results_df)
            ot_by_cluster[c_id].append(f"L{lap}: <span style='color:{att_color}'><b>{attacker}</b></span> pass <span style='color:{def_color}'><b>{defender_rows['Driver'].values[0]}</b></span>")
            
    return clusters, ot_by_cluster


# ─────────────────────────────────────────────────────────────
#  CORE DATA PROCESSOR (RESOURCE CACHED)
# ─────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False, ttl=3600)
def process_circuit_data(year, race, session_id):
    """Uses st.cache_resource to prevent UnhashableParamErrors on FastF1 objects."""
    try:
        session = fastf1.get_session(year, race, session_id)
        session.load(telemetry=True, weather=True, messages=True)
        
        ref_lap = session.laps.pick_fastest()
        if pd.isna(ref_lap.get('LapTime')): return None, None, None, None, "No valid telemetry laps found."
            
        tel = ref_lap.get_telemetry()
        tel['Time_s'] = tel['Time'].dt.total_seconds()
        tel['Speed_ms'] = tel['Speed'] / 3.6
        tel = tel.drop_duplicates(subset=['Time_s']).copy()
        
        tel['dx'] = tel['X'].diff().fillna(0)
        tel['dy'] = tel['Y'].diff().fillna(0)
        tel['Car_Heading'] = np.degrees(np.arctan2(tel['dy'], tel['dx'])) % 360
        
        if len(tel) > 2:
            accel = np.gradient(tel['Speed_ms'], tel['Time_s'])
            tel['Long_G'] = (accel / 9.81)
            tel['Long_G'] = tel['Long_G'].rolling(window=3, min_periods=1).mean()
            
            dx_s = tel['X'].rolling(5, center=True).mean().diff()
            dy_s = tel['Y'].rolling(5, center=True).mean().diff()
            ddx = dx_s.diff()
            ddy = dy_s.diff()
            curvature = (dx_s * ddy - dy_s * ddx) / ((dx_s**2 + dy_s**2)**1.5 + 1e-6)
            tel['Lat_G'] = ((tel['Speed_ms']**2) * curvature) / 9.81
            tel['Lat_G'] = tel['Lat_G'].clip(-5, 5).rolling(5, center=True).mean().fillna(0)
        else:
            tel['Long_G'], tel['Lat_G'] = 0, 0

        wd = session.weather_data
        if not wd.empty:
            wind_dir = wd['WindDirection'].mean()
            wind_spd = wd['WindSpeed'].mean()
            tel['Wind_Type'] = tel['Car_Heading'].apply(lambda h: determine_wind_impact(h, wind_dir))
            tel['Wind_Arrow'] = get_compass_arrow(wind_dir)
            tel['Wind_Speed'] = wind_spd
        else:
            tel['Wind_Type'], tel['Wind_Arrow'], tel['Wind_Speed'] = "N/A", "", 0

        try: circuit_info = session.get_circuit_info()
        except: circuit_info = None
        
        return session, tel, ref_lap, circuit_info, None
    except Exception as e:
        return None, None, None, None, str(e)


# ─────────────────────────────────────────────────────────────
#  STATIC TRACK MAP (CLEAN LEGEND & PROPER DRS)
# ─────────────────────────────────────────────────────────────
def render_static_track_map(tel, ref_lap, circuit_info):
    fig = go.Figure()
    
    s1_t = ref_lap.get('Sector1SessionTime')
    s2_t = ref_lap.get('Sector2SessionTime')
    
    tel['Sector'] = 3
    if pd.notna(s1_t): tel.loc[tel['SessionTime'] <= s1_t, 'Sector'] = 1
    if pd.notna(s1_t) and pd.notna(s2_t): tel.loc[(tel['SessionTime'] > s1_t) & (tel['SessionTime'] <= s2_t), 'Sector'] = 2

    def make_hover(df):
        return [
            f"<b>Sector {sec}</b><br>Speed: {spd} km/h<br>Gear: {gr}<br>RPM: {rpm}<br>Throttle: {thr}%<br>Brake: {'ON' if brk else 'OFF'}<br>Wind: {wt} {wa} ({ws:.1f} m/s)<extra></extra>"
            for sec, spd, gr, rpm, thr, brk, wt, wa, ws in zip(df['Sector'], df['Speed'], df['nGear'], df['RPM'], df['Throttle'], df['Brake']>0, df['Wind_Type'], df['Wind_Arrow'], df['Wind_Speed'])
        ]

    s1 = tel[tel['Sector'] == 1]
    s2 = tel[tel['Sector'] == 2]
    s3 = tel[tel['Sector'] == 3]
    
    # ── EXPLICIT LEGEND DEFINITIONS ──
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='#e8002d', width=5), name='Sector 1'))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='#3fb6dc', width=5), name='Sector 2'))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='#ffd700', width=5), name='Sector 3'))
    
    # Render actual sector lines (hidden from legend)
    if not s1.empty: fig.add_trace(go.Scatter(x=s1['X'], y=s1['Y'], mode='lines', line=dict(color='#e8002d', width=5), hovertemplate="%{text}", text=make_hover(s1), showlegend=False))
    if not s2.empty: fig.add_trace(go.Scatter(x=s2['X'], y=s2['Y'], mode='lines', line=dict(color='#3fb6dc', width=5), hovertemplate="%{text}", text=make_hover(s2), showlegend=False))
    if not s3.empty: fig.add_trace(go.Scatter(x=s3['X'], y=s3['Y'], mode='lines', line=dict(color='#ffd700', width=5), hovertemplate="%{text}", text=make_hover(s3), showlegend=False))

    # ── DRS ZONES & DETECTION ──
    if 'DRS' in tel.columns:
        drs_active = tel[tel['DRS'] >= 8].copy()
        if not drs_active.empty:
            fig.add_trace(go.Scatter(x=[None], y=[None], mode='lines', line=dict(color='#00d47e', width=10), name='DRS Zone'))
            drs_active['gap'] = drs_active['Distance'].diff() > 100
            for _, seg in drs_active.groupby(drs_active['gap'].cumsum()):
                if len(seg) > 1:
                    fig.add_trace(go.Scatter(x=seg['X'], y=seg['Y'], mode='lines', line=dict(color='#00d47e', width=10), hovertemplate="<b>DRS ZONE</b><extra></extra>", showlegend=False))
        
        tel['DRS_shift'] = tel['DRS'].shift(1, fill_value=0)
        drs_det_points = tel[(tel['DRS'] >= 8) & (tel['DRS_shift'] < 8)]
        valid_det = []
        last_dist = -9999
        for _, row in drs_det_points.iterrows():
            if row['Distance'] - last_dist > 500:
                valid_det.append(row)
                last_dist = row['Distance']
        if valid_det:
            df_det = pd.DataFrame(valid_det)
            fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(symbol='circle', size=12, color='#ffd700', line=dict(color='white', width=1)), name='DRS Start'))
            fig.add_trace(go.Scatter(x=df_det['X'], y=df_det['Y'], mode='markers', marker=dict(symbol='circle', size=14, color='#ffd700', line=dict(color='#13131a', width=2)), hovertemplate="<b>DRS ACTIVATION START</b><extra></extra>", showlegend=False))

    # ── SPEED TRAP ──
    max_speed_idx = tel['Speed'].idxmax()
    if pd.notna(max_speed_idx):
        max_pt = tel.loc[max_speed_idx]
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(symbol='circle', size=14, color='#00d47e', line=dict(width=1.5, color='white')), name='Speed Trap'))
        fig.add_trace(go.Scatter(x=[max_pt['X']], y=[max_pt['Y']], mode='markers', marker=dict(symbol='circle', size=16, color='#00d47e', line=dict(width=2, color='white')), hovertemplate=f"<b>SPEED TRAP</b><br>{max_pt['Speed']} km/h<extra></extra>", showlegend=False))

    # ── CORNERS ──
    if circuit_info is not None and not circuit_info.corners.empty:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(size=16, color='#13131a', line=dict(width=1.5, color='white')), name='Corner'))
        for _, corner in circuit_info.corners.iterrows():
            fig.add_trace(go.Scatter(x=[corner['X']], y=[corner['Y']], mode='markers+text', marker=dict(size=18, color='#13131a', line=dict(width=1.5, color='white')), text=[f"<b>{int(corner['Number'])}</b>"], textposition='middle center', textfont=dict(size=10, color='white', family="JetBrains Mono"), hovertemplate=f"<b>Turn {int(corner['Number'])}</b><extra></extra>", showlegend=False))

    fig.update_layout(**PLOTLY_THEME, height=550, margin=dict(t=30, b=10, l=10, r=10), showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, bgcolor="rgba(0,0,0,0)"))
    fig.update_xaxes(showgrid=False, zeroline=False, showticklabels=False)
    fig.update_yaxes(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x", scaleratio=1)
    st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────
#  JSON COMPILER FOR JS WIDESCREEN TABLE (CRASH-PROOF CACHE)
# ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=3600)
def compile_table_payload(year, race, session_id, available_drivers, _session, _results_df, _laps):
    max_laps = int(_laps['LapNumber'].max()) if not _laps.empty else 0
    stats, pb_dict = [], {}
    global_mins, global_maxs = {}, {}
    
    for drv in available_drivers:
        drv_laps = _session.laps.pick_driver(drv).dropna(subset=['LapTime'])
        for _, lap in drv_laps.iterlaps():
            try:
                lap_tel = lap.get_telemetry()
                if lap_tel.empty: continue
                
                speeds = lap_tel['Speed']
                slow = speeds[speeds < 150].mean() if not speeds[speeds < 150].empty else 0
                med = speeds[(speeds >= 150) & (speeds <= 240)].mean() if not speeds[(speeds >= 150) & (speeds <= 240)].empty else 0
                fast = speeds[speeds > 240].mean() if not speeds[speeds > 240].empty else 0
                
                lap_time_s = lap['LapTime'].total_seconds()
                lap_time_str = f"{int(lap_time_s // 60)}:{lap_time_s % 60 :06.3f}"
                avg_speed = speeds.mean()
                speed_trap = lap.get('SpeedST', speeds.max())
                if pd.isna(speed_trap): speed_trap = speeds.max()
                
                stats.append({
                    "Lap": int(lap['LapNumber']), "Driver": drv, "Time": lap_time_str, "Time_s": lap_time_s, 
                    "Avg": avg_speed, "Slow": slow, "Med": med, "Fast": fast, "Trap": speed_trap,
                    "TrackStatus": str(lap.get('TrackStatus', '1'))
                })
            except: continue

    df_all = pd.DataFrame(stats)
    if df_all.empty: return None

    # Calculate Global and Personal Bests
    gb = {
        'Time_s': df_all['Time_s'].min(),
        'Avg': df_all['Avg'].max(), 'Slow': df_all['Slow'].max(), 'Med': df_all['Med'].max(),
        'Fast': df_all['Fast'].max(), 'Trap': df_all['Trap'].max()
    }
    pb = {
        'Time_s': df_all.groupby('Driver')['Time_s'].min().to_dict(),
        'Avg': df_all.groupby('Driver')['Avg'].max().to_dict(),
        'Slow': df_all.groupby('Driver')['Slow'].max().to_dict(),
        'Med': df_all.groupby('Driver')['Med'].max().to_dict(),
        'Fast': df_all.groupby('Driver')['Fast'].max().to_dict(),
        'Trap': df_all.groupby('Driver')['Trap'].max().to_dict(),
    }

    def get_f1_color(val, driver, metric, gb_dict, pb_dict, is_time=False):
        if pd.isna(val) or val == 0: return "#8888a0"
        if is_time:
            if val <= gb_dict[metric] + 0.001: return "#b051ff" # Session Best (Purple)
            if val <= pb_dict[metric][driver] + 0.001: return "#00d47e" # Personal Best (Green)
        else:
            if val >= gb_dict[metric] - 0.001: return "#b051ff"
            if val >= pb_dict[metric][driver] - 0.001: return "#00d47e"
        return "#ffd700" # Standard (Yellow)

    for col in ['Avg', 'Slow', 'Med', 'Fast', 'Trap']:
        global_mins[col], global_maxs[col] = df_all[col].min(), df_all[col].max()

    wd = _session.weather_data
    frames = {}
    
    for lap_num in range(1, max_laps + 1):
        lap_df = df_all[df_all['Lap'] == lap_num].sort_values('Time_s')
        if lap_df.empty: continue
        
        air_t, trk_t, wind_str, rain_b = 0, 0, "--", False
        status_val = lap_df['TrackStatus'].iloc[0]
        track_status = parse_track_status(status_val)
        
        lap_time_obj = _laps[_laps['LapNumber'] == lap_num]['Time'].min()
        if pd.notna(lap_time_obj) and not wd.empty:
            idx = (wd['Time'] - lap_time_obj).abs().idxmin()
            w_row = wd.loc[idx]
            air_t, trk_t = w_row.get('AirTemp', 0), w_row.get('TrackTemp', 0)
            rain_b = bool(w_row.get('Rainfall', False))
            w_spd, w_dir = w_row.get('WindSpeed', 0), w_row.get('WindDirection', 0)
            wind_str = f"{w_spd:.1f} m/s {get_compass_arrow(w_dir)}"
            
        leaderboard = []
        for _, row in lap_df.iterrows():
            drv = row['Driver']
            leaderboard.append({
                "drv": drv, "color": get_accurate_driver_color(drv, _results_df), "time": row['Time'],
                "time_c": get_f1_color(row['Time_s'], drv, 'Time_s', gb, pb, True),
                "avg": row['Avg'], "avg_c": get_gradient_color(row['Avg'], global_mins['Avg'], global_maxs['Avg']),
                "slow": row['Slow'], "slow_c": get_gradient_color(row['Slow'], global_mins['Slow'], global_maxs['Slow']),
                "med": row['Med'], "med_c": get_gradient_color(row['Med'], global_mins['Med'], global_maxs['Med']),
                "fast": row['Fast'], "fast_c": get_gradient_color(row['Fast'], global_mins['Fast'], global_maxs['Fast']),
                "trap": row['Trap'], "trap_c": get_gradient_color(row['Trap'], global_mins['Trap'], global_maxs['Trap'])
            })
                
        frames[lap_num] = {
            "status": track_status,
            "air": f"{air_t:.1f}", "trk": f"{trk_t:.1f}", "rain": rain_b, "wind": wind_str,
            "leaderboard": leaderboard
        }

    return json.dumps({"maxLaps": max_laps, "frames": frames})


def render_widescreen_table_player(json_payload):
    player_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <link href="https://fonts.googleapis.com/css2?family=Exo+2:wght@400;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
      <style>
        body {{ background: transparent; color: white; font-family: 'Exo 2', sans-serif; margin: 0; padding: 0; user-select: none; }}
        .deck {{ background: #13131a; border: 1px solid #2a2a38; border-top: 2px solid #e8002d; border-radius: 6px; padding: 12px 16px; margin-bottom: 12px; display: flex; align-items: center; gap: 15px; }}
        .btn {{ background: #e8002d; color: white; border: none; padding: 8px 24px; border-radius: 4px; font-weight: bold; cursor: pointer; text-transform: uppercase; letter-spacing: 1px; min-width: 120px; transition: 0.2s;}}
        .btn:hover {{ background: #ff1e46; }}
        select {{ background: #0d0d0f; color: white; border: 1px solid #2a2a38; padding: 8px 12px; border-radius: 4px; outline: none; font-weight: 600; }}
        input[type=range] {{ flex: 1; accent-color: #e8002d; cursor: pointer; }}
        
        .dash {{ display: flex; align-items: center; gap: 16px; background: #13131a; border: 1px solid #2a2a38; border-radius: 6px; padding: 10px 16px; margin-bottom: 12px; justify-content: space-between;}}
        .lap-tag {{ font-family: 'JetBrains Mono', monospace; font-size: 1.1rem; font-weight: 700; color: #e8e8f0; min-width: 100px; }}
        .prog-bg {{ flex: 1; height: 4px; background: #2a2a38; border-radius: 2px; overflow: hidden; margin: 0 20px; }}
        .prog-fill {{ height: 100%; background: #e8002d; border-radius: 2px; transition: width 0.1s linear; }}
        .stats {{ display: flex; gap: 20px; font-size: 0.85rem; font-family: 'JetBrains Mono', monospace; }}
        
        .table-container {{ width: 100%; background: #13131a; border: 1px solid #2a2a38; border-radius: 6px; overflow-y: auto; height: 600px; }}
        table {{ width: 100%; border-collapse: collapse; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; text-align: left; }}
        th {{ position: sticky; top: 0; background: #0d0d0f; color: #8888a0; font-family: 'Exo 2', sans-serif; font-size: 0.75rem; letter-spacing: 0.1em; text-transform: uppercase; padding: 14px 16px; border-bottom: 1px solid #e8002d; z-index: 1; }}
        td {{ padding: 12px 16px; border-bottom: 1px solid #2a2a38; color: #e8e8f0; text-shadow: 0px 1px 2px rgba(0,0,0,0.8); }}
      </style>
    </head>
    <body>
      <div class="deck">
        <button id="playBtn" class="btn">▶ PLAY</button>
        <select id="speedSel">
          <option value="1500">0.5x Speed</option>
          <option value="800" selected>1.0x Speed</option>
          <option value="400">2.0x Speed</option>
          <option value="150">4.0x Speed</option>
        </select>
        <input type="range" id="slider" min="1" max="100" value="1">
      </div>
      
      <div class="dash">
        <div class="lap-tag">LAP <span id="lapNum" style="color:#e8002d">1</span><span style="color:#555568" id="lapMax">/100</span></div>
        <div class="prog-bg"><div id="progFill" class="prog-fill" style="width: 0%;"></div></div>
        <div class="stats">
          <span id="stStatus" style="font-weight:800; color:#00d47e; border-right:1px solid #2a2a38; padding-right:15px;">● CLEAR</span>
          <span id="stRain" style="font-weight:700">☀️ Dry</span>
          <span id="stAir" style="color:#888">🌡️ Air --</span>
          <span id="stTrk" style="color:#888">⬛ Trk --</span>
          <span id="stWind" style="color:#888">💨 Wind --</span>
        </div>
      </div>
      
      <div class="table-container">
        <table>
          <thead>
            <tr><th>Pos</th><th>Driver</th><th>Lap Time</th><th>Avg</th><th>Slow</th><th>Med</th><th>Fast</th><th>Trap</th></tr>
          </thead>
          <tbody id="lb-body"></tbody>
        </table>
      </div>

      <script>
        const R = {json_payload};
        document.getElementById('slider').max = R.maxLaps;
        document.getElementById('lapMax').innerText = '/' + R.maxLaps;

        let currentLap = 1;
        let playing = false;
        let timer = null;

        function renderLap(lap) {{
            const f = R.frames[lap];
            if(!f) return;
            
            document.getElementById('lapNum').innerText = lap;
            document.getElementById('slider').value = lap;
            document.getElementById('progFill').style.width = ((lap / R.maxLaps) * 100) + '%';
            
            let sColor = f.status === 'Clear' ? '#00d47e' : (f.status === 'Red Flag' ? '#e8002d' : '#ffd700');
            let sIcon = f.status === 'Clear' ? '●' : (f.status === 'Red Flag' ? '✖' : '▲');
            document.getElementById('stStatus').innerHTML = `<span style="color:${{sColor}}">${{sIcon}} ${{f.status.toUpperCase()}}</span>`;
            
            const rc = f.rain ? '#4db8ff' : '#ffd700';
            const ri = f.rain ? '🌧️ Wet' : '☀️ Dry';
            document.getElementById('stRain').innerHTML = `<span style="color:${{rc}}">${{ri}}</span>`;
            document.getElementById('stAir').innerHTML = `<span style="color:#fff">Air:</span> ${{f.air}}°C`;
            document.getElementById('stTrk').innerHTML = `<span style="color:#fff">Trk:</span> ${{f.trk}}°C`;
            document.getElementById('stWind').innerHTML = `<span style="color:#fff">Wind:</span> ${{f.wind}}`;
            
            let tbody = document.getElementById("lb-body");
            tbody.innerHTML = "";
            let pos = 1;
            f.leaderboard.forEach(d => {{
                let tr = document.createElement("tr");
                tr.innerHTML = `
                    <td style="color:#888;">${{pos}}</td>
                    <td style="border-left: 4px solid ${{d.color}}; font-weight: bold; padding-left: 12px;">${{d.drv}}</td>
                    <td style="color:${{d.time_c}}; font-weight:800; text-shadow:0px 1px 3px rgba(0,0,0,0.9);">${{d.time}}</td>
                    <td style="background:${{d.avg_c}}; font-weight:bold; color:white;">${{d.avg.toFixed(1)}}</td>
                    <td style="background:${{d.slow_c}}; color:white;">${{d.slow.toFixed(1)}}</td>
                    <td style="background:${{d.med_c}}; color:white;">${{d.med.toFixed(1)}}</td>
                    <td style="background:${{d.fast_c}}; color:white;">${{d.fast.toFixed(1)}}</td>
                    <td style="background:${{d.trap_c}}; color:white;">${{d.trap.toFixed(1)}}</td>
                `;
                tbody.appendChild(tr);
                pos++;
            }});
        }}

        function step() {{
            while(currentLap < R.maxLaps && !R.frames[currentLap+1]) {{ currentLap++; }}
            if(currentLap < R.maxLaps) {{ currentLap++; renderLap(currentLap); }} 
            else {{ togglePlay(false); }}
        }}
        
        function togglePlay(force) {{
            playing = force !== undefined ? force : !playing;
            document.getElementById('playBtn').innerText = playing ? "⏸ PAUSE" : "▶ PLAY";
            if(playing) {{
                if(currentLap >= R.maxLaps) currentLap = 1;
                timer = setInterval(step, parseInt(document.getElementById('speedSel').value));
            }} else {{ clearInterval(timer); }}
        }}

        document.getElementById('playBtn').onclick = () => togglePlay();
        document.getElementById('slider').oninput = (e) => {{ togglePlay(false); currentLap = parseInt(e.target.value); if(R.frames[currentLap]) renderLap(currentLap); }};
        document.getElementById('speedSel').onchange = () => {{ if(playing) {{ togglePlay(false); togglePlay(true); }} }};

        while(!R.frames[currentLap] && currentLap < R.maxLaps) currentLap++;
        renderLap(currentLap); 
      </script>
    </body>
    </html>
    """
    components.html(player_html, height=750, scrolling=False)


# ─────────────────────────────────────────────────────────────
#  UI RENDERING: HEATMAPS & HIGH-DENSITY SCATTER
# ─────────────────────────────────────────────────────────────
def render_heatmaps(session, tel, results_df):
    st.divider()
    section_header("ADVANCED HEATMAPS", "Velocity & Action Zones")
    
    st.markdown('<div class="pw-section-label">Absolute Velocity Heatmap</div>', unsafe_allow_html=True)
    st.caption("High-density velocity plotting across the entire circuit layout.")
    
    fig_spd = go.Figure()
    fig_spd.add_trace(go.Scatter(
        x=tel['X'], y=tel['Y'], mode='markers',
        marker=dict(color=tel['Speed'], colorscale='Turbo', size=3, showscale=True, colorbar=dict(title="Speed (km/h)", len=0.8, thickness=10)),
        customdata=np.stack((tel['Speed'], tel['Wind_Type'], tel['Wind_Arrow']), axis=-1), 
        hovertemplate="<b>Speed:</b> %{customdata[0]} km/h<br><b>Wind:</b> %{customdata[1]} %{customdata[2]}<extra></extra>", 
        name="Speed"
    ))
    fig_spd.update_layout(**PLOTLY_THEME, height=550, margin=dict(t=0,b=0,l=0,r=0))
    fig_spd.update_xaxes(showgrid=False, zeroline=False, showticklabels=False)
    fig_spd.update_yaxes(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x", scaleratio=1)
    st.plotly_chart(fig_spd, use_container_width=True)
    
    st.markdown('<br><div class="pw-section-label">Overtake Hotspots (Action Zones)</div>', unsafe_allow_html=True)
    st.caption("High-density spatial mapping of heavy braking zones.")
    
    with st.spinner("Calculating spatial overtake trajectory matrices..."):
        clusters, ot_dict = get_spatial_overtakes(session, tel, results_df)
        
    fig_act = go.Figure()
    # Track Layout Outline
    fig_act.add_trace(go.Scatter(x=tel['X'], y=tel['Y'], mode='lines', line=dict(color='rgba(255,255,255,0.15)', width=3), hoverinfo='skip', showlegend=False))
    
    if not clusters.empty:
        x_density, y_density = [], []
        x_hover, y_hover, hov_text = [], [], []
        x_ot, y_ot = [], []
        
        for _, row in clusters.iterrows():
            c_id = int(row['cluster'])
            ot_list = ot_dict.get(c_id, [])
            if not ot_list: continue 
            
            # 1. High-density scatter logic: plot many semi-transparent dots to build "red intensity" volume
            np.random.seed(c_id) # For deterministic rendering
            num_dots = len(ot_list) * 20 
            for _ in range(num_dots):
                x_density.append(row['X'] + np.random.normal(0, 120))
                y_density.append(row['Y'] + np.random.normal(0, 120))

            # 2. Actual Overtake scatter points
            for idx, ot_str in enumerate(ot_list):
                angle = (idx / max(1, len(ot_list))) * 2 * math.pi
                radius = 30 + (idx % 4) * 20
                x_ot.append(row['X'] + radius * math.cos(angle))
                y_ot.append(row['Y'] + radius * math.sin(angle))
                
            # 3. Single invisible hover target for the entire corner
            x_hover.append(row['X'])
            y_hover.append(row['Y'])
            hov_text.append("<br>".join(ot_list))

        if x_density:
            # The Red Intensity Density Plot (No hover, purely visual)
            fig_act.add_trace(go.Scatter(
                x=x_density, y=y_density, mode='markers',
                marker=dict(color='#e8002d', size=5, opacity=0.3, line=dict(width=0)),
                hoverinfo='skip', showlegend=False
            ))
            
            # The Overtake Scatter (hoverinfo='skip' -> removes hover ONLY from these dots)
            fig_act.add_trace(go.Scatter(
                x=x_ot, y=y_ot, mode='markers',
                marker=dict(color='#00d47e', size=8, opacity=0.9, line=dict(color='white', width=0.5)),
                hoverinfo='skip',
                name="Overtake Executed", showlegend=True
            ))

            # The Unified Hover Target (Invisible, large radius covering the corner)
            fig_act.add_trace(go.Scatter(
                x=x_hover, y=y_hover, mode='markers',
                marker=dict(color='rgba(0,0,0,0)', size=60), # 100% transparent to the eye
                customdata=hov_text,
                hovertemplate="<b>OVERTAKES AT THIS CORNER:</b><br>%{customdata}<extra></extra>",
                name="Action Zone", showlegend=False
            ))
        else:
            st.info("No on-track overtakes detected in this session.")
        
    fig_act.update_layout(**PLOTLY_THEME, height=550, margin=dict(t=30,b=10,l=10,r=10), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, bgcolor="rgba(0,0,0,0)"))
    fig_act.update_xaxes(showgrid=False, zeroline=False, showticklabels=False)
    fig_act.update_yaxes(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x", scaleratio=1)
    st.plotly_chart(fig_act, use_container_width=True)

# ─────────────────────────────────────────────────────────────
#  UI RENDERING: ENGINEERING DESK
# ─────────────────────────────────────────────────────────────
def get_corner_overlay_3d(circuit_info, x_data, y_data, z_data):
    if circuit_info is not None and not circuit_info.corners.empty:
        corners = circuit_info.corners
        corner_z = []
        z_arr = z_data.values if isinstance(z_data, pd.Series) else z_data
        x_arr = x_data.values if isinstance(x_data, pd.Series) else x_data
        y_arr = y_data.values if isinstance(y_data, pd.Series) else y_data
        for cx, cy in zip(corners['X'], corners['Y']):
            dist = np.sqrt((x_arr - cx)**2 + (y_arr - cy)**2)
            idx = dist.argmin()
            corner_z.append(z_arr[idx] + 250) 
        return go.Scatter3d(
            x=corners['X'], y=corners['Y'], z=corner_z,
            mode='markers+text',
            marker=dict(size=12, color='white', line=dict(color='#111', width=3)),
            text=[f"<b>{n}</b>" for n in corners['Number']],
            textposition='middle center',
            textfont=dict(size=10, color='black', family="JetBrains Mono"),
            hoverinfo='skip', showlegend=False
        )
    return None

def render_engineering_desk(tel, circuit_info):
    st.divider()
    section_header("ENGINEERING DESK", "Track Geometry, Setup & Physics")
    
    st.markdown('<div class="pw-section-label">3D Topography (Solid Elevation Wall)</div>', unsafe_allow_html=True)
    st.caption("Drag to rotate. Calculates dynamic Z-axis topography.")
    
    fig_3d = go.Figure()
    x, y, z = tel['X'].values, tel['Y'].values, tel['Z'].values
    z_exag = z * 2.5 
    z_base = np.full_like(z_exag, z_exag.min() - 200) 

    X_surf = np.array([x, x])
    Y_surf = np.array([y, y])
    Z_surf = np.array([z_base, z_exag])
    
    fig_3d.add_trace(go.Surface(x=X_surf, y=Y_surf, z=Z_surf, colorscale=[[0, 'rgba(42, 42, 56, 0.8)'], [1, 'rgba(100, 100, 120, 0.9)']], showscale=False, hoverinfo='skip', name="Elevation Base"))
    fig_3d.add_trace(go.Scatter3d(x=x, y=y, z=z_exag, mode='lines', line=dict(color=tel['Speed'], colorscale='Plasma', width=8), customdata=np.stack((tel['Speed'], tel['nGear'], z), axis=-1), hovertemplate="<b>Elevation:</b> %{customdata[2]:.1f}m<br><b>Speed:</b> %{customdata[0]} km/h<br><b>Gear:</b> %{customdata[1]}<extra></extra>", name="Track Surface"))

    corner_trace_3d = get_corner_overlay_3d(circuit_info, x, y, z_exag)
    if corner_trace_3d: fig_3d.add_trace(corner_trace_3d)
    
    fig_3d.add_trace(go.Scatter3d(x=[None], y=[None], z=[None], mode='lines', line=dict(color='#646478', width=10), name="Solid Elevation Wall"))
    fig_3d.add_trace(go.Scatter3d(x=[None], y=[None], z=[None], mode='lines', line=dict(color='#e8002d', width=5), name="Racing Line (Speed Colored)"))
    fig_3d.add_trace(go.Scatter3d(x=[None], y=[None], z=[None], mode='markers', marker=dict(color='white', size=10, line=dict(color='#111', width=2)), name="Corner Marker"))
    
    fig_3d.update_layout(**PLOTLY_THEME, height=650, margin=dict(t=0, b=0, l=0, r=0), legend=dict(title="Topography Legend", orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5), scene=dict(aspectmode='data', xaxis=dict(showbackground=False, showticklabels=False, title="", showgrid=False, zeroline=False), yaxis=dict(showbackground=False, showticklabels=False, title="", showgrid=False, zeroline=False), zaxis=dict(showbackground=False, showticklabels=False, title="", showgrid=False, zeroline=False), camera=dict(eye=dict(x=1.2, y=1.2, z=0.8))))
    st.plotly_chart(fig_3d, use_container_width=True)

    col_gear, col_sev = st.columns(2)
    with col_gear:
        st.markdown('<br><div class="pw-section-label">Gearshift Modality</div>', unsafe_allow_html=True)
        st.caption("Color maps to Gear. Identifies short-shifting zones.")
        fig_gear = go.Figure()
        fig_gear.add_trace(go.Scatter(x=tel['X'], y=tel['Y'], mode='markers', marker=dict(color=tel['nGear'], colorscale='Turbo', size=4, showscale=True, colorbar=dict(title="Gear", thickness=10, len=0.8, x=1.0)), customdata=np.stack((tel['nGear'], tel['Wind_Type'], tel['Wind_Arrow']), axis=-1), hovertemplate="<b>Gear:</b> %{customdata[0]}<br><b>Wind:</b> %{customdata[1]} %{customdata[2]}<extra></extra>", name="Gear"))
        fig_gear.update_layout(**PLOTLY_THEME, height=450, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
        fig_gear.update_xaxes(showgrid=False, zeroline=False, showticklabels=False)
        fig_gear.update_yaxes(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x", scaleratio=1)
        st.plotly_chart(fig_gear, use_container_width=True)

    with col_sev:
        st.markdown('<br><div class="pw-section-label">Severity Index (Braking Zones)</div>', unsafe_allow_html=True)
        st.caption("Deep red highlights the heaviest longitudinal braking forces.")
        fig_sev = go.Figure()
        fig_sev.add_trace(go.Scatter(x=tel['X'], y=tel['Y'], mode='markers', marker=dict(color=tel['Long_G'].abs(), colorscale='Reds', size=4, showscale=True, colorbar=dict(title="Braking Gs", thickness=10, len=0.8, x=1.0)), customdata=np.stack((tel['Long_G'].abs(), tel['Wind_Type'], tel['Wind_Arrow']), axis=-1), hovertemplate="<b>Braking G-Force:</b> %{customdata[0]:.2f} G<br><b>Wind:</b> %{customdata[1]} %{customdata[2]}<extra></extra>", name="Braking"))
        fig_sev.update_layout(**PLOTLY_THEME, height=450, margin=dict(t=0, b=0, l=0, r=0), showlegend=False)
        fig_sev.update_xaxes(showgrid=False, zeroline=False, showticklabels=False)
        fig_sev.update_yaxes(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x", scaleratio=1)
        st.plotly_chart(fig_sev, use_container_width=True)

    st.markdown('<br><div class="pw-section-label">Symmetry Check (G-G Friction Circle)</div>', unsafe_allow_html=True)
    st.caption("Checks lateral vs longitudinal balance to identify asymmetric setups.")
    fig_gg = go.Figure()
    fig_gg.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.2)")
    fig_gg.add_vline(x=0, line_dash="dash", line_color="rgba(255,255,255,0.2)")
    fig_gg.add_trace(go.Scatter(x=tel['Lat_G'], y=tel['Long_G'], mode='markers', marker=dict(color=tel['Speed'], colorscale='Plasma', size=6, showscale=True, colorbar=dict(title="Speed", thickness=12, len=0.8, x=1.02)), customdata=np.stack((tel['Lat_G'], tel['Long_G'], tel['Wind_Type'], tel['Wind_Arrow']), axis=-1), hovertemplate="<b>Lat:</b> %{customdata[0]:.2f} G<br><b>Long:</b> %{customdata[1]:.2f} G<br><b>Wind:</b> %{customdata[2]} %{customdata[3]}<extra></extra>", name="G-Forces"))
    fig_gg.update_layout(**PLOTLY_THEME, height=550, margin=dict(t=30, b=30, l=30, r=30), showlegend=False)
    fig_gg.update_xaxes(title="Lateral G (Left / Right)", range=[-5.5, 5.5], showgrid=True, gridcolor='rgba(255,255,255,0.05)')
    fig_gg.update_yaxes(title="Longitudinal G (Braking / Accel)", range=[-6, 3], showgrid=True, gridcolor='rgba(255,255,255,0.05)')
    st.plotly_chart(fig_gg, use_container_width=True)


# ══════════════════════════════════════════════════════════════
#  PUBLIC ENTRY POINT
# ══════════════════════════════════════════════════════════════
def render_circuit(year, race, session_id, session_name, available_drivers):
    with st.spinner("Compiling track geometry, physics engine, and topography..."):
        session, tel, ref_lap, circuit_info, err = process_circuit_data(year, race, session_id)
        
    if err or tel is None:
        no_data_error(err or "Unable to map circuit layout. Try a different session.")
        return
        
    results_df = getattr(session, 'results', pd.DataFrame())
    laps = session.laps.dropna(subset=['LapNumber', 'LapTime', 'Driver'])

    st.divider()
    section_header("SESSION DASHBOARD", "Interactive Track Walk & Lap-by-Lap Replay")

    # Native Streamlit Map Plot
    render_static_track_map(tel, ref_lap, circuit_info)

    if available_drivers:
        with st.spinner("Preloading vector telemetry & wind physics (Takes ~10s)..."):
            json_payload = compile_table_payload(year, race, session_id, available_drivers, _session=session, _results_df=results_df, _laps=laps)
            
        if json_payload:
            render_widescreen_table_player(json_payload)
            
    render_heatmaps(session, tel, results_df)
    render_engineering_desk(tel, circuit_info)