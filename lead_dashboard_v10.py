import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import re

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="📊 Lead Dashboard v10", layout="wide")

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.header("📁 Upload Files")
lead_files = st.sidebar.file_uploader(
    "Lead CSVs (Multiple Vendors)", type="csv", accept_multiple_files=True
)
sales_file = st.sidebar.file_uploader(
    "Sales Data (CSV/Excel)", type=["csv","xlsx"]
)
dispo_file = st.sidebar.file_uploader(
    "Lead Dispositions (CSV)", type="csv"
)
manual_spend = st.sidebar.number_input(
    "SmartFinancial Total Spend", min_value=0.0, step=1.0
)

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
    # email
    emails = [c for c in df.columns if 'email' in c.lower()]
    df['email'] = df[emails[0]].astype(str).str.lower().str.strip() if emails else None
    # cost
    costs = [c for c in df.columns if any(x in c.lower() for x in ['cost','spend','amount','amt'])]
    df['cost'] = pd.to_numeric(df[costs[0]], errors='coerce').fillna(0) if costs else 0.0
    if vendor.lower()=='eq':
        df['cost'] = df['cost'].apply(lambda x: x/100 if x>100 else x)
    if vendor.lower().startswith('smartfinancial') and manual_spend>0:
        df['cost'] = manual_spend/len(df) if len(df)>0 else 0
    # names
    fns = [c for c in df.columns if 'first' in c.lower()]
    lns = [c for c in df.columns if 'last' in c.lower()]
    df['first_name'] = df[fns[0]].astype(str) if fns else None
    df['last_name']  = df[lns[0]].astype(str) if lns else None
    # phone
    phs = [c for c in df.columns if 'phone' in c.lower()]
    df['Phone'] = (
        df[phs[0]].astype(str)
          .str.replace(r'\D','',regex=True)
          .str[-10:]
    ) if phs else None
    # date
    dates = [c for c in df.columns if 'date' in c.lower()]
    if dates:
        df['Created Date'] = pd.to_datetime(df[dates[0]], errors='coerce')
    # zip
    zips = [c for c in df.columns if 'zip' in c.lower()]
    if zips:
        df['Zip'] = df[zips[0]]
    # annotate
    df['vendor']   = vendor
    df['campaign'] = campaign
    keep = ['vendor','campaign','email','first_name','last_name','cost','Phone','Created Date','Zip']
    return df[[c for c in keep if c in df.columns]]


def parse_sales(f):
    try:
        df = pd.read_excel(f) if f.name.lower().endswith(('xls','xlsx')) else pd.read_csv(f)
    except:
        return None
    df.rename(columns=lambda c: c.strip(), inplace=True)
    em = [c for c in df.columns if 'email' in c.lower()]
    df['email'] = df[em[0]].astype(str).str.lower().str.strip() if em else None
    for col in ['Policy #','Premium','Items','Assigned To User']:
        if col not in df.columns:
            df[col] = np.nan
    df['Premium'] = pd.to_numeric(df['Premium'], errors='coerce').fillna(0)
    df['Items']   = pd.to_numeric(df['Items'], errors='coerce').fillna(0)
    return df[['email','Policy #','Premium','Items','Assigned To User']]

# ── Load & Merge ───────────────────────────────────────────────────────────────
if not lead_files or not sales_file:
    st.info("Upload lead + sales files to get started.")
    st.stop()

dfs = [parse_lead_file(f) for f in lead_files]
leads = pd.concat([d for d in dfs if d is not None], ignore_index=True)
if leads.empty:
    st.error("No valid lead data. Check filenames/formats.")
    st.stop()

if dispo_file:
    dispo = pd.read_csv(dispofile:=dispo_file)
    if 'Folders' in dispo.columns:
        dispo = dispo[~dispo['Folders'].astype(str).str.contains('!')]
    ph = [c for c in dispo.columns if 'phone' in c.lower()]
    fn = [c for c in dispo.columns if 'first' in c.lower()]
    ln = [c for c in dispo.columns if 'last' in c.lower()]
    if ph:
        dispo['Phone'] = (
            dispo[ph[0]].astype(str)
                  .str.replace(r'\D','',regex=True)
                  .str[-10:]
        )
    if fn:
        dispo['first_name'] = dispo[fn[0]].astype(str).str.upper().str.strip()
    if ln:
        dispo['last_name']  = dispo[ln[0]].astype(str).str.upper().str.strip()
    leads['Phone']      = leads['Phone'].astype(str).str.replace(r'\D','',regex=True).str[-10:]
    leads['first_name'] = leads['first_name'].astype(str).str.upper().str.strip()
    leads['last_name']  = leads['last_name'].astype(str).str.upper().str.strip()
    leads = pd.merge(leads, dispo, on='Phone', how='left', suffixes=('','_d'))
    st.success("Dispositions merged.")

sales = parse_sales(sales_file)
if sales is not None:
    leads = leads.merge(sales, on='email', how='left')
    st.success("Sales merged.")

# ── Flags & Month ─────────────────────────────────────────────────────────────
leads['is_connected'] = (
    leads['Milestone'].isin(['Contacted','Quoted','Not interested','Xdate','Sold'])
    if 'Milestone' in leads.columns else False
)
leads['is_quoted'] = (
    leads['Milestone']=='Quoted' if 'Milestone' in leads.columns else False
)

# Convert Created Date to datetime and derive Month
if 'Created Date' in leads.columns:
    leads['Created Date'] = pd.to_datetime(leads['Created Date'], errors='coerce')
    leads['Month'] = leads['Created Date'].dt.to_period('M')
else:
    leads['Month'] = 'All'

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1,tab2,tab3,tab4 = st.tabs([
    '📊 Campaign View',
    '🏷️ Vendor View',
    '🧑 Agent Metrics',
    '📍 ZIP Breakdown'
])

# Campaign View
with tab1:
    months = sorted(leads['Month'].astype(str).unique())
    selm = st.selectbox('Select Month', ['All'] + months)
    dfc = leads if selm=='All' else leads[leads['Month'].astype(str)==selm]
    summ = dfc.groupby(['vendor','campaign']).agg(
        Premium=('Premium','sum'),
        Spend=('cost','sum'),
        Leads=('email','nunique'),
        Connects=('is_connected','sum'),
        Quotes=('is_quoted','sum'),
        Policies=('Policy #', lambda x: x.ne('').sum())
    ).reset_index()
    for _, r in summ.iterrows():
        r_ct = round(r.Connects/r.Leads*100,1) if r.Leads else 0
        r_qr = round(r.Quotes/r.Leads*100,1) if r.Leads else 0
        r_cl = round(r.Policies/r.Leads*100,1) if r.Leads else 0
        st.markdown(f"### {r.vendor} – {r.campaign}")
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Premium Earned", f"${r.Premium:,.2f}")
        c2.metric("Marketing Spend", f"${r.Spend:,.2f}")
        c3.metric("Spend→Earn", f"{(r.Premium/r.Spend if r.Spend else 0):.2f}x")
        c4.metric("Total Leads", int(r.Leads))
        c5,c6,c7 = st.columns(3)
        c5.metric("Connect Rate", f"{r_ct}%")
        c6.metric("Quote Rate", f"{r_qr}%")
        c7.metric("Close Rate", f"{r_cl}%")

# Vendor View
with tab2:
    vd = leads if selm=='All' else leads[leads['Month'].astype(str)==selm]
    gv = vd.groupby('vendor').agg(
        Premium=('Premium','sum'),
        Spend=('cost','sum'),
        Leads=('email','nunique'),
        Connects=('is_connected','sum'),
        Quotes=('is_quoted','sum'),
        Policies=('Policy #', lambda x: x.ne('').sum())
    ).reset_index()
    for _, r in gv.iterrows():
        r_cl = round(r.Policies/r.Leads*100,1) if r.Leads else 0
        a,b,c,d = st.columns(4)
        a.metric("Premium", f"${r.Premium:,.2f}")
        b.metric("Spend", f"${r.Spend:,.2f}")
        c.metric("Leads", int(r.Leads))
        d.metric("Close Rate", f"{r_cl}%")

# Agent Metrics
with tab3:
    am = leads if selm=='All' else leads[leads['Month'].astype(str)==selm]
    if 'Assigned To User' in am.columns:
        ag = am.groupby('Assigned To User').agg(
            Leads=('email','nunique'),
            Policies=('Policy #', lambda x: x.ne('').sum()),
            Connects=('is_connected','sum'),
            Quotes=('is_quoted','sum')
        ).reset_index()
        ag['Connect Rate'] = (ag.Connects/ag.Leads*100).round(1).astype(str)+'%'
        ag['Quote Rate']   = (ag.Quotes/ag.Leads*100).round(1).astype(str)+'%'
        st.dataframe(ag)
    else:
        st.warning('No Assigned To User data for agents.')

# ZIP Breakdown
with tab4:
    if 'Zip' in leads.columns:
        zz = leads if selm=='All' else leads[leads['Month'].astype(str)==selm]
        zsum = zz.groupby('Zip').agg(
            Leads=('email','nunique'),
            Premium=('Premium','sum')
        ).reset_index()
        chart = alt.Chart(zsum).mark_bar().encode(x='Zip',y='Premium')
        st.altair_chart(chart, use_container_width=True)
    else:
        st.warning('No ZIP data found.')
