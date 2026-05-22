"""
replay.py — High-Density Telemetry & Quali Timeline Board  ·  PitWall Analytics
"""
import json
import math
import textwrap
import streamlit as st
import pandas as pd
import numpy as np
import fastf1
import streamlit.components.v1 as components

from utils import (
    safe_load_session, section_header, no_data_error, driver_color
)

# ─────────────────────────────────────────────────────────────
#  Utility: JSON-Safe Floats & Split Formatting
# ─────────────────────────────────────────────────────────────
def _f(x):
    try:
        v = float(x)
        return 0.0 if (math.isnan(v) or math.isinf(v)) else round(v, 4)
    except Exception:
        return 0.0

def _fmt_split(td, is_lap=False):
    if pd.isna(td): return "—"
    s = td.total_seconds()
    if s <= 0: return "—"
    if is_lap and s >= 60:
        return f"{int(s//60)}:{s%60:06.3f}"
    return f"{s:.3f}"

def _fmt_race_time(td):
    if pd.isna(td): return "—"
    s = td.total_seconds()
    if s <= 0: return "—"
    hours = int(s // 3600)
    minutes = int((s % 3600) // 60)
    seconds = s % 60
    
    # If over 20 minutes, format as Total Race Time
    if hours > 0 or minutes > 20: 
        if hours > 0: return f"{hours}:{minutes:02d}:{seconds:06.3f}"
        else: return f"{minutes:02d}:{seconds:06.3f}"
    # Otherwise, format as Gap Interval
    else: 
        if minutes > 0: return f"+{minutes}:{seconds:06.3f}"
        else: return f"+{seconds:.3f}s"

def _eval_split(current, pb, sb, is_lap=False):
    if pd.isna(current): return ["—", ""]
    val = _fmt_split(current, is_lap)
    if current <= sb: return [val, "p"]  # Purple (Session Best)
    if current <= pb: return [val, "g"]  # Green  (Personal Best)
    return [val, "y"]                    # Yellow (Standard)


# ─────────────────────────────────────────────────────────────
#  TYRE ICON ENGINE
# ─────────────────────────────────────────────────────────────
TYRE_ICONS = {
    "SOFT": "🔴",
    "MEDIUM": "🟡",
    "HARD": "⚪",
    "INTERMEDIATE": "🟢",
    "WET": "🔵",
    "HYPERSOFT": "💖",
    "ULTRASOFT": "💜",
    "SUPERSOFT": "❤️",
}

def tyre_icon(compound):
    if pd.isna(compound): return "⚫"
    compound = str(compound).upper().strip()
    return TYRE_ICONS.get(compound, "⚫")


# ─────────────────────────────────────────────────────────────
#  OT/DRS TELEMETRY HELPER
# ─────────────────────────────────────────────────────────────
def _build_ot_active(session, laps):
    """Safely extracts OT/DRS deployment boolean per driver, per lap."""
    
    drv_num_map = {}
    for drv in laps['Driver'].unique():
        d_nums = laps[laps['Driver'] == drv]['DriverNumber'].dropna().unique()
        if len(d_nums) > 0:
            try: drv_num_map[drv] = str(int(float(d_nums[0])))
            except Exception: drv_num_map[drv] = str(d_nums[0])

    car_data = getattr(session, "car_data", {})
    ot_active = {drv: {} for drv in drv_num_map.keys()}

    if not car_data:
        return ot_active

    for drv, c_num in drv_num_map.items():
        cd = None
        
        if c_num in car_data: cd = car_data[c_num]
        elif int(c_num) in car_data: cd = car_data[int(c_num)]
        elif str(c_num) in car_data: cd = car_data[str(c_num)]
        
        if cd is None or "DRS" not in cd.columns: 
            continue

        cd_ot_open = cd[cd["DRS"] >= 8]
        drv_laps = laps[laps["Driver"] == drv]

        for _, lap in drv_laps.iterrows():
            try: 
                lap_num = int(float(lap['LapNumber']))
            except Exception: 
                continue

            ls, le = lap.get('LapStartTime'), lap.get('Time')
            if pd.isna(ls) or pd.isna(le):
                ot_active[drv][lap_num] = False
                continue

            lap_window = cd_ot_open[(cd_ot_open['Time'] >= ls) & (cd_ot_open['Time'] <= le)]
            ot_active[drv][lap_num] = len(lap_window) > 0

    return ot_active


# ══════════════════════════════════════════════════════════════
#  STEP 1A — RACE ENGINE (Dynamic Telemetry)
# ══════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False, ttl=3600)
def precalculate_race_data(year, race, session_id):
    try:
        session = fastf1.get_session(year, race, session_id)
        session.load(telemetry=True, weather=True, messages=True)
    except Exception as e:
        return None, 0, None, str(e)

    laps         = session.laps.copy()
    results      = getattr(session, "results",             pd.DataFrame())
    weather_data = getattr(session, "weather_data",        pd.DataFrame())
    rcm          = getattr(session, "race_control_messages", pd.DataFrame())

    if laps.empty:
        return None, 0, None, "No lap data found."

    laps["LapTime_s"]  = laps["LapTime"].dt.total_seconds()
    laps["LapNumber"]  = pd.to_numeric(laps["LapNumber"],  errors="coerce")
    laps["Position"]   = pd.to_numeric(laps["Position"],   errors="coerce")
    laps               = laps.dropna(subset=["LapNumber"])
    max_laps           = int(laps["LapNumber"].max())

    track_length_km = 0.0
    try:
        fl_tel = laps.pick_fastest().get_telemetry()
        track_length_km = fl_tel['Distance'].max() / 1000.0
    except Exception: pass

    grid_positions = {r["Abbreviation"]: r.get("GridPosition", 0) for _, r in results.iterrows()} if not results.empty else {}
    
    # Process OT/DRS Logic
    ot_active = _build_ot_active(session, laps)

    sb_s1, sb_s2, sb_s3, sb_lt = laps['Sector1Time'].min(), laps['Sector2Time'].min(), laps['Sector3Time'].min(), laps['LapTime'].min()
    replay_frames = {}

    for lap_num in range(1, max_laps + 1):
        leader_rows = laps[(laps["LapNumber"] == lap_num) & (laps["Position"] == 1)]
        if leader_rows.empty: leader_rows = laps[laps["LapNumber"] == lap_num].dropna(subset=["Time"]).sort_values("Time").head(1)
        if leader_rows.empty: continue

        l_row = leader_rows.iloc[0]
        snapshot_sec = l_row["Time"].total_seconds() - (l_row["LapTime"].total_seconds() / 2.0) if pd.notna(l_row.get("LapTime")) else l_row["Time"].total_seconds()

        all_past = laps[laps["LapNumber"] <= lap_num]
        
        # ── FASTEST BANNERS ──
        fastest_overall, fastest_current = None, None
        valid_past = all_past.dropna(subset=["LapTime"])
        if not valid_past.empty:
            bl = valid_past.loc[valid_past["LapTime"].idxmin()]
            fastest_overall = {"drv": bl["Driver"], "lap": _fmt_split(bl.get('LapTime'), True), "num": int(bl["LapNumber"]), "s1": _fmt_split(bl.get('Sector1Time')), "s2": _fmt_split(bl.get('Sector2Time')), "s3": _fmt_split(bl.get('Sector3Time'))}

        valid_cur = laps[(laps["LapNumber"] == lap_num)].dropna(subset=["LapTime"])
        if not valid_cur.empty:
            cl = valid_cur.loc[valid_cur["LapTime"].idxmin()]
            fastest_current = {"drv": cl["Driver"], "lap": _fmt_split(cl.get('LapTime'), True), "s1": _fmt_split(cl.get('Sector1Time')), "s2": _fmt_split(cl.get('Sector2Time')), "s3": _fmt_split(cl.get('Sector3Time'))}

        state = all_past.groupby("Driver", as_index=False).last()
        state["RaceTime_s"] = state["Time"].dt.total_seconds()
        state = state.sort_values(["LapNumber","RaceTime_s"], ascending=[False, True]).reset_index(drop=True)
        state["LivePos"] = state.index + 1

        frame_rows = []
        prev_raw = (replay_frames.get(lap_num - 1) or {}).get("raw_dict", {})

        for idx, row in state.iterrows():
            drv, live_pos, drv_lap = row["Driver"], int(row["LivePos"]), int(row["LapNumber"])

            if idx == 0: interval, interval_raw, trend = "LEADER", 0.0, ""
            else:
                ahead = state.iloc[idx - 1]
                laps_diff = int(ahead["LapNumber"]) - drv_lap
                stale = (lap_num - drv_lap) > 2

                if stale: interval, interval_raw, trend = "OUT", 9999.0, ""
                elif laps_diff > 0: interval, interval_raw, trend = f"+{laps_diff}L", 999.0, ""
                else:
                    interval_raw = max(0.0, row["RaceTime_s"] - ahead["RaceTime_s"])
                    prev_gap = prev_raw.get(drv, {}).get("interval_raw", interval_raw)
                    trend = " ↓" if interval_raw < prev_gap else (" ↑" if interval_raw > prev_gap else "") if 0 < prev_gap < 900 else ""
                    interval = f"+{interval_raw:.3f}s{trend}"

            past_drv = laps[(laps["Driver"] == drv) & (laps["LapNumber"] <= lap_num)]
            tyre_dots = "".join(tyre_icon(s.get("Compound")) for _, s in past_drv.drop_duplicates(subset=["Stint"]).iterrows())
            if pd.notna(row.get("PitInTime")) and (lap_num - drv_lap) == 0: tyre_dots += " 🔧"
            
            tyre_age = "-"
            if not past_drv.empty:
                t_age = past_drv.iloc[-1].get("TyreLife")
                if pd.notna(t_age): tyre_age = f"{int(t_age)} L"

            is_out = interval == "OUT"
            s1_val, s2_val, s3_val, lt_val = ["—", ""], ["—", ""], ["—", ""], ["—", ""]
            top_spd, avg_spd = "—", "—"

            if not past_drv.empty and not is_out:
                pb_s1, pb_s2, pb_s3, pb_lt = past_drv['Sector1Time'].min(), past_drv['Sector2Time'].min(), past_drv['Sector3Time'].min(), past_drv['LapTime'].min()
                cur_lap = past_drv.iloc[-1]
                
                s1_val = _eval_split(cur_lap.get('Sector1Time'), pb_s1, sb_s1)
                s2_val = _eval_split(cur_lap.get('Sector2Time'), pb_s2, sb_s2)
                s3_val = _eval_split(cur_lap.get('Sector3Time'), pb_s3, sb_s3)
                lt_val = _eval_split(cur_lap.get('LapTime'), pb_lt, sb_lt, True)
                
                if pd.notna(cur_lap.get('SpeedST')): top_spd = f"{int(cur_lap['SpeedST'])}"
                if track_length_km > 0 and pd.notna(cur_lap.get('LapTime')):
                    lt_hrs = cur_lap['LapTime'].total_seconds() / 3600.0
                    if lt_hrs > 0: avg_spd = f"{int(track_length_km / lt_hrs)}"

            # Robust Grid Position Catch
            try:
                gp = grid_positions.get(drv, live_pos)
                pos_delta = int(float(gp)) - int(live_pos) if pd.notna(gp) else 0
            except Exception:
                pos_delta = 0

            frame_rows.append({
                "Pos": live_pos,
                "Driver": drv,
                "Grid Δ": pos_delta,
                "OT": ot_active.get(drv, {}).get(drv_lap, False),
                "Season2026": int(year) >= 2026,
                "Interval": interval, "interval_raw": interval_raw, 
                "S1": s1_val, "S2": s2_val, "S3": s3_val, "LapTime": lt_val,
                "AvgSpd": avg_spd, "TopSpd": top_spd, "Tyres": tyre_dots, "TyreAge": tyre_age
            })

        stat_codes = "".join(leader_rows["TrackStatus"].dropna().astype(str).tolist())
        global_status = ("SC/VSC" if "4" in stat_codes or "6" in stat_codes else "Red Flag" if "5" in stat_codes else "Yellow" if "2" in stat_codes else "Clear")

        s1_y = s2_y = s3_y = False
        if global_status == "Yellow" and not rcm.empty:
            try:
                col = "Time" if "Time" in rcm.columns else "SessionTime"
                if col in rcm.columns and pd.api.types.is_timedelta64_dtype(rcm[col]):
                    rcm_s = rcm[col].dt.total_seconds()
                    recent = rcm[(rcm_s <= snapshot_sec) & (rcm_s >= snapshot_sec - 90)]
                    for _, m in recent.iterrows():
                        txt = str(m["Message"]).upper()
                        if "YELLOW" in txt:
                            if "SECTOR 1" in txt: s1_y = True
                            if "SECTOR 2" in txt: s2_y = True
                            if "SECTOR 3" in txt: s3_y = True
                        if "CLEAR" in txt:
                            if "SECTOR 1" in txt: s1_y = False
                            if "SECTOR 2" in txt: s2_y = False
                            if "SECTOR 3" in txt: s3_y = False
            except Exception: pass 

        air_t = trk_t = "–"
        rain  = False
        if not weather_data.empty:
            wt = weather_data["Time"].dt.total_seconds().values
            wi = int(np.clip(np.searchsorted(wt, snapshot_sec), 0, len(wt) - 1))
            w_row = weather_data.iloc[wi]
            air_t = f"{float(w_row.get('AirTemp', 0)):.1f}°C"
            trk_t = f"{float(w_row.get('TrackTemp', 0)):.1f}°C"
            rain  = bool(w_row.get("Rainfall", False))

        tower_df = pd.DataFrame(frame_rows).drop(columns=["interval_raw"]).set_index("Pos")
        replay_frames[lap_num] = {
            "df": tower_df, "fast_ovr": fastest_overall, "fast_cur": fastest_current,
            "stat": {"global": global_status, "s1": s1_y, "s2": s2_y, "s3": s3_y, "air": air_t, "trk": trk_t, "rain": rain}
        }

    return replay_frames, max_laps, results, None


# ══════════════════════════════════════════════════════════════
#  STEP 1B — QUALIFYING TIMELINE ENGINE (Chronological Events)
# ══════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False, ttl=3600)
def precalculate_quali_data(year, race, session_id):
    try:
        session = fastf1.get_session(year, race, session_id)
        session.load(telemetry=True, weather=False, messages=False)
    except Exception as e:
        return None, None, str(e)

    laps = session.laps.copy()
    results = getattr(session, "results", pd.DataFrame())
    if laps.empty: return None, None, "No lap data found."

    valid_laps = laps.dropna(subset=['LapTime']).sort_values('Time').reset_index(drop=True)
    if valid_laps.empty: return None, None, "No timed laps found."

    valid_laps['TimeDiff'] = valid_laps['Time'].diff().dt.total_seconds()
    
    # Process OT/DRS Logic for Quali
    ot_active = _build_ot_active(session, laps)

    phases = []
    current_phase = 1
    is_quali = session_id.upper().startswith("Q")

    for diff in valid_laps['TimeDiff']:
        if pd.notna(diff) and diff > 420:
            if is_quali and current_phase >= 3:
                pass
            else:
                current_phase += 1

        phase_name = f"Q{current_phase}" if is_quali else f"Run {current_phase}"
        phases.append(phase_name)

    valid_laps['Phase'] = phases
    all_drivers = results["Abbreviation"].tolist() if not results.empty else valid_laps["Driver"].unique().tolist()
    
    master_payload = {"Full Session": {}}
    for p in valid_laps['Phase'].unique(): master_payload[p] = {}
    
    for phase_key in master_payload.keys():
        phase_laps = valid_laps if phase_key == "Full Session" else valid_laps[valid_laps['Phase'] == phase_key].reset_index(drop=True)
        if phase_laps.empty: continue
        
        frames = {}
        for k in range(len(phase_laps)):
            past = phase_laps.iloc[:k+1]
            cur_lap = phase_laps.iloc[k]
            
            sb_s1, sb_s2, sb_s3, sb_lt = past['Sector1Time'].min(), past['Sector2Time'].min(), past['Sector3Time'].min(), past['LapTime'].min()
            best_idx = past.groupby('Driver')['LapTime'].idxmin()
            best_laps = past.loc[best_idx].sort_values('LapTime').reset_index(drop=True)
            
            p1_time = best_laps.iloc[0]['LapTime']
            row_data = []
            set_drivers = set()
            
            for pos, (idx, row) in enumerate(best_laps.iterrows(), 1):
                drv, lt = row['Driver'], row['LapTime']
                set_drivers.add(drv)
                
                gap_str = "LEADER" if pos == 1 else f"+{(lt - p1_time).total_seconds():.3f}s"
                s1_val = _eval_split(row['Sector1Time'], row['Sector1Time'], sb_s1)
                s2_val = _eval_split(row['Sector2Time'], row['Sector2Time'], sb_s2)
                s3_val = _eval_split(row['Sector3Time'], row['Sector3Time'], sb_s3)
                lt_val = _eval_split(lt, lt, sb_lt, True)
                top_spd = f"{int(row['SpeedST'])}" if pd.notna(row.get('SpeedST')) else "—"
                
                ot_val = False
                if pd.notna(row.get('LapNumber')):
                    ot_val = ot_active.get(drv, {}).get(int(row['LapNumber']), False)

                row_data.append({
                    "Pos": pos, "Driver": drv, "Interval": gap_str, 
                    "OT": ot_val, "Season2026": int(year) >= 2026,
                    "S1": s1_val, "S2": s2_val, "S3": s3_val, "LapTime": lt_val,
                    "TopSpd": top_spd, "Tyres": tyre_icon(row.get('Compound'))
                })
                
            for drv in [d for d in all_drivers if d not in set_drivers]:
                row_data.append({
                    "Pos": "—", "Driver": drv, "Interval": "NO TIME", 
                    "OT": False, "Season2026": int(year) >= 2026,
                    "S1": ["—", ""], "S2": ["—", ""], "S3": ["—", ""], "LapTime": ["—", ""], "TopSpd": "—", "Tyres": "—"
                })
                
            fast_ovr = {"drv": best_laps.iloc[0]['Driver'], "lap": _fmt_split(best_laps.iloc[0]['LapTime'], True), "num": k+1, "s1": _fmt_split(best_laps.iloc[0]['Sector1Time']), "s2": _fmt_split(best_laps.iloc[0]['Sector2Time']), "s3": _fmt_split(best_laps.iloc[0]['Sector3Time'])}
            fast_cur = {"drv": cur_lap['Driver'], "lap": _fmt_split(cur_lap['LapTime'], True), "s1": _fmt_split(cur_lap['Sector1Time']), "s2": _fmt_split(cur_lap['Sector2Time']), "s3": _fmt_split(cur_lap['Sector3Time'])}
            
            frames[k+1] = {"df": pd.DataFrame(row_data), "fast_ovr": fast_ovr, "fast_cur": fast_cur, "stat": {"global": "Clear", "air": "—", "trk": "—", "rain": False}}
            
        master_payload[phase_key] = {"frames": frames, "max_events": len(phase_laps)}
        
    return master_payload, results, None


# ══════════════════════════════════════════════════════════════
#  STEP 2 — HIGH-DENSITY HTML TOWER RENDERING
# ══════════════════════════════════════════════════════════════

def _tower_html(tower_df: pd.DataFrame, results: pd.DataFrame, is_quali=False) -> str:
    C_MAP = {'p': ('#b138dd', 'rgba(177,56,221,0.15)'), 'g': ('#00d47e', 'rgba(0,212,126,0.15)'), 'y': ('#ffd700', 'rgba(255,215,0,0.1)'), '': ('#555568', 'transparent')}
    def style_td(split_data):
        fg, bg = C_MAP.get(split_data[1], C_MAP[''])
        return f'<td style="padding:8px 10px;color:{fg};background:{bg};font-size:.85rem;font-family:\'JetBrains Mono\',monospace;text-align:center;font-weight:700;border-left:1px solid rgba(255,255,255,0.02);">{split_data[0]}</td>'

    rows_html = []
    for pos, row in tower_df.iterrows():
        drv, interval = str(row.get("Driver", "")), str(row.get("Interval", ""))
        dcolor = driver_color(drv, results)
        
        badge_label = "OT" if row.get("Season2026", False) else "DRS"
        active_color = "#00d47e"

        ot_html = (
            f'<span style="color:{active_color}; border:1px solid {active_color}; padding:1px 4px; border-radius:3px; font-size:0.55rem; margin-left:8px; vertical-align:middle; background:rgba(0,212,126,0.1);">{badge_label}</span>'
            if bool(row.get("OT", False))
            else
            f'<span style="color:#555568; border:1px solid #555568; padding:1px 4px; border-radius:3px; font-size:0.55rem; margin-left:8px; vertical-align:middle; background:rgba(120,120,120,0.08);">{badge_label}</span>'
        )

        if interval == "LEADER": int_style, int_text = "color:#ffd700;font-weight:700", "LEADER"
        elif interval in ["OUT", "NO TIME"]: int_style, int_text = "color:#555568;font-style:italic", interval
        elif "↓" in interval: int_style, int_text = "color:#00d47e;font-weight:600", interval
        elif "↑" in interval: int_style, int_text = "color:#e8002d", interval
        else: int_style, int_text = "color:#c0c0d0", interval

        row_bg = "rgba(255,255,255,0.025)" if (isinstance(pos, int) and pos % 2 == 0) else "transparent"

        race_cols = f"""
          <td style="padding:8px 10px;color:#a0a0b0;font-size:.8rem;font-family:'JetBrains Mono',monospace;text-align:center">{row.get("AvgSpd", "—")}</td>
          <td style="padding:8px 10px;color:#a0a0b0;font-size:.8rem;font-family:'JetBrains Mono',monospace;text-align:center">{row.get("TopSpd", "—")}</td>
          <td style="padding:8px 10px;font-size:.95rem;letter-spacing:.05em;text-align:center">{row.get("Tyres", "—")}</td>
          <td style="padding:8px 10px;color:#a0a0b0;font-size:.8rem;font-family:'JetBrains Mono',monospace;text-align:center">{row.get("TyreAge", "—")}</td>
        """ if not is_quali else f"""
          <td style="padding:8px 10px;color:#a0a0b0;font-size:.8rem;font-family:'JetBrains Mono',monospace;text-align:center">{row.get("TopSpd", "—")}</td>
          <td style="padding:8px 10px;font-size:.95rem;letter-spacing:.05em;text-align:center">{row.get("Tyres", "—")}</td>
        """

        grid_delta = ""
        if not is_quali:
            try:
                dv = int(row.get("Grid Δ", 0))
                if dv > 0: d_style, d_text = "color:#00d47e;font-weight:700", f"↑{dv}"
                elif dv < 0: d_style, d_text = "color:#e8002d;font-weight:700", f"↓{abs(dv)}"
                else: d_style, d_text = "color:#555568", "–"
            except Exception: d_style, d_text = "color:#555568", "–"
            grid_delta = f'<td style="padding:8px 10px;{d_style};font-size:.8rem;text-align:center">{d_text}</td>'

        rows_html.append(f"""
        <tr style="background:{row_bg};border-bottom:1px solid #1e1e2e">
          <td style="padding:8px 10px;color:#888;font-size:.75rem;width:28px">{pos}</td>
          <td style="padding:8px 10px;border-left:3px solid {dcolor};color:{dcolor};font-weight:700;letter-spacing:.08em;">{drv}{ot_html}</td>
          {grid_delta}
          <td style="padding:8px 12px;{int_style};font-size:.8rem;font-family:'JetBrains Mono',monospace;">{int_text}</td>
          {style_td(row.get("S1", ["—", ""]))}
          {style_td(row.get("S2", ["—", ""]))}
          {style_td(row.get("S3", ["—", ""]))}
          {style_td(row.get("LapTime", ["—", ""]))}
          {race_cols}
        </tr>""")

    race_headers = f"""
        <th style="padding:8px 10px;color:#555568;font-size:.65rem;letter-spacing:.15em;text-align:center;font-weight:600">GRID Δ</th>
        <th style="padding:8px 12px;color:#555568;font-size:.65rem;letter-spacing:.15em;text-align:left;font-weight:600">INTERVAL</th>
        <th style="padding:8px 10px;color:#555568;font-size:.65rem;letter-spacing:.15em;text-align:center;font-weight:600">S1</th>
        <th style="padding:8px 10px;color:#555568;font-size:.65rem;letter-spacing:.15em;text-align:center;font-weight:600">S2</th>
        <th style="padding:8px 10px;color:#555568;font-size:.65rem;letter-spacing:.15em;text-align:center;font-weight:600">S3</th>
        <th style="padding:8px 12px;color:#555568;font-size:.65rem;letter-spacing:.15em;text-align:center;font-weight:600;background:rgba(255,255,255,0.01)">LAP TIME</th>
        <th style="padding:8px 10px;color:#555568;font-size:.65rem;letter-spacing:.15em;text-align:center;font-weight:600">AVG KM/H</th>
        <th style="padding:8px 10px;color:#555568;font-size:.65rem;letter-spacing:.15em;text-align:center;font-weight:600">TOP KM/H</th>
        <th style="padding:8px 10px;color:#555568;font-size:.65rem;letter-spacing:.15em;text-align:center;font-weight:600">TYRES</th>
        <th style="padding:8px 10px;color:#555568;font-size:.65rem;letter-spacing:.15em;text-align:center;font-weight:600">AGE</th>
    """ if not is_quali else f"""
        <th style="padding:8px 12px;color:#555568;font-size:.65rem;letter-spacing:.15em;text-align:left;font-weight:600">GAP</th>
        <th style="padding:8px 10px;color:#555568;font-size:.65rem;letter-spacing:.15em;text-align:center;font-weight:600">BEST S1</th>
        <th style="padding:8px 10px;color:#555568;font-size:.65rem;letter-spacing:.15em;text-align:center;font-weight:600">BEST S2</th>
        <th style="padding:8px 10px;color:#555568;font-size:.65rem;letter-spacing:.15em;text-align:center;font-weight:600">BEST S3</th>
        <th style="padding:8px 12px;color:#555568;font-size:.65rem;letter-spacing:.15em;text-align:center;font-weight:600;background:rgba(255,255,255,0.01)">BEST LAP</th>
        <th style="padding:8px 10px;color:#555568;font-size:.65rem;letter-spacing:.15em;text-align:center;font-weight:600">TOP KM/H</th>
        <th style="padding:8px 10px;color:#555568;font-size:.65rem;letter-spacing:.15em;text-align:center;font-weight:600">TYRES</th>
    """

    body = "".join(rows_html)
    return f"""
      <table style="width:100%;border-collapse:collapse;white-space:nowrap">
        <thead style="position:sticky;top:0;z-index:1">
          <tr style="background:#0d0d0f;border-bottom:2px solid #e8002d">
            <th style="padding:8px 10px;color:#555568;font-size:.65rem;letter-spacing:.15em;text-align:left;font-weight:600">POS</th>
            <th style="padding:8px 10px;color:#555568;font-size:.65rem;letter-spacing:.15em;text-align:left;font-weight:600">DRV</th>
            {race_headers}
          </tr>
        </thead>
        <tbody>{body}</tbody>
      </table>"""


# ══════════════════════════════════════════════════════════════
#  STEP 3 — NATIVE JAVASCRIPT PLAYER (Zero-Latency Core)
# ══════════════════════════════════════════════════════════════

def render_js_player(replay_frames, max_laps, results, is_quali=False):
    payload = {"maxLaps": max_laps, "frames": {}}
    for lap, frame in replay_frames.items():
        payload["frames"][lap] = {
            "tower": _tower_html(frame["df"], results, is_quali),
            "stat": frame.get("stat", {}),
            "fast_ovr": frame.get("fast_ovr"),
            "fast_cur": frame.get("fast_cur")
        }

    json_data = json.dumps(payload)
    lbl_tag = "TIMED LAP" if is_quali else "LAP"

    engine_html = f"""
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
        
        .dash {{ display: flex; align-items: center; gap: 16px; background: #13131a; border: 1px solid #2a2a38; border-radius: 6px; padding: 10px 16px; margin-bottom: 12px; }}
        .lap-tag {{ font-family: 'JetBrains Mono', monospace; font-size: 1.1rem; font-weight: 700; color: #e8e8f0; }}
        .prog-bg {{ flex: 1; height: 4px; background: #2a2a38; border-radius: 2px; overflow: hidden; }}
        .prog-fill {{ height: 100%; background: #e8002d; border-radius: 2px; transition: width 0.1s linear; }}
        .stats {{ display: flex; gap: 20px; font-size: 0.85rem; }}
        
        .warn {{ background: rgba(255,215,0,0.12); border: 1px solid rgba(255,215,0,0.4); border-radius: 4px; padding: 6px 14px; font-size: 0.8rem; color: #ffd700; font-weight: 600; margin-bottom: 10px; display: none;}}
        
        .banners {{ display: flex; gap: 12px; margin-bottom: 10px; }}
        .fastest-banner {{ flex: 1; display: none; align-items: center; justify-content: space-between; padding: 8px 16px; background: rgba(177,56,221,0.08); border: 1px solid rgba(177,56,221,0.3); border-radius: 6px; color: #b138dd; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 700; }}
        .fastest-banner.current {{ background: rgba(0,212,126,0.08); border: 1px solid rgba(0,212,126,0.3); color: #00d47e; }}
        .fastest-banner .val {{ color: #e8e8f0; }}
        .fastest-banner .lbl {{ color: #888; font-size: 0.75rem; margin-right: 4px; }}
        
        .tower-box {{ width: 100%; height: 600px; background: #13131a; border-radius: 6px; border: 1px solid #2a2a38; overflow-y: auto; overflow-x: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.2); }}
        .tower-box::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        .tower-box::-webkit-scrollbar-track {{ background: #13131a; }}
        .tower-box::-webkit-scrollbar-thumb {{ background: #2a2a38; border-radius: 4px; }}
        .tower-box::-webkit-scrollbar-thumb:hover {{ background: #555568; }}
      </style>
    </head>
    <body>

      <div class="deck">
        <button id="playBtn" class="btn">▶ PLAY</button>
        <button id="resetBtn" class="btn" style="background:#2a2a38; min-width:80px;">⏮</button>
        <select id="speedSel">
          <option value="900">0.5x Speed</option>
          <option value="450" selected>1.0x Speed</option>
          <option value="200">2.0x Speed</option>
          <option value="50">4.0x Speed</option>
        </select>
        <input type="range" id="slider" min="1" max="100" value="1">
      </div>

      <div class="dash">
        <div class="lap-tag">{lbl_tag} <span id="lapNum" style="color:#e8002d">1</span><span style="color:#555568" id="lapMax">/100</span></div>
        <div class="prog-bg"><div id="progFill" class="prog-fill" style="width: 0%;"></div></div>
        <div class="stats">
          <span id="stGlobal" style="font-weight:700">● Clear</span>
          <span id="stAir" style="color:#888">🌡️ Air --</span>
          <span id="stTrk" style="color:#888">⬛ Trk --</span>
          <span id="stRain" style="color:#888">☀️ Dry</span>
        </div>
      </div>

      <div id="warnBox" class="warn">⚠️ Local Yellow</div>

      <div class="banners">
        <div id="fastOvr" class="fastest-banner"></div>
        <div id="fastCur" class="fastest-banner current"></div>
      </div>

      <div class="tower-box"><div id="towerBody"></div></div>

      <script>
        const R = {json_data};
        let currentLap = 1;
        let playing = false;
        let timer = null;

        document.getElementById('slider').max = R.maxLaps;
        document.getElementById('lapMax').innerText = '/' + R.maxLaps;

        function renderLap(lap) {{
            const f = R.frames[lap];
            if(!f) return;
            
            document.getElementById('lapNum').innerText = lap;
            document.getElementById('slider').value = lap;
            document.getElementById('progFill').style.width = ((lap / R.maxLaps) * 100) + '%';
            document.getElementById('towerBody').innerHTML = f.tower;
            
            const st = f.stat || {{}};
            const gc = st.global === 'Clear' ? '#00d47e' : (st.global === 'Red Flag' ? '#e8002d' : '#ffd700');
            const gi = st.global === 'Clear' ? '●' : (st.global === 'Red Flag' ? '✖' : '▲');
            document.getElementById('stGlobal').innerHTML = `<span style="color:${{gc}}">${{gi}} ${{st.global || "Clear"}}</span>`;
            document.getElementById('stAir').innerText = '🌡️ Air ' + (st.air || "—");
            document.getElementById('stTrk').innerText = '⬛ Trk ' + (st.trk || "—");
            document.getElementById('stRain').innerText = st.rain ? '🌧️ Rain' : '☀️ Dry';

            if(st.s1 || st.s2 || st.s3) {{
                let y = [];
                if(st.s1) y.push("S1 🟡"); if(st.s2) y.push("S2 🟡"); if(st.s3) y.push("S3 🟡");
                document.getElementById('warnBox').innerText = "⚠️ Local Yellow — " + y.join(" · ");
                document.getElementById('warnBox').style.display = "block";
            }} else {{
                document.getElementById('warnBox').style.display = "none";
            }}

            const bOvr = document.getElementById('fastOvr');
            if (f.fast_ovr) {{
                bOvr.innerHTML = `<div>⚡ FASTEST (OVERALL) &nbsp;&nbsp; <span style="color:#fff">${{f.fast_ovr.drv}}</span> &nbsp; <span class="val">${{f.fast_ovr.lap}}</span> <span style="color:#555568;font-size:0.75rem">(L${{f.fast_ovr.num}})</span></div> <div><span class="lbl">S1</span> <span class="val">${{f.fast_ovr.s1}}</span> &nbsp; <span class="lbl">S2</span> <span class="val">${{f.fast_ovr.s2}}</span> &nbsp; <span class="lbl">S3</span> <span class="val">${{f.fast_ovr.s3}}</span></div>`;
                bOvr.style.display = 'flex';
            }} else {{ bOvr.style.display = 'none'; }}

            const bCur = document.getElementById('fastCur');
            if (f.fast_cur) {{
                bCur.innerHTML = `<div>⏱ FASTEST (THIS LAP) &nbsp;&nbsp; <span style="color:#fff">${{f.fast_cur.drv}}</span> &nbsp; <span class="val">${{f.fast_cur.lap}}</span></div> <div><span class="lbl">S1</span> <span class="val">${{f.fast_cur.s1}}</span> &nbsp; <span class="lbl">S2</span> <span class="val">${{f.fast_cur.s2}}</span> &nbsp; <span class="lbl">S3</span> <span class="val">${{f.fast_cur.s3}}</span></div>`;
                bCur.style.display = 'flex';
            }} else {{ bCur.style.display = 'none'; }}
        }}

        function step() {{
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
        document.getElementById('resetBtn').onclick = () => {{ togglePlay(false); currentLap = 1; renderLap(1); }};
        document.getElementById('slider').oninput = (e) => {{ togglePlay(false); currentLap = parseInt(e.target.value); renderLap(currentLap); }};
        document.getElementById('speedSel').onchange = () => {{ if(playing) {{ togglePlay(false); togglePlay(true); }} }};

        renderLap(1); 
      </script>
    </body>
    </html>
    """
    components.html(engine_html, height=800, scrolling=False)


# ══════════════════════════════════════════════════════════════
#  STEP 4 — STATIC CLASSIFICATION (Pre-2018 Safe)
# ══════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False, ttl=3600)
def load_static_results(year, race, session_id):
    try:
        session = fastf1.get_session(year, race, session_id)
        # Force telemetry=False for absolute safety on historic races
        session.load(telemetry=False, weather=False, messages=False)
        return session.results, None
    except Exception as e:
        return None, str(e)

def render_static_classification(year, race, session_id):
    with st.spinner("Loading session classification..."):
        results, err = load_static_results(year, race, session_id)
        
    if err or results is None or results.empty:
        no_data_error(err or "Failed to load classification data.")
        return
        
    df = results.copy()
    
    # Pre-2018 Fallbacks for missing columns
    if "Abbreviation" in df.columns:
        df = df.rename(columns={"Abbreviation": "Driver"})
    elif "LastName" in df.columns:
        df = df.rename(columns={"LastName": "Driver"})
        
    if "TeamName" in df.columns:
        df = df.rename(columns={"TeamName": "Team"})
    
    # ── BUG FIX 1: Strip duplicate columns ──
    df = df.loc[:, ~df.columns.duplicated()].copy()
    
    # Ensure position is a whole number
    if 'Position' in df.columns:
        df['Position'] = pd.to_numeric(df['Position'], errors='coerce').fillna(999).astype(int)
        df = df.sort_values('Position')
        df['Position'] = df['Position'].apply(lambda x: str(x) if x != 999 else "NC")
    else:
        df['Position'] = "NC"
        
    cols = ["Position", "Driver", "Team"]
    
    if session_id.upper() in ["Q", "Q1", "Q2", "Q3", "SQ"]:
        for q in ["Q1", "Q2", "Q3"]:
            if q in df.columns:
                df[q] = df[q].apply(_fmt_split, is_lap=True)
                cols.append(q)
    else:
        # Custom Race Time formatting
        def format_race_time(row):
            val = row.get("Time")
            if pd.notna(val) and isinstance(val, pd.Timedelta):
                return _fmt_race_time(val)
            return str(row.get("Status", "—"))
            
        if "Time" in df.columns and "Status" in df.columns:
            df["Total Time / Gap"] = df.apply(format_race_time, axis=1)
            cols.append("Total Time / Gap")
        elif "Time" in df.columns:
            df["Total Time / Gap"] = df["Time"].apply(lambda x: _fmt_race_time(x) if isinstance(x, pd.Timedelta) else str(x))
            cols.append("Total Time / Gap")
            
    df = df[[c for c in cols if c in df.columns]]
    
    # ── BUG FIX 2: Do NOT set_index on Position. This prevents the Styler Crash. ──
    df = df.reset_index(drop=True)
    
    def driver_bg(val):
        color = driver_color(val, results)
        return f'background-color: {color}20; color: {color}; font-weight: bold; border-left: 4px solid {color};'

    styler = df.style
    if 'Driver' in df.columns: 
        styler = styler.map(driver_bg, subset=['Driver'])
        
    # UI Layout with Export Button
    col1, col2 = st.columns([0.8, 0.2])
    with col1:
        st.markdown('<div class="pw-section-label" style="margin-top:10px;">Final Classification</div>', unsafe_allow_html=True)
    with col2:
        st.download_button(
            label="⬇️ Export to CSV",
            data=df.to_csv(index=False).encode('utf-8'),
            file_name=f"F1_Results_{year}_{race}_{session_id}.csv",
            mime="text/csv",
            use_container_width=True
        )
            
    st.dataframe(styler, use_container_width=True, height=750)


# ══════════════════════════════════════════════════════════════
#  PUBLIC ENTRY POINT (The Unified Hub)
# ══════════════════════════════════════════════════════════════

def render_replay(year, race, session_id, session_name):
    section_header("SESSION DASHBOARD", f"{year} {race}  ·  {session_name}")

    # ── HISTORICAL ARCHIVE ROUTER (Pre-2018 Fix) ──
    if int(year) < 2018:
        st.info(f"🏛️ **Historical Archive:** High-density telemetry animation is unavailable for the {year} season. Displaying official static classification.")
        render_static_classification(year, race, session_id)
        return

    if session_id.upper() in ["R", "S"]:
        load_ph = st.empty()
        with load_ph.container():
            st.markdown("""
            <div style="background:#13131a;border:1px solid #2a2a38;border-radius:6px;padding:20px 24px">
              <div style="font-size:.7rem;letter-spacing:.2em;color:#e8002d;text-transform:uppercase;margin-bottom:12px">Loading High-Density Telemetry</div>
              <div style="color:#888;font-size:.85rem;line-height:1.7">• Parsing lap arrays, speeds & sector splits<br>• Extracting continuous OT trace statuses<br>• Compiling zero-latency animation payload</div>
            </div>""", unsafe_allow_html=True)

            with st.spinner("Baking Telemetry Splits… (Takes ~10s for full race aggregation)"):
                frames, max_laps, results, err = precalculate_race_data(year, race, session_id)

            if err or not frames:
                no_data_error(err or "Failed to compile replay frames. Try a different session.")
                return

        load_ph.empty()
        render_js_player(frames, max_laps, results, is_quali=False)

    else:
        # QUALIFYING TIMELINE ROUTER
        load_ph = st.empty()
        with load_ph.container():
            st.markdown("""
            <div style="background:#13131a;border:1px solid #2a2a38;border-radius:6px;padding:20px 24px">
              <div style="font-size:.7rem;letter-spacing:.2em;color:#e8002d;text-transform:uppercase;margin-bottom:12px">Loading Qualifying Timeline</div>
              <div style="color:#888;font-size:.85rem;line-height:1.7">• Analyzing chronological track evolution<br>• Dynamically identifying Q1, Q2, Q3 breaks<br>• Compiling zero-latency animation payload</div>
            </div>""", unsafe_allow_html=True)

            with st.spinner("Baking Timeline Splits…"):
                payload_dict, results, err = precalculate_quali_data(year, race, session_id)

            if err or not payload_dict:
                no_data_error(err or "Failed to compile qualifying frames.")
                return
        load_ph.empty()

        phase_sel = st.selectbox("Select Session Segment", list(payload_dict.keys()), index=0)
        
        selected_frames = payload_dict[phase_sel]["frames"]
        max_events = payload_dict[phase_sel]["max_events"]
        
        if max_events > 0:
            render_js_player(selected_frames, max_events, results, is_quali=True)
        else:
            st.warning("No timed laps recorded in this session segment.")

    # Render Classification independently of race vs quali logic
    render_static_classification(year, race, session_id)