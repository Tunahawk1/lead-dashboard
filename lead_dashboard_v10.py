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
        st.warning(f"⚠️ Filename '{f.name}' invalid; skipping.")
        return None
    try:
        df = pd.read_csv(f)
    except Exception:
        st.warning(f"⚠️ Could not read '{f.name}'; skipping.")
        return None
    df.rename(columns=lambda c: c.strip(), inplace=True)
    # email
    em_cols = [c for c in df.columns if c.lower()=='email']
    df['email'] = df[em_cols[0]].astype(str).str.lower().str.strip() if em_cols else None
    # cost default
    df['cost'] = 0.0
    # vendor cost handling
    if vendor.lower()=='eq':
        if 'cost' in df.columns:
            df['cost'] = pd.to_numeric(df['cost'], errors='coerce').fillna(0)
            df['cost'] = df['cost'].apply(lambda x: x/100 if x>100 else x)
    elif vendor.lower().startswith('smartfinancial'):
        # manual spend override later
        pass
    # names
    fn = [c for c in df.columns if 'first' in c.lower()]
    ln = [c for c in df.columns if 'last' in c.lower()]
    df['first_name'] = df[fn[0]].astype(str) if fn else None
    df['last_name']  = df[ln[0]].astype(str) if ln else None
    # phone
    ph = [c for c in df.columns if 'phone' in c.lower()]
    if ph:
        df['Phone'] = (
            df[ph[0]].astype(str)
              .str.replace(r'\D','',regex=True)
              .str[-10:]
        )
    else:
        df['Phone'] = None
    # date
    dt = [c for c in df.columns if 'date' in c.lower()]
    if dt:
        df['Created Date'] = pd.to_datetime(df[dt[0]], errors='coerce')
    # zip
    zp = [c for c in df.columns if 'zip' in c.lower()]
    if zp:
        df['Zip'] = df[zp[0]]
    # annotate
    df['vendor']   = vendor
    df['campaign'] = campaign
    keep = ['vendor','campaign','email','first_name','last_name','cost','Phone','Created Date','Zip']
    return df[[c for c in keep if c in df.columns]]


def parse_sales_file(f):
    try:
        df = pd.read_excel(f) if f.name.lower().endswith(('xls','xlsx')) else pd.read_csv(f)
    except Exception:
        st.warning(f"⚠️ Could not read sales file: {f.name}")
        return None
    df.rename(columns=lambda c: c.strip(), inplace=True)
    # email
    em = [c for c in df.columns if 'email' in c.lower()]
    df['email'] = df[em[0]].astype(str).str.lower().str.strip() if em else None
    # assigned user
    assign_cols = [c for c in df.columns if 'assign' in c.lower()]
    df['Assigned To User'] = df[assign_cols[0]].astype(str) if assign_cols else None
    # ensure fields
    for col in ['Policy #','Premium','Items']:
        if col not in df.columns:
            df[col] = 0 if col!='Policy #' else ''
    df['Premium'] = pd.to_numeric(df['Premium'], errors='coerce').fillna(0)
    df['Items']   = pd.to_numeric(df['Items'], errors='coerce').fillna(0)
    return df[['email','Policy #','Premium','Items','Assigned To User']]

# ── Load & Initial Merge ───────────────────────────────────────────────────────
if not lead_files or not sales_file:
    st.info("Upload lead & sales files to start.")
    st.stop()
lead_dfs = [parse_lead_file(f) for f in lead_files]
leads = pd.concat([d for d in lead_dfs if d is not None], ignore_index=True)
if leads.empty:
    st.error("No valid lead data parsed.")
    st.stop()
# apply SmartFinancial spend
sf_mask = leads['vendor'].str.lower().str.startswith('smartfinancial')
if manual_spend>0 and sf_mask.sum()>0:
    leads.loc[sf_mask, 'cost'] = manual_spend / sf_mask.sum()

# ── Dispositions Mapping (no duplication) ─────────────────────────────────────
if dispo_file:
    dispo_raw = pd.read_csv(dispofile:=dispo_file)
    # exclude return reasons
    if 'Folders' in dispo_raw.columns:
        dispo_raw = dispo_raw[~dispo_raw['Folders'].astype(str).str.contains('!')]
    dispo_raw.rename(columns=lambda c: c.strip(), inplace=True)
    # map by phone
    if 'Phone' in dispo_raw.columns:
        dispo_raw['Phone'] = (
            dispo_raw['Phone'].astype(str)
                     .str.replace(r'\D','',regex=True)
                     .str[-10:]
        )
        phone_map = dispo_raw.dropna(subset=['Phone']).drop_duplicates('Phone').set_index('Phone')['Milestone']
        leads['Milestone'] = leads['Phone'].map(phone_map)
    # fallback by name
    dispo_raw['first_name'] = dispo_raw.get('first_name', dispo_raw.get('First Name', pd.Series())).astype(str).str.upper().str.strip()
    dispo_raw['last_name']  = dispo_raw.get('last_name',  dispo_raw.get('Last Name',  pd.Series())).astype(str).str.upper().str.strip()
    name_map = dispo_raw.dropna(subset=['first_name','last_name']).drop_duplicates(subset=['first_name','last_name']).set_index(['first_name','last_name'])['Milestone']
    mask = leads['Milestone'].isna() & leads['first_name'].notna() & leads['last_name'].notna()
    leads.loc[mask, 'Milestone'] = leads[mask].apply(lambda r: name_map.get((r['first_name'],r['last_name'])), axis=1)
    st.success("Dispositions mapped.")

# ── Sales Merge ───────────────────────────────────────────────────────────────
sales = parse_sales_file(sales_file)
if sales is not None:
    leads = leads.merge(sales, on='email', how='left')
    st.success("Sales merged.")

# ── Flags & Month ─────────────────────────────────────────────────────────────
leads['is_connected'] = leads['Milestone'].isin(['Contacted','Quoted','Not interested','Xdate','Sold'])
leads['is_quoted']    = leads['Milestone']=='Quoted'
if 'Created Date' in leads.columns:
    leads['Created Date'] = pd.to_datetime(leads['Created Date'], errors='coerce')
    leads['Month'] = leads['Created Date'].dt.to_period('M').astype(str)
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
    months = sorted(leads['Month'].unique())
    selm = st.selectbox('Select Month', ['All']+months)
    dfc = leads if selm=='All' else leads[leads['Month']==selm]
    summ = dfc.groupby(['vendor','campaign']).agg(
        Premium=('Premium','sum'),
        Spend=('cost','sum'),
        Leads=('email','nunique'),
        Connects=('is_connected','sum'),
        Quotes=('is_quoted','sum'),
        Policies=('Policy #', lambda x: x.ne('').sum())
    ).reset_index()
    for _,r in summ.iterrows():
        ct = round(r.Connects/r.Leads*100,1) if r.Leads else 0
        qr = round(r.Quotes/r.Leads*100,1) if r.Leads else 0
        cr = round(r.Policies/r.Leads*100,1) if r.Leads else 0
        st.markdown(f"### {r.vendor} – {r.campaign}")
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Premium Earned", f"${r.Premium:,.2f}")
        c2.metric("Marketing Spend", f"${r.Spend:,.2f}")
        c3.metric("Spend→Earn", f"{(r.Premium/r.Spend if r.Spend else 0):.2f}x")
        c4.metric("Total Leads", int(r.Leads))
        c5,c6,c7 = st.columns(3)
        c5.metric("Connect Rate", f"{ct}%")
        c6.metric("Quote Rate", f"{qr}%")
        c7.metric("Close Rate", f"{cr}%")

# Vendor View
with tab2:
    vd = leads if selm=='All' else leads[leads['Month']==selm]
    gv = vd.groupby('vendor').agg(
        Premium=('Premium','sum'),
        Spend=('cost','sum'),
        Leads=('email','nunique'),
        Connects=('is_connected','sum'),
        Quotes=('is_quoted','sum'),
        Policies=('Policy #', lambda x: x.ne('').sum())
    ).reset_index()
    for _,r in gv.iterrows():
        cr = round(r.Policies/r.Leads*100,1) if r.Leads else 0
        st.markdown(f"## {r.vendor}")
        a,b,c,d = st.columns(4)
        a.metric("Premium", f"${r.Premium:,.2f}")
        b.metric("Spend", f"${r.Spend:,.2f}")
        c.metric("Leads", int(r.Leads))
        d.metric("Close Rate", f"{cr}%")

# Agent Metrics
with tab3:
    am = leads if selm=='All' else leads[leads['Month']==selm]
    if 'Assigned To User' in am.columns:
        ag = am.groupby('Assigned To User').agg(
            Leads=('email','nunique'),
            Policies=('Policy #', lambda x: x.ne('').sum()),
            Connects=('is_connected','sum'),
            Quotes=('is_quoted','sum')
        ).reset_index()
        ag['Connect Rate'] =(ag.Connects/ag.Leads*100).round(1).astype(str)+'%'
        ag['Quote Rate']   =(ag.Quotes/ag.Leads*100).round(1).astype(str)+'%'
        st.dataframe(ag)
    else:
        st.warning('No Assigned To User data for agents.')

# ZIP Breakdown
with tab4:
    if 'Zip' in leads.columns:
        zz = leads if selm=='All' else leads[leads['Month']==selm]
        zsum = zz.groupby('Zip').agg(
            Leads=('email','nunique'),
            Premium=('Premium','sum')
        ).reset_index()
        chart = alt.Chart(zsum).mark_bar().encode(x='Zip',y='Premium')
        st.altair_chart(chart, use_container_width=True)
    else:
        st.warning('No ZIP data found.')
