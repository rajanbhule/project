import streamlit as st
import pandas as pd
import json
import matplotlib.pyplot as plt

# --- 1. PAGE SETUP ---
st.set_page_config(page_title="ALF Engineering Dashboard", page_icon="⚙️", layout="wide")
st.title("⚙️ ABC Engineering Pvt. Ltd.")
st.subheader("IIoT Press Machine Performance & Efficiency Dashboard")

# --- 2. HELPER FUNCTIONS ---
def to_min(t):
    try:
        if ':' in str(t):
            h, m = str(t).split(':')
            return int(h) * 60 + int(m)
        return float(t)
    except: 
        return 0.0

@st.cache_data # Caches the data so the app runs lightning fast
def load_and_process_data(file):
    df = pd.read_csv(file)
    
    # CLEANING
    df = df[~df['tool_id'].isin([50, 500, 50.0, 500.0])]
    df = df[df['machine_id'] > 0].dropna(subset=['machine_id', 'tool_id'])
    
    true_reasons = []
    idle_total_mins = []

    # LOGIC
    for row in df['multiple_loss_code']:
        row_reasons = []
        row_idle = 0.0
        try:
            data = json.loads(str(row).replace("'", '"'))
            for item in data:
                name = item.get('lossName')
                time = to_min(item.get('lossTime', 0))
                if name == 'Machine Idle':
                    row_idle += time
                elif name:
                    row_reasons.append(name)
        except: pass
        true_reasons.append(row_reasons)
        idle_total_mins.append(row_idle)

    df['net_idle_m'] = idle_total_mins
    df['net_downtime_m'] = (df['downtime'].apply(to_min) - df['net_idle_m']).clip(lower=0)
    
    # Extract Root Causes
    flat_reasons = [item for sublist in true_reasons if isinstance(sublist, list) for item in sublist]
    loss_counts = pd.Series(flat_reasons).value_counts()
    
    return df, loss_counts

# --- 3. UI LAYOUT & FILE UPLOAD ---
uploaded_file = st.file_uploader("Upload your Production Data (dpr.csv)", type=["csv"])

if uploaded_file is not None:
    # Load data
    df, loss_counts = load_and_process_data(uploaded_file)
    
    # Top-Level KPI Metrics
    st.markdown("---")
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric(label="Total Strokes Processed", value=f"{df['batch_strokes'].sum():,.0f}")
    kpi2.metric(label="Total True Downtime (Hrs)", value=f"{(df['net_downtime_m'].sum() / 60):,.2f}")
    kpi3.metric(label="Active Machines Monitored", value=df['machine_id'].nunique())
    
    # Create Tabs for neat organization
    tab1, tab2, tab3 = st.tabs(["📊 Performance KPIs", "⏱️ Shift Efficiency", "🔍 Root Cause Analysis"])
    
    # --- TAB 1: PERFORMANCE KPIs ---
    with tab1:
        st.header("Best & Worst Performers")
        sections = {'machine_id': 'Machine', 'tool_id': 'Tool & Die'}
        kpis = {'batch_strokes': ('Total Production (Strokes)', True), 
                'actual_spm': ('Avg Operating Speed (SPM)', True), 
                'net_downtime_m': ('Net True Downtime (Mins)', False)}

        for key, title in sections.items():
            st.subheader(f"{title} Performance")
            summary = df.groupby(key).agg({'batch_strokes':'sum', 'actual_spm':'mean', 'net_downtime_m':'sum'}).reset_index()
            
            # Create a display table
            display_data = []
            for col, (name, high_better) in kpis.items():
                sorted_df = summary.sort_values(by=col, ascending=not high_better)
                b, w = sorted_df.iloc[0], sorted_df.iloc[-1]
                display_data.append({
                    "Metric": name,
                    "Best Performer": f"ID {b[key]} ({b[col]:,.2f})",
                    "Worst Performer": f"ID {w[key]} ({w[col]:,.2f})"
                })
            st.table(pd.DataFrame(display_data))

    # --- TAB 2: SHIFT EFFICIENCY ---
    with tab2:
        st.header("Shift Efficiency Summary")
        shift_tab = df.groupby('shift').agg(
            Total_Strokes=('batch_strokes', 'sum'), 
            Downtime_Mins=('net_downtime_m', 'sum')
        ).sort_values('Total_Strokes', ascending=False).reset_index()
        
        shift_tab['Downtime (Hrs)'] = (shift_tab['Downtime_Mins'] / 60).round(2)
        shift_tab = shift_tab[['shift', 'Total_Strokes', 'Downtime (Hrs)']]
        shift_tab.index = shift_tab.index + 1 # For visual ranking
        
        st.dataframe(shift_tab, use_container_width=True)

    # --- TAB 3: ROOT CAUSE ANALYSIS & VISUALIZATION ---
    with tab3:
        st.header("Downtime Root Cause Analysis (Excl. Machine Idle)")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.write("**Top Critical Reasons**")
            st.dataframe(loss_counts.rename("Occurrences"), height=350, use_container_width=True)
            
        with col2:
            st.write("**Downtime Visualization**")
            # Matplotlib integration
            fig, ax = plt.subplots(figsize=(8, 5))
            loss_counts.head(8).sort_values().plot(kind='barh', color='darkorange', ax=ax)
            ax.set_title('Top 8 True Downtime Root Causes')
            ax.set_xlabel('Occurrences')
            st.pyplot(fig)

else:
    st.info("Please upload the dpr.csv file to generate the dashboard.")