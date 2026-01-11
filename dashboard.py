import streamlit as st
import pandas as pd
import os

# Page Config
st.set_page_config(page_title="ReguLink AI", layout="wide", page_icon="🇪🇺")

# Custom CSS for "Bloomberg Terminal" vibes
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #FAFAFA; }
    .metric-card { background-color: #262730; padding: 15px; border-radius: 5px; border: 1px solid #41424b; }
    div[data-testid="stExpander"] { border: 1px solid #41424b; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# Load Data
DATA_FILE = os.path.join("data", "intelligence_report.csv")

@st.cache_data
def load_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        # Ensure date column is datetime for sorting
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.date
        return df
    return pd.DataFrame()

df = load_data()

# Header
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.markdown("# 🇪🇺")
with col_title:
    st.title("ReguLink AI: Intelligence Feed")
    st.caption("Automated Regulatory Monitoring for the European Union")

# Metrics
if not df.empty:
    total_alerts = len(df)
    high_impact = len(df[df['impact_score'] >= 7])
    sources_count = df['source'].nunique()
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Alerts", total_alerts)
    m2.metric("High Impact (>7)", high_impact, delta_color="inverse")
    m3.metric("Sources Monitored", sources_count)
    st.markdown("---")

# Main Feed
if not df.empty:
    # Sidebar Filters
    st.sidebar.header("🔍 Filters")
    
    # 1. Search
    search_term = st.sidebar.text_input("Search keywords...")
    
    # 2. Score Slider
    min_score = st.sidebar.slider("Minimum Impact Score", 0, 10, 3)
    
    # 3. Source Filter
    all_sources = sorted(df['source'].unique().tolist())
    selected_sources = st.sidebar.multiselect("Select Sources", all_sources, default=all_sources)

    # Apply Logic
    filtered_df = df[
        (df['impact_score'] >= min_score) &
        (df['source'].isin(selected_sources))
    ]
    
    if search_term:
        filtered_df = filtered_df[
            filtered_df['summary'].str.contains(search_term, case=False, na=False) |
            filtered_df['tags'].str.contains(search_term, case=False, na=False)
        ]

    # Sort by Date (Newest first) and Score
    filtered_df = filtered_df.sort_values(by=['date', 'impact_score'], ascending=[False, False])

    st.subheader(f"Latest Intelligence ({len(filtered_df)})")

    for index, row in filtered_df.iterrows():
        # Color logic
        score = row['impact_score']
        color = "🔴" if score >= 8 else "jg" if score >= 5 else "🟢"
        emoji_score = f"{color} **{score}/10**"
        
        with st.expander(f"{emoji_score} | {row['summary']}"):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**Source:** {row['source']}")
                st.markdown(f"**Date:** {row['date']}")
                st.markdown(f"**Tags:** `{row['tags']}`")
                st.markdown(f"**Summary:** {row['summary']}")
            with c2:
                st.markdown(f"[🔗 Read Source]({row['url']})")
                if st.button("Generate Newsletter 📝", key=f"btn_{index}"):
                    st.toast("Drafting newsletter section... (Mock)")

else:
    st.info("No data found. Please run the 'Analyst Agent' to generate the report.")