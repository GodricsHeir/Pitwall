"""
strategy.py — Race Strategy & Stint Overview for PitWall Analytics
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from utils import (
    safe_load_session, apply_tyre_labels, extract_pit_map, format_time,
    TYRE_COLORS, PLOTLY_THEME, section_header, no_data_error, driver_color
)

def render_strategy(year, race, session_id, session_name):
    section_header("STRATEGY BOARD", f"{year} {race}  ·  {session_name}")

    # ── 1. LOAD ──────────────────────────────────────────
    session, laps, err = safe_load_session(year, race, session_id)
    if err:
        no_data_error(err)
        return

    results = getattr(session, 'results', pd.DataFrame())

    laps['Stint'] = laps['Stint'].fillna(0).astype(int)
    clean = apply_tyre_labels(laps)
    pit_map = extract_pit_map(laps)

    # ── 2. TYRE STRATEGY GANTT CHART ─────────────────────
    st.markdown("#### Grid Tyre Strategy & Stint Lengths")
    
    stints = (clean.groupby(['Driver', 'Stint', 'Tyre'])
              .agg(Start_Lap=('LapNumber', 'min'),
                   End_Lap=('LapNumber', 'max'),
                   Laps_Driven=('LapNumber', 'count'))
              .reset_index())

    try:
        finish_order = results.sort_values('Position')['Abbreviation'].dropna().tolist()
        finish_order.reverse() 
    except Exception:
        finish_order = sorted(stints['Driver'].unique())

    fig = px.bar(
        stints, y="Driver", x="Laps_Driven", base="Start_Lap",
        color="Tyre", color_discrete_map=TYRE_COLORS, orientation='h',
        hover_data={'Driver': True, 'Tyre': True, 'Stint': True, 'Start_Lap': True, 'End_Lap': True, 'Laps_Driven': False},
        labels={'Laps_Driven': 'Stint Length', 'Start_Lap': 'Lap Pit In', 'End_Lap': 'Lap Pit Out'}
    )

    fig.update_layout(
        **PLOTLY_THEME, height=700,
        xaxis_title="Lap Number", yaxis_title="Driver", barmode='overlay' 
    )
    fig.update_yaxes(categoryorder='array', categoryarray=finish_order)
    st.plotly_chart(fig, use_container_width=True)

    # ── 3. UNDERCUT / OVERCUT ANALYZER ───────────────────
    st.divider()
    section_header("UNDERCUT / OVERCUT", "Direct Pit Sequence Analyzer")
    
    # Call the isolated fragment
    _render_analyzer_fragment(clean, pit_map, results)


# ── HELPER: AUTO-FIND MAX GAINER ─────────────────────────
def _find_max_gainer(clean, pit_map, d1, mode="absolute"):
    best_d = None
    best_l = None
    max_g = -999
    similar_cars_count = 0
    
    d1_pure = clean[(clean['Driver'] == d1) & pd.isna(clean['PitInTime']) & pd.isna(clean['PitOutTime'])]
    d1_pace = d1_pure['LapTime_s'].mean() if not d1_pure.empty else None
    
    for _, row in pit_map.iterrows():
        drv = row['Driver']
        if drv == d1:
            continue
            
        in_lap = int(row['Pit Lap'])
        drv_laps = clean[clean['Driver'] == drv]
        
        if mode == "similar" and d1_pace is not None:
            drv_pure = drv_laps[pd.isna(drv_laps['PitInTime']) & pd.isna(drv_laps['PitOutTime'])]
            drv_pace = drv_pure['LapTime_s'].mean() if not drv_pure.empty else None
            
            if drv_pace is None or abs(drv_pace - d1_pace) > 1.0:
                continue 
            similar_cars_count += 1
        
        pb_arr = drv_laps[drv_laps['LapNumber'] == in_lap - 1]['Position'].values
        if len(pb_arr) == 0 or pd.isna(pb_arr[0]): continue
        p_before = int(pb_arr[0])
        
        end_lap = drv_laps['LapNumber'].max()
        pe_arr = drv_laps[drv_laps['LapNumber'] == end_lap]['Position'].values
        if len(pe_arr) == 0 or pd.isna(pe_arr[0]): continue
        p_end = int(pe_arr[0])
        
        gain = p_before - p_end
        if gain > max_g:
            max_g = gain
            best_d = drv
            best_l = in_lap
            
    return best_d, best_l, max_g, similar_cars_count


# ── ISOLATED UI FRAGMENT (Prevents full-page reloads) ────
@st.fragment
def _render_analyzer_fragment(clean, pit_map, results):
    available_drivers = sorted(clean['Driver'].dropna().unique())
    if len(available_drivers) < 2:
        st.info("Not enough driver data to run pit comparisons.")
        return

    # ── CLEAN UI LAYOUT ──
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("##### 1. Select Base Driver (Driver A)")
        d1 = st.selectbox("Driver A", available_drivers, index=0, label_visibility="collapsed", key="d1_drv")
        d1_pits = pit_map[pit_map['Driver'] == d1].copy()
        
        if d1_pits.empty:
            st.warning(f"{d1} did not record any pit stops.")
            d1_lap = None
        else:
            d1_pit_options = {f"Pit {i+1} (Lap {int(row['Pit Lap'])})": int(row['Pit Lap']) for i, row in d1_pits.iterrows()}
            d1_target = st.selectbox(f"{d1} Pit Stop", list(d1_pit_options.keys()), key="d1_pit")
            d1_lap = d1_pit_options[d1_target]

    with col2:
        st.markdown("##### 2. Select Opponent (Driver B)")
        auto_match = st.toggle("⚡ Auto-Match: Max Gainer", help="Automatically finds the driver who gained the most overall race positions from a pit cycle.")
        
        if auto_match:
            match_mode = st.radio("Opponent Filtering:", ["Absolute Max Gainer (Entire Grid)", "Similar Pace Max Gainer"], horizontal=True)
            mode_val = "similar" if "Similar" in match_mode else "absolute"
            
            d2_auto, d2_lap_auto, max_gain, sim_count = _find_max_gainer(clean, pit_map, d1, mode=mode_val)
            
            if d2_auto and max_gain > 0:
                bracket_str = "within 1.0s pace delta" if mode_val == "similar" else "on the grid"
                st.success(f"**Auto-Matched:** {d2_auto} • Gained **{max_gain}** overall positions (Best {bracket_str}).")
                
                d2 = d2_auto
                d2_pits = pit_map[pit_map['Driver'] == d2].copy()
                d2_pit_options = {f"Pit {i+1} (Lap {int(row['Pit Lap'])})": int(row['Pit Lap']) for i, row in d2_pits.iterrows()}
                
                try:
                    default_idx = list(d2_pit_options.values()).index(d2_lap_auto)
                except ValueError:
                    default_idx = 0
                    
                d2_target = st.selectbox(f"Explore {d2}'s Pit Stops", list(d2_pit_options.keys()), index=default_idx, key="d2_auto_pit")
                d2_lap = d2_pit_options[d2_target]
                
            else:
                if mode_val == "similar":
                    if sim_count == 0:
                        st.warning(f"No other drivers had a pure race pace within 1.0s of {d1}.")
                    else:
                        st.warning(f"None of the {sim_count} drivers with similar pace to {d1} gained any overall positions from their pit cycles.")
                else:
                    st.warning("No driver on the entire grid gained overall track position from their pit cycles in this session.")
                    
                d2, d2_lap = None, None
        else:
            d2 = st.selectbox("Driver B", available_drivers, index=1, label_visibility="collapsed", key="d2_drv")
            d2_pits = pit_map[pit_map['Driver'] == d2].copy()
            if d2_pits.empty:
                st.warning(f"{d2} did not record any pit stops.")
                d2_lap = None
            else:
                d2_pit_options = {f"Pit {i+1} (Lap {int(row['Pit Lap'])})": int(row['Pit Lap']) for i, row in d2_pits.iterrows()}
                
                closest_pit_idx = 0
                if not d1_pits.empty and d1_lap is not None:
                    d2_pit_laps = d2_pits['Pit Lap'].values
                    closest_pit_idx = int(abs(d2_pit_laps - d1_lap).argmin()) if len(d2_pit_laps) > 0 else 0
                    
                d2_target = st.selectbox(f"{d2} Pit Stop", list(d2_pit_options.keys()), index=closest_pit_idx, key="d2_pit")
                d2_lap = d2_pit_options[d2_target]

    st.markdown("<br>", unsafe_allow_html=True)

    if d1_pits.empty or not d2 or d2_lap is None or d1_lap is None:
        return

    # Helper: Extract Pit Sequence Metrics
    def get_pit_metrics(driver, in_lap_num):
        drv_laps = clean[clean['Driver'] == driver]
        
        try:
            in_lap = drv_laps[drv_laps['LapNumber'] == in_lap_num].iloc[0]
            out_lap = drv_laps[drv_laps['LapNumber'] == in_lap_num + 1].iloc[0]
            new_stint_num = out_lap['Stint']
            
            # ── TRACK STATUS (SC / VSC / FLAGS) ──
            status_str = str(in_lap.get('TrackStatus', '1')) + str(out_lap.get('TrackStatus', '1'))
            incident_tags = []
            if '4' in status_str: incident_tags.append("Safety Car (SC)")
            if '6' in status_str or '7' in status_str: incident_tags.append("Virtual Safety Car (VSC)")
            if '5' in status_str: incident_tags.append("Red Flag")
            if '2' in status_str and not ('4' in status_str or '6' in status_str): incident_tags.append("Yellow Flag")
            
            # De-duplicate tags
            incident_tags = list(dict.fromkeys(incident_tags))
            
            pos_before = drv_laps[drv_laps['LapNumber'] == in_lap_num - 1]['Position'].values
            p_before = int(pos_before[0]) if len(pos_before) > 0 and pd.notna(pos_before[0]) else "NC"

            pos_after = drv_laps[drv_laps['LapNumber'] == in_lap_num + 2]['Position'].values
            p_after = int(pos_after[0]) if len(pos_after) > 0 and pd.notna(pos_after[0]) else "NC"
            
            stint_laps = drv_laps[drv_laps['Stint'] == new_stint_num]
            if not stint_laps.empty:
                stint_end_lap = stint_laps['LapNumber'].max()
                pos_stint_end = stint_laps[stint_laps['LapNumber'] == stint_end_lap]['Position'].values
                p_stint_end = int(pos_stint_end[0]) if len(pos_stint_end) > 0 and pd.notna(pos_stint_end[0]) else "NC"
            else:
                stint_end_lap, p_stint_end = "N/A", "NC"
                
            race_end_lap = drv_laps['LapNumber'].max()
            pos_race_end = drv_laps[drv_laps['LapNumber'] == race_end_lap]['Position'].values
            p_race_end = int(pos_race_end[0]) if len(pos_race_end) > 0 and pd.notna(pos_race_end[0]) else "NC"
            
            in_time = in_lap['LapTime_s']
            out_time = out_lap['LapTime_s']
            total_time = in_time + out_time
            
            return {
                'driver': driver, 'in_time': in_time, 'out_time': out_time, 'total': total_time,
                'p_before': p_before, 'p_after': p_after, 'p_stint_end': p_stint_end, 'p_race_end': p_race_end,
                'stint_end_lap': stint_end_lap, 'race_end_lap': race_end_lap,
                'tyre_old': in_lap['Tyre'], 'tyre_new': out_lap['Tyre'],
                'incident_tags': incident_tags
            }
        except Exception:
            return None

    with st.spinner("Analyzing pit cycles..."):
        m1 = get_pit_metrics(d1, d1_lap)
        m2 = get_pit_metrics(d2, d2_lap)

    if not m1 or not m2:
        st.error("Incomplete lap data around the selected pit stops.")
        return

    # ── RENDER BATTLE METRICS ──
    st.markdown("##### 3. Track Position Analytics")
    
    diff = m1['total'] - m2['total']
    winner = d1 if diff < 0 else d2
    loser = d2 if diff < 0 else d1
    abs_diff = abs(diff)

    def render_pos_metrics(m):
        def get_delta(before, after):
            if isinstance(before, int) and isinstance(after, int):
                net = before - after
                if net > 0: return f"↑ Gained {net}", "normal"
                elif net < 0: return f"↓ Lost {abs(net)}", "inverse"
                else: return "Held Position", "off"
            return "", "off"
            
        st.markdown(f"**{m['driver']} ({m['tyre_old']} ➔ {m['tyre_new']})**")
        
        # ── INCIDENT INJECTION HERE ──
        if m['incident_tags']:
            st.warning(f"⚠️ Pitted under: **{' / '.join(m['incident_tags'])}**")
        
        a_str, a_col = get_delta(m['p_before'], m['p_after'])
        st.metric("Immediate Pit Delta", f"P{m['p_before']} ➔ P{m['p_after']}", a_str, delta_color=a_col)
        
        s_str, s_col = get_delta(m['p_before'], m['p_stint_end'])
        st.metric(f"Stint End Delta (Lap {m['stint_end_lap']})", f"P{m['p_before']} ➔ P{m['p_stint_end']}", s_str, delta_color=s_col)
        
        r_str, r_col = get_delta(m['p_before'], m['p_race_end'])
        st.metric(f"Race Finish Delta (Lap {m['race_end_lap']})", f"P{m['p_before']} ➔ P{m['p_race_end']}", r_str, delta_color=r_col)

    c1, c2, c3 = st.columns(3)
    
    with c1: render_pos_metrics(m1)
    with c2: render_pos_metrics(m2)
        
    with c3:
        st.markdown(f"**{d1} vs {d2} Verdict**")
        
        # Alert if comparing SC to Green Flag
        if bool(m1['incident_tags']) != bool(m2['incident_tags']):
            st.error("🚨 **Unequal Track Conditions!** One driver pitted under an incident, drastically reducing their pit lane time loss. Direct time comparisons are skewed.")
            
        st.success(f"**{winner}** executed a faster pit sequence by **{abs_diff:.3f}s**.")
        st.metric("Total Sequence Time", format_time(m1['total']), f"{diff:.3f}s", delta_color="inverse")
        
        in_diff = m1['in_time'] - m2['in_time']
        out_diff = m1['out_time'] - m2['out_time']
        st.caption(f"**In-Lap Phase:** {d1} was {'faster' if in_diff < 0 else 'slower'} by {abs(in_diff):.3f}s")
        st.caption(f"**Out-Lap Phase:** {d1} was {'faster' if out_diff < 0 else 'slower'} by {abs(out_diff):.3f}s")

    # ── TIME LOSS BREAKDOWN CHART ──
    fig_bar = go.Figure()
    
    color1 = driver_color(d1, results)
    color2 = driver_color(d2, results)

    fig_bar.add_trace(go.Bar(
        name=d1, x=['In-Lap Time', 'Out-Lap Time (inc. Pit)'], y=[m1['in_time'], m1['out_time']],
        marker_color=color1, text=[format_time(m1['in_time']), format_time(m1['out_time'])], textposition='auto'
    ))
    
    fig_bar.add_trace(go.Bar(
        name=d2, x=['In-Lap Time', 'Out-Lap Time (inc. Pit)'], y=[m2['in_time'], m2['out_time']],
        marker_color=color2, text=[format_time(m2['in_time']), format_time(m2['out_time'])], textposition='auto'
    ))

    fig_bar.update_layout(
        **PLOTLY_THEME, height=450, title="Phase Breakdown: Where was the time won?",
        barmode='group', yaxis_title="Time (seconds)",
        hovermode="x unified"
    )
    
    st.plotly_chart(fig_bar, use_container_width=True)