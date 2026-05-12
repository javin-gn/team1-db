import streamlit as st
import pandas as pd
import plotly.express as px
import json
from datetime import datetime
import gdown

# Set page configuration
st.set_page_config(page_title="Job Market Insights Dashboard", layout="wide")

# --- DATA LOADING & PREPROCESSING ---
@st.cache_data
def load_data():
    # Load the dataset

    url = 'https://drive.google.com/uc?export=download&id=1x7hnhCDnUr5UhwEpcpF5_FnFLMnWV7yY'

    # 2. Download into a memory buffer (quiet=True skips output)
    output = gdown.download(url, output=None, quiet=False)
    # 3. Read directly with pandas (assuming CSV)
    df = pd.read_csv(output, compression='zip')
    #df = pd.read_csv('./data/SGJobData.csv')
    
    # 1. CLEANING: Remove null rows with missing position levels (NaN)
    #drop null row
    df =  df.dropna(how='all')
   
    #drop positionLevels that are 'nan' as string
    df = df.dropna(subset=['positionLevels'])
   
    
    # 2. Parse JSON categories
    def extract_categories(cat_string):
        if pd.isna(cat_string): return []
        try:
            # Fix potential escaped quotes
            clean_str = str(cat_string).replace('""', '"')
            cat_list = json.loads(clean_str)
            return [item['category'] for item in cat_list]
        except:
            return []
            
    df['category_list'] = df['categories'].apply(extract_categories)
    
    # 3. Ensure numerical columns are clean
    df['average_salary'] = pd.to_numeric(df['average_salary'], errors='coerce').fillna(0)
    df['numberOfVacancies'] = pd.to_numeric(df['numberOfVacancies'], errors='coerce').fillna(0)
    df['metadata_totalNumberJobApplication'] = pd.to_numeric(df['metadata_totalNumberJobApplication'], errors='coerce').fillna(0)
    
    return df

df = load_data()

# --- PREPARE FILTER OPTIONS ---
all_categories = sorted(list(set([
    str(cat) for sublist in df['category_list'].dropna() 
    for cat in sublist if cat
])))
all_levels = sorted([str(level) for level in df['positionLevels'].unique()])

# --- SESSION STATE INITIALIZATION ---
# This ensures the checkboxes start as "Checked"
for cat in all_categories:
    if f"cat_{cat}" not in st.session_state:
        st.session_state[f"cat_{cat}"] = True

for level in all_levels:
    if f"lvl_{level}" not in st.session_state:
        st.session_state[f"lvl_{level}"] = True

# --- CALLBACK FUNCTIONS ---
def change_all_cats(val):
    for cat in all_categories:
        st.session_state[f"cat_{cat}"] = val

def change_all_levels(val):
    for level in all_levels:
        st.session_state[f"lvl_{level}"] = val

# --- SIDEBAR FILTERS ---
st.sidebar.header("Dashboard Filters")

# 1. Job Categories
st.sidebar.markdown("### Job Categories")
with st.sidebar.expander("Select Categories", expanded=False):
    c1, c2 = st.columns(2)
    c1.button("Select All", on_click=change_all_cats, args=(True,), key="btn_sel_cat")
    c2.button("Deselect All", on_click=change_all_cats, args=(False,), key="btn_desel_cat")
    
    selected_cats = [cat for cat in all_categories if st.checkbox(cat, key=f"cat_{cat}")]

# 2. Position Levels
st.sidebar.markdown("### Position Levels")
with st.sidebar.expander("Select Levels", expanded=True):
    l1, l2 = st.columns(2)
    l1.button("Select All", on_click=change_all_levels, args=(True,), key="btn_sel_lvl")
    l2.button("Deselect All", on_click=change_all_levels, args=(False,), key="btn_desel_lvl")
    
    selected_levels = [lvl for lvl in all_levels if st.checkbox(lvl, key=f"lvl_{lvl}")]

# --- FILTER LOGIC ---
df_filtered = df[df['positionLevels'].isin(selected_levels)]
df_exploded = df_filtered.explode('category_list')
df_exploded = df_exploded[df_exploded['category_list'].isin(selected_cats)]

# --- MAIN DASHBOARD ---
st.title("📊 Job Market Analysis Dashboard")
st.header("Key Metrics")
if not selected_cats or not selected_levels:
    st.warning("⚠️ Please select at least one Category and one Position Level.")
else:
    # Key Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Vacancies", f"{int(df_exploded['numberOfVacancies'].sum()):,}")
    m2.metric("Applications", f"{int(df_exploded['metadata_totalNumberJobApplication'].sum()):,}")
    m3.metric("Avg Salary", f"${df_filtered['average_salary'].mean():,.0f}")
    m4.metric("Avg Exp", f"{df_filtered['minimumYearsExperience'].mean():.1f}y")

    st.divider()

    # Visualizations
    c1, c2 = st.columns(2)

    with c1:
        # Vacancies by Category
        vac_data = df_exploded.groupby('category_list')['numberOfVacancies'].sum().reset_index().sort_values('numberOfVacancies', ascending=False)
        fig_vac = px.bar(vac_data, x='category_list', y='numberOfVacancies', 
                         title="Total Vacancies by Industry", 
                         labels={'category_list': 'Industry', 'numberOfVacancies': 'Vacancies'},
                         color='numberOfVacancies', color_continuous_scale='Viridis')
        st.plotly_chart(fig_vac, use_container_width=True)

    with c2:
        # Competition (Apps per Vacancy)
        comp_data = df_exploded.groupby('category_list').agg({'numberOfVacancies':'sum', 'metadata_totalNumberJobApplication':'sum'})
        # Avoid division by zero
        comp_data['Apps/Vacancy'] = comp_data['metadata_totalNumberJobApplication'] / comp_data['numberOfVacancies'].replace(0, 1)
        comp_data = comp_data.reset_index().sort_values('Apps/Vacancy', ascending=False)
        
        fig_comp = px.bar(comp_data, x='category_list', y='Apps/Vacancy', 
                          title="Competition Ratio (Apps per Vacancy)", 
                          labels={'category_list': 'Industry', 'Apps/Vacancy': 'Apps per Vacancy'},
                          color='Apps/Vacancy', color_continuous_scale='Reds')
        st.plotly_chart(fig_comp, use_container_width=True)

    # Salary Chart
    c3, c4 = st.columns(2)

    with c3:
        # Filter outliers for scatter plot visualization
        sal_limit = df_filtered['average_salary'].quantile(0.98)
        df_scatter = df_filtered[df_filtered['average_salary'] <= sal_limit]
        
        fig_scatter = px.scatter(df_scatter, x='average_salary', y='metadata_totalNumberJobApplication', 
                                 color='positionLevels', size='numberOfVacancies', 
                                 hover_name='title', opacity=0.6,
                                 title="Correlation: Salary vs. Application Volume",
                                 labels={'average_salary': 'Avg Salary ($)', 'metadata_totalNumberJobApplication': 'Total Apps'})
        st.plotly_chart(fig_scatter, use_container_width=True)

    with c4:
        # Interest by Employment Type
        emp_type = df_filtered.groupby('employmentTypes')['metadata_totalNumberJobApplication'].mean().reset_index()
        fig_pie = px.pie(emp_type, values='metadata_totalNumberJobApplication', names='employmentTypes', 
                         title="Average Applicant Interest by Employment Type",
                         hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_pie, use_container_width=True)


st.caption(f"🟢 Retrieved at: {datetime.now().strftime('%d/%m/%Y %H:%M') }" + " | Data Source: data.gov.sg")