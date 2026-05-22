"""
teammates.py — Teammate Head-to-Head module for PitWall Analytics
"""
import streamlit as st
import fastf1
import pandas as pd
from utils import section_header

def render_teammate_selector(year, race, session_id, session_name, available_drivers):
    section_header("TEAMMATE DUEL", f"{year} {race}  ·  {session_name}")
    st.markdown("#### Intra-Team Battles")
    
    valid_pairs = []
    
    # ── 1. DYNAMIC TEAMMATE EXTRACTION ──
    try:
        session = fastf1.get_session(year, race, session_id)
        # Load quietly without telemetry or laps for maximum speed
        session.load(telemetry=False, weather=False, messages=False, laps=False)
        results = session.results
        
        # Group drivers by their official TeamName for this specific session
        teams = {}
        for _, row in results.iterrows():
            team = row.get('TeamName')
            driver = row.get('Abbreviation')
            
            # Ensure the driver is valid and actually recorded times in the session
            if pd.notna(team) and pd.notna(driver) and driver in available_drivers:
                if team not in teams:
                    teams[team] = []
                teams[team].append(driver)
                
        # Extract pairs (only teams that fielded at least 2 drivers)
        for team, drivers in teams.items():
            if len(drivers) >= 2:
                # In the rare event of >2 drivers (like an FP1 session swap), pair the top two
                valid_pairs.append((drivers[0], drivers[1], team))
                
    except Exception as e:
        st.error(f"Could not load team groupings: {e}")
        return
        
    if not valid_pairs:
        st.info("No valid teammate pairs found for this specific session.")
        return
        
    # ── 2. UI & ROUTING ──
    # Create a clean dictionary mapping the display name to the driver list
    # e.g., "Mercedes: HAM vs RUS" -> ["HAM", "RUS"]
    pair_options = {f"{team}: {d1} vs {d2}": [d1, d2] for d1, d2, team in valid_pairs}
    
    col1, col2 = st.columns([1.5, 2])
    with col1:
        selected_pair_str = st.selectbox("Select Team Battle", list(pair_options.keys()))
        
    st.divider()
    
    # Extract the target array of driver abbreviations
    selected_drivers = pair_options[selected_pair_str]
    
    # Fire up the comparison engine
    with st.spinner(f"Loading Head-to-Head for {selected_drivers[0]} vs {selected_drivers[1]}..."):
        import compare
        compare.render_comparison(year, race, session_id, session_name, selected_drivers)