"""
strategy.py — Race Strategy & Stint Overview for PitWall Analytics
"""
import streamlit as st
import pandas as pd
import fastf1
import plotly.express as px
import plotly.graph_objects as go

from utils import (
    safe_load_session, apply_tyre_labels, extract_pit_map, format_time,
    TYRE_COLORS, PLOTLY_THEME, section_header, no_data_error
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


# ─────────────────────────────────────────────────────────────
#  HISTORICAL CIRCUIT RISK PROFILE ENGINE (SESSION-SPECIFIC)
# ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=86400 * 7)
def _get_circuit_risk_profile(current_year, event_name, session_name):
    """
    Scrapes from 2018 up to the current year for THIS SPECIFIC SESSION TYPE.
    Uses absolute TrackStatus codes (1=Clear, 2=Yellow, 4=SC, 5=Red, 6=VSC) 
    instead of text matching for 100% precision. Logs years and specific counts.
    """
    stats = {
        'All': {'total': 0, 'SC_sess': 0, 'VSC_sess': 0, 'Red_sess': 0, 'Yellow_sess': 0, 'SC_count': 0, 'VSC_count': 0, 'Red_count': 0, 'Yellow_count': 0, 'SC_years': {}, 'VSC_years': {}, 'Red_years': {}, 'Yellow_years': {}},
        'Dry': {'total': 0, 'SC_sess': 0, 'VSC_sess': 0, 'Red_sess': 0, 'Yellow_sess': 0, 'SC_count': 0, 'VSC_count': 0, 'Red_count': 0, 'Yellow_count': 0, 'SC_years': {}, 'VSC_years': {}, 'Red_years': {}, 'Yellow_years': {}},
        'Wet': {'total': 0, 'SC_sess': 0, 'VSC_sess': 0, 'Red_sess': 0, 'Yellow_sess': 0, 'SC_count': 0, 'VSC_count': 0, 'Red_count': 0, 'Yellow_count': 0, 'SC_years': {}, 'VSC_years': {}, 'Red_years': {}, 'Yellow_years': {}}
    }
    
    try: current_year = int(current_year)
    except: return stats
    
    for y in range(2018, current_year + 1):
        try:
            ev = fastf1.get_event(y, event_name)
            schedule = fastf1.get_event_schedule(y)
            
            if ev.EventName not in schedule['EventName'].values:
                continue
                
            try:
                session = ev.get_session(session_name)
                session.load(telemetry=False, weather=True, messages=True)
                
                is_wet = False
                if not session.weather_data.empty and 'Rainfall' in session.weather_data.columns:
                    if session.weather_data['Rainfall'].sum() > 0:
                        is_wet = True
                
                w_key = 'Wet' if is_wet else 'Dry'
                
                # Fetch absolute end time to filter out post-race administrative flags
                limit_time = pd.Timedelta(days=999) 
                if session.session_status is not None and not session.session_status.empty:
                    finished_rows = session.session_status[session.session_status['Status'].str.upper() == 'FINISHED']
                    if not finished_rows.empty:
                        limit_time = finished_rows['Time'].iloc[0]

                ts = session.track_status
                if ts is not None and not ts.empty:
                    valid_ts = ts[ts['Time'] <= limit_time]
                    codes = valid_ts['Status'].astype(str).tolist()
                    
                    sc_instances = codes.count('4')
                    vsc_instances = codes.count('6')
                    red_instances = codes.count('5')
                    yellow_instances = codes.count('2')
                    
                    # Register session
                    stats['All']['total'] += 1
                    stats[w_key]['total'] += 1
                    
                    for k in ['All', w_key]:
                        stats[k]['SC_count'] += sc_instances
                        stats[k]['VSC_count'] += vsc_instances
                        stats[k]['Red_count'] += red_instances
                        stats[k]['Yellow_count'] += yellow_instances
                        
                        if sc_instances > 0: 
                            stats[k]['SC_sess'] += 1
                            stats[k]['SC_years'][y] = sc_instances
                        if vsc_instances > 0: 
                            stats[k]['VSC_sess'] += 1
                            stats[k]['VSC_years'][y] = vsc_instances
                        if red_instances > 0: 
                            stats[k]['Red_sess'] += 1
                            stats[k]['Red_years'][y] = red_instances
                        if yellow_instances > 0: 
                            stats[k]['Yellow_sess'] += 1
                            stats[k]['Yellow_years'][y] = yellow_instances
                        
            except Exception:
                continue 
        except Exception:
            continue 
            
    return stats


def _render_risk_ui(year, race, session_name):
    st.markdown(f'<div class="pw-section-label">Historical Circuit Risk Profile ({session_name.upper()} SESSIONS ONLY)</div>', unsafe_allow_html=True)
    
    with st.spinner(f"Aggregating historical {session_name} data for this circuit (From 2018 to {year})..."):
        stats = _get_circuit_risk_profile(year, race, session_name)
        
    if stats['All']['total'] == 0:
        st.info(f"No historical {session_name} data available for this circuit since 2018.")
        return
        
    tab1, tab2, tab3 = st.tabs(["Combined (All Conditions)", "Dry Sessions", "Wet/Mixed Sessions"])
    
    def render_tab_content(data_dict):
        t = data_dict['total']
        if t == 0: 
            st.markdown("<div style='color:#888; font-style:italic; padding: 20px 0;'>No sessions recorded for these conditions.</div>", unsafe_allow_html=True)
            return
        
        sc_s, sc_c = data_dict['SC_sess'], data_dict['SC_count']
        vsc_s, vsc_c = data_dict['VSC_sess'], data_dict['VSC_count']
        red_s, red_c = data_dict['Red_sess'], data_dict['Red_count']
        y_s, y_c = data_dict['Yellow_sess'], data_dict['Yellow_count']
        
        col_y = "#FFEA00"
        col_vsc = "#FFBA08"
        col_sc = "#FF8F00"
        col_red = "#E8002D"
        
        # 1. Metric Display Cards (Probability of presence)
        st.markdown(f"""
        <div style="display:flex; gap:12px; margin-top: 10px; margin-bottom: 25px;">
           <div style="flex:1; background:rgba(255,234,0,0.02); border:1px solid rgba(255,234,0,0.15); border-top: 3px solid {col_y}; border-radius:6px; padding:15px 10px; text-align:center;">
              <div style="color:{col_y}; font-size:1.6rem; font-weight:800; font-family:'JetBrains Mono', monospace;">{(y_s/t)*100:.1f}% <span style="font-size:0.9rem; color:#666;">({y_s}/{t})</span></div>
              <div style="color:#888; font-size:0.7rem; letter-spacing:0.1em; text-transform:uppercase; margin-top:6px; font-weight:600;">Yellow Flag Chance</div>
           </div>
           <div style="flex:1; background:rgba(255,186,8,0.02); border:1px solid rgba(255,186,8,0.15); border-top: 3px solid {col_vsc}; border-radius:6px; padding:15px 10px; text-align:center;">
              <div style="color:{col_vsc}; font-size:1.6rem; font-weight:800; font-family:'JetBrains Mono', monospace;">{(vsc_s/t)*100:.1f}% <span style="font-size:0.9rem; color:#666;">({vsc_s}/{t})</span></div>
              <div style="color:#888; font-size:0.7rem; letter-spacing:0.1em; text-transform:uppercase; margin-top:6px; font-weight:600;">VSC Probability</div>
           </div>
           <div style="flex:1; background:rgba(255,143,0,0.02); border:1px solid rgba(255,143,0,0.15); border-top: 3px solid {col_sc}; border-radius:6px; padding:15px 10px; text-align:center;">
              <div style="color:{col_sc}; font-size:1.6rem; font-weight:800; font-family:'JetBrains Mono', monospace;">{(sc_s/t)*100:.1f}% <span style="font-size:0.9rem; color:#666;">({sc_s}/{t})</span></div>
              <div style="color:#888; font-size:0.7rem; letter-spacing:0.1em; text-transform:uppercase; margin-top:6px; font-weight:600;">Safety Car Chance</div>
           </div>
           <div style="flex:1; background:rgba(232,0,45,0.02); border:1px solid rgba(232,0,45,0.15); border-top: 3px solid {col_red}; border-radius:6px; padding:15px 10px; text-align:center;">
              <div style="color:{col_red}; font-size:1.6rem; font-weight:800; font-family:'JetBrains Mono', monospace;">{(red_s/t)*100:.1f}% <span style="font-size:0.9rem; color:#666;">({red_s}/{t})</span></div>
              <div style="color:#888; font-size:0.7rem; letter-spacing:0.1em; text-transform:uppercase; margin-top:6px; font-weight:600;">Red Flag Chance</div>
           </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Helper to format year strings for hover tooltip
        def format_years(years_dict):
            if not years_dict: return "None"
            return ", ".join([f"{yr} ({cnt})" for yr, cnt in sorted(years_dict.items(), reverse=True)])
            
        hover_texts = [
            f"<b>Yellow Flags</b><br>Years: {format_years(data_dict['Yellow_years'])}",
            f"<b>Virtual Safety Cars</b><br>Years: {format_years(data_dict['VSC_years'])}",
            f"<b>Safety Cars</b><br>Years: {format_years(data_dict['SC_years'])}",
            f"<b>Red Flags</b><br>Years: {format_years(data_dict['Red_years'])}"
        ]
        
        # 2. Volume Infographic (Average counts per session)
        categories = ['Yellow Flags', 'VSCs', 'Safety Cars', 'Red Flags']
        colored_cats = [
            f"<span style='color:{col_y}; font-weight:700;'>Yellow Flags</span>",
            f"<span style='color:{col_vsc}; font-weight:700;'>VSCs</span>",
            f"<span style='color:{col_sc}; font-weight:700;'>Safety Cars</span>",
            f"<span style='color:{col_red}; font-weight:700;'>Red Flags</span>"
        ]
        averages = [y_c / t, vsc_c / t, sc_c / t, red_c / t]
        colors = [col_y, col_vsc, col_sc, col_red]
        
        fig_avg = go.Figure(go.Bar(
            x=averages, y=categories, orientation='h',
            marker=dict(color=colors, line=dict(color='rgba(255,255,255,0.1)', width=1)),
            text=[f"{val:.2f}" for val in averages], 
            textposition='outside',
            textfont=dict(family="JetBrains Mono", size=12, color="white"),
            cliponaxis=False,
            customdata=hover_texts,
            hovertemplate="%{customdata}<extra></extra>"
        ))
        
        fig_avg.update_layout(
            **PLOTLY_THEME, height=240, title=dict(text="Average Incident Density Per Session", font=dict(size=13)),
            margin=dict(t=40, b=10, l=110, r=40), xaxis_title="Mean Occurrences per Session"
        )
        
        fig_avg.update_yaxes(
            tickvals=categories,
            ticktext=colored_cats
        )
        
        st.plotly_chart(fig_avg, use_container_width=True)
        st.markdown(f"<div style='color:#555568; font-size:0.75rem; text-align:right; font-family:\"JetBrains Mono\", monospace;'>BASED ON {t} HISTORICAL {session_name.upper()} SESSIONS</div>", unsafe_allow_html=True)
        
    with tab1: render_tab_content(stats['All'])
    with tab2: render_tab_content(stats['Dry'])
    with tab3: render_tab_content(stats['Wet'])


# ─────────────────────────────────────────────────────────────
#  MAIN RENDERER
# ─────────────────────────────────────────────────────────────
def render_strategy(year, race, session_id, session_name):
    section_header("STRATEGY BOARD", f"{year} {race}  ·  {session_name}")

    # ── 1. CIRCUIT RISK PROFILE ──────────────────────────
    _render_risk_ui(year, race, session_name)
    st.divider()

    # ── 2. LOAD SESSION ──────────────────────────────────
    session, laps, err = safe_load_session(year, race, session_id)
    if err:
        no_data_error(err)
        return

    results = getattr(session, 'results', pd.DataFrame())

    laps['Stint'] = laps['Stint'].fillna(0).astype(int)
    clean = apply_tyre_labels(laps)
    pit_map = extract_pit_map(laps)

    # ── 3. TYRE STRATEGY GANTT CHART ─────────────────────
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

    colored_ticks = [f"<span style='color:{get_accurate_driver_color(d, results)}; font-weight:800; font-family:\"JetBrains Mono\", monospace;'>{d}</span>" for d in finish_order]

    fig.update_layout(
        **PLOTLY_THEME, height=750,
        xaxis_title="Lap Number", yaxis_title="", barmode='overlay',
        margin=dict(l=100)
    )
    
    fig.update_yaxes(
        categoryorder='array', 
        categoryarray=finish_order,
        tickvals=finish_order,
        ticktext=colored_ticks
    )
    
    st.plotly_chart(fig, use_container_width=True)

    # ── 4. UNDERCUT / OVERCUT ANALYZER ───────────────────
    st.divider()
    section_header("UNDERCUT / OVERCUT", "Direct Pit Sequence Analyzer")
    
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
    
    color1 = get_accurate_driver_color(d1, results)
    color2 = get_accurate_driver_color(d2, results)

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