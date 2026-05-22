"""
race.py — Overall Race Results module for PitWall Analytics
"""
import streamlit as st
import pandas as pd
import numpy as np

from utils import section_header, no_data_error, format_time, driver_color

def get_safe_driver_name(row):
    """Bulletproof name coalescing that ignores literal 'nan' strings."""
    for col in ['Abbreviation', 'LastName', 'FullName', 'BroadcastName', 'TeamName']:
        val = row.get(col)
        if pd.notna(val):
            s = str(val).strip()
            # Catch Pandas string-casted nulls
            if s and s.lower() not in ['nan', 'none', 'nat', '<na>']:
                return s
    return "Unknown"

def _fmt_split(td):
    """Formats a pandas Timedelta into MM:SS.ms or SS.ms"""
    if pd.isna(td): return "—"
    if not isinstance(td, pd.Timedelta): return str(td)
    s = td.total_seconds()
    if s <= 0: return "—"
    if s >= 60:
        return f"{int(s//60)}:{s%60:06.3f}"
    return f"{s:.3f}"

def render_race_results(year, race, session_id, session_name):
    section_header("RACE RESULTS", f"{year} {race}  ·  {session_name}")
    
    with st.spinner("Loading official classification and lap data..."):
        import fastf1
        try:
            session = fastf1.get_session(year, race, session_id)
            session.load(telemetry=False, weather=False, messages=False)
            results = session.results
            try: laps = session.laps
            except Exception: laps = pd.DataFrame()
        except Exception as e:
            no_data_error(f"Failed to load session results: {e}")
            return

    if results is None or results.empty:
        no_data_error("Results not available for this session.")
        return

    # Wipe duplicate indices and columns from the raw API data
    results = results.loc[:, ~results.columns.duplicated()].reset_index(drop=True)

    is_quali = session_id.upper() in ['Q', 'SQ']

    # ══════════════════════════════════════════════════════════════
    #  A. QUALIFYING ENGINE (Segmented Tables with Sectors)
    # ══════════════════════════════════════════════════════════════
    if is_quali:
        q_cols = [c for c in ['Q1', 'Q2', 'Q3', 'SQ1', 'SQ2', 'SQ3'] if c in results.columns]
        if not q_cols:
            st.info("No detailed qualifying segments found for this specific historical session.")
            return
            
        # Extract overall session minimums for purple sector calculations
        if not laps.empty:
            overall_s1 = laps['Sector1Time'].min() if 'Sector1Time' in laps.columns else pd.NaT
            overall_s2 = laps['Sector2Time'].min() if 'Sector2Time' in laps.columns else pd.NaT
            overall_s3 = laps['Sector3Time'].min() if 'Sector3Time' in laps.columns else pd.NaT
        else:
            overall_s1 = overall_s2 = overall_s3 = pd.NaT
            
        def _get_sec_html(sec_td, o_min, p_min):
            """Generates color-coded HTML for a sector split."""
            if pd.isna(sec_td): return "—"
            try:
                val = sec_td.total_seconds()
                o_val = o_min.total_seconds() if pd.notna(o_min) else 0
                p_val = p_min.total_seconds() if pd.notna(p_min) else 0
                
                if abs(val - o_val) < 0.001 and val > 0:
                    return f"<span style='color:#df4bff; font-weight:900; background:rgba(223,75,255,0.15); padding:2px 6px; border-radius:4px;'>{val:.3f}</span>"
                elif abs(val - p_val) < 0.001 and val > 0:
                    return f"<span style='color:#00d47e; font-weight:700;'>{val:.3f}</span>"
                else:
                    return f"<span style='color:#ffd700;'>{val:.3f}</span>"
            except Exception:
                return "—"
                
        for q_col in q_cols:
            q_df = results[pd.notna(results[q_col])].copy()
            if q_df.empty: continue
            
            # Sort cleanly by the Timedelta
            q_df = q_df.sort_values(q_col).reset_index(drop=True)
            
            leader_time = q_df.iloc[0][q_col]
            prev_time = leader_time
            
            rows_html = []
            for i, (_, row) in enumerate(q_df.iterrows()):
                pos = i + 1
                drv = get_safe_driver_name(row)
                team = row.get('TeamName', 'Unknown')
                dcolor = driver_color(drv, results)
                
                t = row[q_col]
                time_str = _fmt_split(t)
                
                # Fetch matching sector data for this specific segment's lap time
                s1_html = s2_html = s3_html = "—"
                
                if not laps.empty and pd.notna(t):
                    drv_num = str(row.get('DriverNumber', ''))
                    drv_laps = pd.DataFrame()
                    if drv_num:
                        try: drv_laps = laps.pick_driver(drv_num)
                        except Exception: pass
                    if drv_laps is None or drv_laps.empty:
                        try: drv_laps = laps.pick_driver(drv)
                        except Exception: pass
                        
                    if drv_laps is not None and not drv_laps.empty:
                        pb_s1 = drv_laps['Sector1Time'].min() if 'Sector1Time' in drv_laps else pd.NaT
                        pb_s2 = drv_laps['Sector2Time'].min() if 'Sector2Time' in drv_laps else pd.NaT
                        pb_s3 = drv_laps['Sector3Time'].min() if 'Sector3Time' in drv_laps else pd.NaT
                        
                        # Match the lap time to extract specific sectors for this segment
                        matched_laps = drv_laps[drv_laps['LapTime'] == t]
                        if not matched_laps.empty:
                            matched_lap = matched_laps.iloc[0]
                            s1 = matched_lap.get('Sector1Time', pd.NaT)
                            s2 = matched_lap.get('Sector2Time', pd.NaT)
                            s3 = matched_lap.get('Sector3Time', pd.NaT)
                            
                            s1_html = _get_sec_html(s1, overall_s1, pb_s1)
                            s2_html = _get_sec_html(s2, overall_s2, pb_s2)
                            s3_html = _get_sec_html(s3, overall_s3, pb_s3)
                
                if isinstance(t, pd.Timedelta):
                    gap_l_sec = (t - leader_time).total_seconds()
                    gap_a_sec = (t - prev_time).total_seconds()
                    prev_time = t
                    
                    if gap_l_sec == 0:
                        gap_l_str = "<span style='color:#ffd700; font-weight:700;'>LEADER</span>"
                        gap_a_str = "—"
                    else:
                        gap_l_str = f"+{gap_l_sec:.3f}s"
                        gap_a_str = f"+{gap_a_sec:.3f}s"
                else:
                    gap_l_str, gap_a_str = "—", "—"
                    
                row_bg = "rgba(255,255,255,0.025)" if i % 2 == 0 else "transparent"
                
                # HTML MUST be flush left to prevent Streamlit Markdown code-block interpretation
                rows_html.append(f"""<tr style="background:{row_bg}; border-bottom:1px solid #1e1e2e;">
<td style="padding:10px 14px; color:#888; font-size:0.85rem; width:40px;">{pos}</td>
<td style="padding:10px 14px; border-left:3px solid {dcolor}; color:{dcolor}; font-weight:700; letter-spacing:0.05em;">{drv}</td>
<td style="padding:10px 14px; color:#a0a0b0; font-size:0.85rem;">{team}</td>
<td style="padding:10px 14px; font-family:'JetBrains Mono',monospace; font-size:0.85rem; color:#fff;">{time_str}</td>
<td style="padding:10px 14px; font-family:'JetBrains Mono',monospace; font-size:0.85rem; text-align:center;">{s1_html}</td>
<td style="padding:10px 14px; font-family:'JetBrains Mono',monospace; font-size:0.85rem; text-align:center;">{s2_html}</td>
<td style="padding:10px 14px; font-family:'JetBrains Mono',monospace; font-size:0.85rem; text-align:center;">{s3_html}</td>
<td style="padding:10px 14px; font-family:'JetBrains Mono',monospace; font-size:0.85rem; color:#ffd700;">{gap_l_str}</td>
<td style="padding:10px 14px; color:#a0a0b0; font-family:'JetBrains Mono',monospace; font-size:0.85rem;">{gap_a_str}</td>
</tr>""")
                
            table_html = f"""<div style="margin-top:30px; margin-bottom:10px;">
<div style="font-family:'Exo 2', sans-serif; font-size:1rem; font-weight:700; color:var(--accent2); margin-bottom:8px; text-transform:uppercase;">{q_col} CLASSIFICATION</div>
<div style="background:#13131a; border:1px solid #2a2a38; border-radius:6px; overflow-x:auto; box-shadow: 0 4px 12px rgba(0,0,0,0.2);">
<table style="width:100%; border-collapse:collapse; white-space:nowrap; text-align:left;">
<thead style="background:#0d0d0f; border-bottom:2px solid #e8002d;">
<tr>
<th style="padding:10px 14px; color:#555568; font-size:0.7rem; letter-spacing:0.15em; font-weight:600;">POS</th>
<th style="padding:10px 14px; color:#555568; font-size:0.7rem; letter-spacing:0.15em; font-weight:600;">DRIVER</th>
<th style="padding:10px 14px; color:#555568; font-size:0.7rem; letter-spacing:0.15em; font-weight:600;">TEAM</th>
<th style="padding:10px 14px; color:#555568; font-size:0.7rem; letter-spacing:0.15em; font-weight:600;">TIME</th>
<th style="padding:10px 14px; color:#555568; font-size:0.7rem; letter-spacing:0.15em; font-weight:600; text-align:center;">S1</th>
<th style="padding:10px 14px; color:#555568; font-size:0.7rem; letter-spacing:0.15em; font-weight:600; text-align:center;">S2</th>
<th style="padding:10px 14px; color:#555568; font-size:0.7rem; letter-spacing:0.15em; font-weight:600; text-align:center;">S3</th>
<th style="padding:10px 14px; color:#555568; font-size:0.7rem; letter-spacing:0.15em; font-weight:600;">GAP TO LEADER</th>
<th style="padding:10px 14px; color:#555568; font-size:0.7rem; letter-spacing:0.15em; font-weight:600;">GAP AHEAD</th>
</tr>
</thead>
<tbody>
{"".join(rows_html)}
</tbody>
</table>
</div>
</div>"""
            st.markdown(table_html, unsafe_allow_html=True)
            
        return # End of Quali Execution

    # ══════════════════════════════════════════════════════════════
    #  B. RACE / SPRINT ENGINE (Static Classification & Splits)
    # ══════════════════════════════════════════════════════════════
    
    if session_id not in ['R', 'S']:
        st.warning("Overall results with points and cumulative gaps are best viewed for full Race or Sprint sessions.")

    df = pd.DataFrame()
    df['Pos'] = pd.to_numeric(results.get('Position'), errors='coerce').astype('Int64').astype(str).replace('<NA>', 'NC')
    
    df['Driver'] = results.apply(get_safe_driver_name, axis=1)
    df['Team'] = results.get('TeamName', '')
    
    grid_pos = pd.to_numeric(results.get('GridPosition'), errors='coerce')
    fin_pos = pd.to_numeric(results.get('Position'), errors='coerce')
    pos_change = grid_pos - fin_pos
    
    def format_pos_change(val):
        if pd.isna(val) or val == 0: return "–"
        if val > 0: return f"↑ {int(val)}"
        if val < 0: return f"↓ {abs(int(val))}"
        return "–"
        
    df['Grid Δ'] = pos_change.apply(format_pos_change)
    
    race_times = []
    gaps = []
    intervals = []
    prev_gap_s = 0.0
    
    for _, row in results.iterrows():
        pos = row.get('Position', np.nan)
        time_td = row.get('Time', pd.NaT)
        status = str(row.get('Status', ''))
        
        # Modern parsing
        if pd.notna(time_td) and isinstance(time_td, pd.Timedelta) and pd.notna(pos):
            time_s = time_td.total_seconds()
            
            if pos == 1.0:
                h, r = divmod(time_s, 3600)
                m, s = divmod(r, 60)
                race_times.append(f"{int(h):02d}:{int(m):02d}:{s:06.3f}")
                gaps.append("Winner")
                intervals.append("–")
                prev_gap_s = 0.0
            else:
                gap_to_leader = time_s
                interval = gap_to_leader - prev_gap_s
                prev_gap_s = gap_to_leader
                
                race_times.append(f"+{gap_to_leader:.3f} s")
                gaps.append(f"+{gap_to_leader:.3f} s")
                intervals.append(f"+{interval:.3f} s")
        else:
            # Historical fallback: Ergast stores gaps as text in 'Status'
            if status.startswith('+'):
                race_times.append(status)
                gaps.append(status)
            else:
                race_times.append(status if status and status.lower() != 'nan' else "—")
                gaps.append(status if status and status.lower() != 'nan' else "—")
            intervals.append("–")

    df['Race Time'] = race_times
    df['Gap (Leader)'] = gaps
    df['Interval (Ahead)'] = intervals
    
    fastest_dict = {}
    fl_str = "N/A"
    
    if not laps.empty and 'LapTime' in laps.columns:
        laps['LapTime_s'] = laps['LapTime'].dt.total_seconds()
        fastest_dict = laps.groupby('Driver')['LapTime_s'].min().to_dict()
        min_fl = laps['LapTime_s'].min()
        fl_str = format_time(min_fl) if pd.notna(min_fl) else "N/A"
        
    df['Fastest Lap'] = df['Driver'].map(fastest_dict).apply(format_time)
    
    def format_points(p):
        if pd.isna(p): return "0"
        return str(int(p)) if p % 1 == 0 else str(p)
        
    df['Points'] = pd.to_numeric(results.get('Points'), errors='coerce').apply(format_points)
    
    # Guarantee a clean DataFrame before hitting the Styler
    df = df.loc[:, ~df.columns.duplicated()].reset_index(drop=True)
    
    def style_dataframe(row):
        styles = [''] * len(row)
        
        if 'Grid Δ' in df.columns:
            try:
                grid_idx = df.columns.get_loc('Grid Δ')
                grid_val = str(row.iloc[grid_idx])
                if '↑' in grid_val: styles[grid_idx] = 'color: #00d47e; font-weight: 700;'
                elif '↓' in grid_val: styles[grid_idx] = 'color: #e8002d; font-weight: 700;'
            except Exception: pass
            
        if 'Fastest Lap' in df.columns:
            try:
                fl_idx = df.columns.get_loc('Fastest Lap')
                if row.iloc[fl_idx] == fl_str and fl_str != "N/A":
                    styles[fl_idx] = 'color: #df4bff; font-weight: 900; background-color: rgba(223, 75, 255, 0.1);'
            except Exception: pass
            
        if 'Driver' in df.columns:
            try:
                drv_idx = df.columns.get_loc('Driver')
                drv_name = row.iloc[drv_idx]
                color = driver_color(drv_name, results)
                styles[drv_idx] = f'border-left: 4px solid {color}; font-weight: bold; color: {color}; background-color: {color}15;'
            except Exception: pass
                
        return styles

    styled_df = df.style.apply(style_dataframe, axis=1)
    
    col1, col2 = st.columns([0.8, 0.2])
    with col1:
        st.markdown("#### Official Classification")
    with col2:
        st.download_button(
            label="⬇️ Export to CSV",
            data=df.to_csv(index=False).encode('utf-8'),
            file_name=f"F1_Race_Results_{year}_{race}_{session_id}.csv",
            mime="text/csv",
            use_container_width=True
        )

    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    # ── 3. IDEAL LAP (THEORETICAL SESSION BEST) ──────────────
    if not laps.empty:
        st.divider()
        section_header("IDEAL LAP", "Theoretical Session Best")
        
        overall_fl = laps['LapTime'].min()
        overall_s1 = laps['Sector1Time'].min() if 'Sector1Time' in laps else pd.NaT
        overall_s2 = laps['Sector2Time'].min() if 'Sector2Time' in laps else pd.NaT
        overall_s3 = laps['Sector3Time'].min() if 'Sector3Time' in laps else pd.NaT

        def get_driver_for_sector(col_name, min_val):
            if pd.isna(min_val): return "N/A"
            try:
                return laps.loc[laps[col_name] == min_val, 'Driver'].iloc[0]
            except Exception:
                return "N/A"

        drv_s1 = get_driver_for_sector('Sector1Time', overall_s1)
        drv_s2 = get_driver_for_sector('Sector2Time', overall_s2)
        drv_s3 = get_driver_for_sector('Sector3Time', overall_s3)

        if pd.notna(overall_s1) and pd.notna(overall_s2) and pd.notna(overall_s3):
            ideal_lap_td = overall_s1 + overall_s2 + overall_s3
            ideal_str = format_time(ideal_lap_td.total_seconds())
        else:
            ideal_str = "N/A"

        def render_ideal_block(title, subtitle, color, value):
            return f"""<div style="border-left: 4px solid {color}; padding: 10px; background: rgba(255,255,255,0.03); border-radius: 4px; margin-bottom: 20px;">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
<div style="font-size: 0.7rem; color: #888; text-transform: uppercase; letter-spacing: 0.1em;">{title}</div>
<div style="font-size: 0.75rem; color: #bbb; font-weight: bold;">{subtitle}</div>
</div>
<div style="font-size: 1.4rem; font-weight: 700; color: {color}; font-family: 'JetBrains Mono', monospace;">{value}</div>
</div>"""

        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(render_ideal_block("Ideal Lap", "Combined Bests", "#df4bff", ideal_str), unsafe_allow_html=True)
        c2.markdown(render_ideal_block("Sector 1", drv_s1, "#df4bff", f"{overall_s1.total_seconds():.3f}" if pd.notna(overall_s1) else "N/A"), unsafe_allow_html=True)
        c3.markdown(render_ideal_block("Sector 2", drv_s2, "#df4bff", f"{overall_s2.total_seconds():.3f}" if pd.notna(overall_s2) else "N/A"), unsafe_allow_html=True)
        c4.markdown(render_ideal_block("Sector 3", drv_s3, "#df4bff", f"{overall_s3.total_seconds():.3f}" if pd.notna(overall_s3) else "N/A"), unsafe_allow_html=True)

    # ── 4. FASTEST LAP SECTOR SPLITS (CSS MATRIX) ────────────
    if not laps.empty:
        section_header("SECTOR TIMES", "Fastest Lap Breakdown by Driver")
        
        try:
            display_data = []
            css_data = []
            
            def get_timing_info(val_td, overall_td, pb_td, is_lap=False):
                if pd.isna(val_td): return "N/A", ""
                
                val = val_td.total_seconds()
                overall = overall_td.total_seconds() if pd.notna(overall_td) else 0
                pb = pb_td.total_seconds() if pd.notna(pb_td) else 0
                
                formatted = format_time(val) if is_lap else f"{val:.3f}"
                
                if abs(val - overall) < 0.001:
                    return formatted, "color: #df4bff; font-weight: 900; background-color: rgba(223, 75, 255, 0.1);" 
                elif abs(val - pb) < 0.001:
                    return formatted, "color: #00d47e; font-weight: 700;"
                else:
                    return formatted, "color: #ffd700;" 
            
            for _, row in results.iterrows():
                drv_name = get_safe_driver_name(row)
                drv_num = row.get('DriverNumber')
                
                drv_laps = None
                if pd.notna(drv_num):
                    try: drv_laps = laps.pick_driver(drv_num)
                    except Exception: pass
                
                if drv_laps is None or drv_laps.empty:
                    try: drv_laps = laps.pick_driver(drv_name)
                    except Exception: continue
                    
                if drv_laps is None or drv_laps.empty: continue
                    
                f_lap = drv_laps.pick_fastest()
                if f_lap is None or len(f_lap) == 0: continue
                    
                lt = f_lap.get('LapTime')
                if pd.isna(lt): continue
                    
                pb_s1 = drv_laps['Sector1Time'].min() if 'Sector1Time' in drv_laps else pd.NaT
                pb_s2 = drv_laps['Sector2Time'].min() if 'Sector2Time' in drv_laps else pd.NaT
                pb_s3 = drv_laps['Sector3Time'].min() if 'Sector3Time' in drv_laps else pd.NaT
                
                v_lap, c_lap = get_timing_info(lt, overall_fl, lt, True)
                v_s1, c_s1 = get_timing_info(f_lap.get('Sector1Time'), overall_s1, pb_s1)
                v_s2, c_s2 = get_timing_info(f_lap.get('Sector2Time'), overall_s2, pb_s2)
                v_s3, c_s3 = get_timing_info(f_lap.get('Sector3Time'), overall_s3, pb_s3)
                
                pos_val = row.get('Position', np.nan)
                pos_str = str(int(pos_val)) if pd.notna(pos_val) else "NC"
                
                display_data.append({
                    'Pos': pos_str, 'Driver': drv_name,
                    'Lap Time': v_lap, 'Sector 1': v_s1, 'Sector 2': v_s2, 'Sector 3': v_s3
                })
                
                css_data.append({
                    'Pos': "",
                    'Driver': f"border-left: 4px solid {driver_color(drv_name, results)}; font-weight: bold;",
                    'Lap Time': c_lap, 'Sector 1': c_s1, 'Sector 2': c_s2, 'Sector 3': c_s3
                })
                
            if display_data:
                df_display = pd.DataFrame(display_data)
                df_css = pd.DataFrame(css_data)
                
                styled_sectors = df_display.style.apply(lambda _: df_css, axis=None)
                st.dataframe(styled_sectors, use_container_width=True, hide_index=True)
            else:
                st.info("No valid sector timing data was recorded for this session.")

        except Exception as e:
            st.warning(f"Could not load sector split data: {e}")