import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import re

# ── Page Config & CSS Styling ─────────────────────────────────────────────────
st.set_page_config(page_title="📊 Lead Dashboard V10", layout="wide")
st.markdown(
    """
    <style>
      /* Dark sidebar */
      .css-1d391kg {background-color: #0B1F3A;}
      .css-1d391kg .css-hxt7ib {color: #FFFFFF;}
      /* KPI cards */
      .metric-card {
        background: #ffffff;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        padding: 1rem;
        margin: 0.5rem;
      }
      .card-container {
        display: flex;
        flex-wrap: wrap;
        gap: 1rem;
      }
    </style>
    """, unsafe_allow_html=True
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("📁 File Uploads")
lead_files = st.sidebar.file_uploader(
    "Lead CSVs (Multi‑Vendor)", type="csv", accept_multiple_files=True
)
sales_file = st.sidebar.file_uploader(
    "Sales Data (CSV/Excel)", type=["csv","xlsx"]
)
dispo_file = st.sidebar.file_uploader(
    "Disposition CSV", type="csv"
)
manual_spend = st.sidebar.number_input(
    "SmartFinancial Total Spend", min_value=0.0, step=1.0
)
st.sidebar.markdown("---")

# ── Parsing Helpers ──────────────────────────────────────────────────────────
def parse_lead_file(f):
    name = f.name.rsplit('.',1)[0]
    for sep in ['_','-',' ']:
        if sep in name:
            vendor, campaign = name.split(sep,1)
            break
    else:
        return None
    try:
        df = pd.read_csv(f)
    except:
        return None
    df.rename(columns=lambda c: c.strip(), inplace=True)
    # Email
    email_cols = [c for c in df.columns if 'email' in c.lower()]
    df['email'] = (df[email_cols[0]].astype(str).str.lower().str.strip()
                   if email_cols else None)
    # Cost
    df['cost'] = 0.0
    if vendor.lower() == 'eq' and 'cost' in df.columns:
        df['cost'] = pd.to_numeric(df['cost'], errors='coerce').fillna(0)
        df['cost'] = df['cost'].apply(lambda x: x/100 if x>100 else x)
    if vendor.lower().startswith('smartfinancial') and manual_spend > 0:
        df['cost'] = manual_spend/len(df) if len(df)>0 else 0
    # Names
    fn = [c for c in df.columns if 'first' in c.lower()]
    ln = [c for c in df.columns if 'last' in c.lower()]
    df['first_name'] = df[fn[0]].astype(str) if fn else None
    df['last_name']  = df[ln[0]].astype(str) if ln else None
    # Phone
    ph = [c for c in df.columns if 'phone' in c.lower()]
    df['Phone'] = (
        df[ph[0]].astype(str)
             .str.replace(r'\D', '', regex=True)
             .str[-10:]
    ) if ph else None
    # Created Date
    dt = [c for c in df.columns if 'date' in c.lower()]
    if dt:
        df['Created Date'] = pd.to_datetime(df[dt[0]], errors='coerce')
    # Zip
    zp = [c for c in df.columns if 'zip' in c.lower()]
    if zp:
        df['Zip'] = df[zp[0]]
    # Annotate
    df['vendor'] = vendor
    df['campaign'] = campaign
    cols = ['vendor','campaign','email','first_name','last_name','cost','Phone','Created Date','Zip']
    return df[[c for c in cols if c in df.columns]]


def parse_sales_file(f):
    try:
        df = (pd.read_excel(f) if f.name.lower().endswith(('xls','xlsx'))
              else pd.read_csv(f))
    except:
        return None
    df.rename(columns=lambda c: c.strip(), inplace=True)
    # Email
    em = [c for c in df.columns if 'email' in c.lower()]
    df['email'] = (df[em[0]].astype(str).str.lower().str.strip()
                   if em else None)
    # Assigned To User
    au = [c for c in df.columns if 'assign' in c.lower()]
    df['Assigned To User'] = df[au[0]].astype(str) if au else None
    # Policy/Premium/Items
    for col in ['Policy #','Premium','Items']:
        if col not in df.columns:
            df[col] = 0 if col != 'Policy #' else ''
    df['Premium'] = pd.to_numeric(df['Premium'], errors='coerce').fillna(0)
    df['Items']   = pd.to_numeric(df['Items'], errors='coerce').fillna(0)
    return df[['email','Policy #','Premium','Items','Assigned To User']]

# ── Load Data ─────────────────────────────────────────────────────────────────
if not lead_files or not sales_file:
    st.warning("Upload lead files and sales data via the sidebar.")
    st.stop()
leads = pd.concat(
    [d for d in (parse_lead_file(f) for f in lead_files) if d is not None],
    ignore_index=True
)
if leads.empty:
    st.error("No valid lead data parsed. Check filenames/formats.")
    st.stop()
# Ensure Milestone column exists
if 'Milestone' not in leads.columns:
    leads['Milestone'] = None

# ── Merge Dispositions ─────────────────────────────────────────────────────────
def merge_dispo(df, path):
    dispo = pd.read_csv(path)
    if 'Folders' in dispo.columns:
        dispo = dispo[~dispo['Folders'].astype(str).str.contains('!')]
    if 'Phone' in dispo.columns:
        dispo['Phone'] = (
            dispo['Phone'].astype(str)
                  .str.replace(r'\D','',regex=True)
                  .str[-10:]
        )
        mp = dispo.dropna(subset=['Phone']).drop_duplicates('Phone').set_index('Phone')['Milestone']
        df['Milestone'] = df['Phone'].map(mp).fillna(df['Milestone'])
    return df

if dispo_file:
    leads = merge_dispo(leads, dispo_file)
    st.success("✅ Dispositions merged.")

# ── Merge Sales ─────────────────────────────────────────────────────────────────
sales = parse_sales_file(sales_file)
if sales is not None:
    leads = leads.merge(sales, on='email', how='left')
    st.success("✅ Sales merged.")

# ── Flags & Month ─────────────────────────────────────────────────────────────
leads['is_connected'] = leads['Milestone'].isin(
    ['Contacted','Quoted','Not interested','Xdate','Sold']
)
leads['is_quoted'] = leads['Milestone'] == 'Quoted'
if 'Created Date' in leads.columns:
    leads['Created Date'] = pd.to_datetime(leads['Created Date'], errors='coerce')
    leads['Month'] = leads['Created Date'].dt.to_period('M').astype(str)
else:
    leads['Month'] = 'All'

# ── Filters & View Selector ────────────────────────────────────────────────────
months = sorted(leads['Month'].unique())
sel_month = st.selectbox("Month", ['All'] + months)
sel_view = st.radio("View", ['Campaign','Vendor','Agent','ZIP'], horizontal=True)
if sel_month != 'All':
    leads = leads[leads['Month'] == sel_month]

# ── KPI Cards ─────────────────────────────────────────────────────────────────
st.markdown("<div class='card-container'>", unsafe_allow_html=True)
metrics = [
    ('Premium',     lambda df: df['Premium'].sum()),
    ('Spend',       lambda df: df['cost'].sum()),
    ('Spend→Earn',  lambda df: round(df['Premium'].sum()/df['cost'].sum(),2)
                     if df['cost'].sum()>0 else 0),
    ('Leads',       lambda df: df['email'].nunique()),
    ('Connect Rate',lambda df: f"{round(df['is_connected'].mean()*100,1)}%"),
    ('Quote Rate',  lambda df: f"{round(df['is_quoted'].mean()*100,1)}%"),
    ('Close Rate',  lambda df: f"{round(df['Policy #'].ne('').mean()*100,1)}%")
]
for title, func in metrics:
    val = func(leads)
    st.markdown(f"""
      <div class='metric-card'>
        <div style='font-size:14px;color:#333;'>{title}</div>
        <div style='font-size:24px;font-weight:bold;margin-top:0.5rem;'>{val}</div>
      </div>
    """, unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# ── Views ─────────────────────────────────────────────────────────────────────
if sel_view == 'Campaign':
    st.subheader("Campaign View")
    dfc = leads.groupby(['vendor','campaign']).agg(
        Premium=('Premium','sum'), Spend=('cost','sum'),
        Leads=('email','nunique'), Connects=('is_connected','sum'),
        Quotes=('is_quoted','sum'), Policies=('Policy #', lambda x: x.ne('').sum())
    ).reset_index()
    for col in ['Connects','Quotes','Policies']:
        dfc[f'{col} Rate'] = (dfc[col]/dfc['Leads']*100).round(1).astype(str)+'%'
    st.dataframe(dfc, use_container_width=True)

elif sel_view == 'Vendor':
    st.subheader("Vendor View")
    dfv = leads.groupby('vendor').agg(
        Premium=('Premium','sum'), Spend=('cost','sum'),
        Leads=('email','nunique'), Connects=('is_connected','sum'),
        Quotes=('is_quoted','sum'), Policies=('Policy #', lambda x: x.ne('').sum())
    ).reset_index()
    for col in ['Connects','Quotes','Policies']:
        dfv[f'{col} Rate'] = (dfv[col]/dfv['Leads']*100).round(1).astype(str)+'%'
    st.dataframe(dfv, use_container_width=True)

elif sel_view == 'Agent':
    st.subheader("Agent Metrics")
    if 'Assigned To User' in leads.columns and leads['Assigned To User'].notna().any():
        dfa = leads.groupby('Assigned To User').agg(
            Leads=('email','nunique')
