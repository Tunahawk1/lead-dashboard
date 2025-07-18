import streamlit as st
import pandas as pd
import numpy as np
import re
import altair as alt

# ── Streamlit page config ─────────────────────────────────────────────────────
st.set_page_config(page_title="📊 Lead Dashboard v10", layout="wide")

# ── Sidebar uploads ────────────────────────────────────────────────────────────
st.sidebar.header("📁 Upload Your Files")
lead_files = st.sidebar.file_uploader(
    "Upload Lead CSVs (Multiple Vendors)", accept_multiple_files=True, type="csv"
)
sales_file = st.sidebar.file_uploader(
    "Upload SALES DATA (CSV or Excel)", type=["csv", "xlsx"]
)
dispo_file = st.sidebar.file_uploader(
    "Upload Lead Dispositions (CSV)", type="csv"
)
smart_manual_spend = st.sidebar.number_input(
    "SmartFinancial Total Spend (Optional)", min_value=0.0, step=1.0
)

# ── Helper: parse vendor lead files ─────────────────────────────────────────────
def parse_lead_file(uploaded_file):
    name = uploaded_file.name.rsplit('.', 1)[0]
    # split on first separator
    for sep in ['_', '-', ' ']:
        if sep in name:
            vendor, campaign = name.split(sep, 1)
            break
    else:
        st.warning(f"⚠️ Filename '{uploaded_file.name}' must be 'vendor_campaign'. Skipping.")
        return None

    try:
        df = pd.read_csv(uploaded_file)
    except Exception:
        st.warning(f"⚠️ Could not read '{uploaded_file.name}'. Skipping.")
        return None

    df = df.copy()
    # generic parsing for any vendor
    cols = {c: c.strip() for c in df.columns}
    df.rename(columns=cols, inplace=True)
    # email
    email_cols = [c for c in df.columns if c.lower() == 'email']
    if email_cols:
        df['email'] = df[email_cols[0]].astype(str).str.lower().str.strip()
    else:
        df['email'] = None
    # cost
    cost_cols = [c for c in df.columns if c.lower() == 'cost']
    if cost_cols:
        df['cost'] = pd.to_numeric(df[cost_cols[0]], errors='coerce').fillna(0)
    else:
        df['cost'] = 0.0
    # first/last name
    fn = [c for c in df.columns if 'first' in c.lower()]
    ln = [c for c in df.columns if 'last' in c.lower()]
    df['first_name'] = df[fn[0]].astype(str) if fn else None
    df['last_name'] = df[ln[0]].astype(str) if ln else None
    # phone
    ph = [c for c in df.columns if 'phone' in c.lower()]
    if ph:
        df['Phone'] = (
            df[ph[0]].astype(str)
               .str.replace(r'\D', '', regex=True)
               .str[-10:]
        )
    else:
        df['Phone'] = None

    # vendor adjustments
    if vendor.lower() == 'eq':
        # cost might be in cents
        df['cost'] = df['cost'].apply(lambda x: x/100 if x>100 else x)
    if vendor.lower().startswith('smartfinancial') and smart_manual_spend>0:
        # override cost later
        pass

    # annotate
    df['vendor'] = vendor
    df['campaign'] = campaign

    # preserve Created Date, Zip
    keep = ['vendor','campaign','email','first_name','last_name','cost','Phone']
    if 'Created Date' in df.columns:
        df['Created Date'] = pd.to_datetime(df['Created Date'], errors='coerce')
        keep.append('Created Date')
    zipc = [c for c in df.columns if c.lower()=='zip']
    if zipc:
        df['Zip'] = df[zipc[0]]
        keep.append('Zip')

    return df[keep]

# ── Helper: parse sales data ────────────────────────────────────────────────────
def parse_sales_file(uploaded_file):
    try:
        if uploaded_file.name.lower().endswith(('xlsx','xls')):
            df = pd.read_excel(uploaded_file)
        else:
            df = pd.read_csv(uploaded_file)
    except Exception as e:
        st.warning(f"⚠️ Could not read sales file: {e}")
        return None
    df = df.rename(columns={c:c.strip() for c in df.columns})
    # email
    em = [c for c in df.columns if c.lower()=='email']
    if em:
        df['email'] = df[em[0]].astype(str).str.lower().str.strip()
    else:
        df['email'] = None
    # ensure cols
    for c in ['Policy #','Premium','Items','Customer','Assigned To User']:
        if c not in df.columns:
            df[c] = np.nan
    df['Premium'] = pd.to_numeric(df['Premium'], errors='coerce').fillna(0)
    df['Items']   = pd.to_numeric(df['Items'], errors='coerce').fillna(0)
    return df[['email','Policy #','Premium','Items','Customer','Assigned To User']]

# ── Main processing ──────────────────────────────────────────────────────────────
if not lead_files or not sales_file:
    st.info('📌 Upload both lead files and sales data to populate dashboard.')
    st.stop()

# parse leads
dfs = [parse_lead_file(f) for f in lead_files]
leads = pd.concat([d for d in dfs if d is not None], ignore_index=True)
if leads.empty:
    st.error('No valid lead files parsed. Check filenames.')
    st.stop()

# apply manual SmartFinancial spend
auto_mask = leads['vendor'].str.lower().str.startswith('smartfinancial')
if smart_manual_spend>0 and auto_mask.sum()>0:
    leads.loc[auto_mask,'cost'] = smart_manual_spend/auto_mask.sum()

# dispositions merge if dispo_file provided
if dispo_file:
    dispo = pd.read_csv(dispofile:=dispo_file)
    # drop return reasons if Folders col
    if 'Folders' in dispo.columns:
        dispo = dispo[~dispo['Folders'].astype(str).str.contains('!')]
    # detect phone, names
    phc = [c for c in dispo.columns if 'phone' in c.lower()]
    fnc = [c for c in dispo.columns if 'first' in c.lower()]
    lnc = [c for c in dispo.columns if 'last' in c.lower()]
    if phc:
        dispo['Phone'] = (
            dispo[phc[0]].astype(str)
                 .str.replace(r'\D','',regex=True)
                 .str[-10:]
        )
    else:
        st.warning("⚠️ No phone column in dispositions; skipping dispo merge.")
        dispo = None
    if dispo is not None:
        if fnc: dispo['first_name']=dispo[fnc[0]].astype(str).str.upper().str.strip()
        if lnc: dispo['last_name']=dispo[lnc[0]].astype(str).str.upper().str.strip()
        # clean leads
        leads['Phone']=leads['Phone'].astype(str).str.replace(r'\D','',regex=True).str[-10:]
        leads['first_name']=leads['first_name'].astype(str).str.upper().str.strip()
        leads['last_name']=leads['last_name'].astype(str).str.upper().str.strip()
        # merge
        m1 = pd.merge(leads, dispo, on='Phone', how='left', suffixes=('','_dispo'))
        if 'Milestone' in m1.columns:
            null_ph = m1['Milestone'].isna()
            fb = pd.merge(leads[null_ph], dispo, on=['first_name','last_name'], how='left', suffixes=('','_dispo'))
            leads = pd.concat([m1[~null_ph], fb], ignore_index=True)
        else:
            leads = m1
        st.success('✅ Dispositions merged.')

# merge sales
sales = parse_sales_file(sales_file)
if sales is not None:
    leads = leads.merge(sales, on='email', how='left')
    leads['Policy #'] = leads['Policy #'].fillna('')
    leads['Premium']  = leads['Premium'].fillna(0)
    leads['Items']    = leads['Items'].fillna(0)
    leads['Customer'] = leads['Customer'].fillna('')
    st.success('✅ Sales data merged.')

# ── Source Performance Tab ─────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(['📦 Source Performance','🧑 Agent Metrics','📍 ZIP Breakdown'])
with tab1:
    # flags
    if 'Milestone' in leads.columns:
        kws=['Contacted','Quoted','Not interested','Xdate','Sold']
        leads['is_connected']=leads['Milestone'].isin(kws)
        leads['is_quoted']=leads['Milestone']=='Quoted'
    else:
        leads['is_connected']=False; leads['is_quoted']=False
    # month filter
    if 'Created Date' in leads.columns:
        leads['Month']=leads['Created Date'].dt.to_period('M')
        months=sorted(leads['Month'].dropna().astype(str).unique())
        sel=st.selectbox('Filter by Month',['All']+months)
        if sel!='All': leads=leads[leads['Month'].astype(str)==sel]
    # aggregate
    df_sum=leads.groupby(['vendor','campaign']).agg(
        Premium_Earned=('Premium','sum'),
        Marketing_Spend=('cost','sum'),
        Total_Leads=('email','nunique')
    ).reset_index()
    df_sum['Spend_to_Earn']=df_sum['Marketing_Spend'].apply(lambda x: np.nan)  # placeholder
    for i,row in df_sum.iterrows():
        if row.Marketing_Spend>0:
            df_sum.at[i,'Spend_to_Earn']=row.Premium_Earned/row.Marketing_Spend
    # render cards
    for _, r in df_sum.iterrows():
        st.subheader(f"{r.vendor} - {r.campaign}")
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Premium Earned", f"${r.Premium_Earned:,.2f}")
        c2.metric("Marketing Spend", f"${r.Marketing_Spend:,.2f}")
        c3.metric("Spend to Earn", f"{r.Spend_to_Earn:.2f}")
        c4.metric("Total Leads", f"{int(r.Total_Leads)}")

# Agent Metrics Tab
def agent_metrics():
    df2=leads.copy()
    if 'Assigned To User' in df2.columns:
        # filter
        campaigns=['All']+sorted(df2['campaign'].unique())
        sel=st.selectbox('Campaign Filter',campaigns)
        if sel!='All': df2=df2[df2['campaign']==sel]
        # flags
        if 'Milestone' in df2.columns:
            df2['is_connected']=df2['Milestone'].isin(['Contacted','Quoted','Not interested','Xdate','Sold'])
            df2['is_quoted']=df2['Milestone']=='Quoted'
        else:
            df2['is_connected']=False; df2['is_quoted']=False
        agg=df2.groupby('Assigned To User').agg(
            Leads=('email','nunique'),
            Policies=('Policy #',pd.Series.nunique),
            Spend=('cost','sum'),
            Connects=('is_connected','sum'),
            Quotes=('is_quoted','sum')
        ).reset_index()
        agg['Connect Rate']=(agg.Connects/agg.Leads*100).round(1).astype(str)+'%'
        agg['Quote Rate']=(agg.Quotes/agg.Leads*100).round(1).astype(str)+'%'
        agg['Cost Per Lead']=(agg.Spend/agg.Leads).round(2)
        st.dataframe(agg)
with tab2:
    agent_metrics()

# ZIP Breakdown
with tab3:
    zc=[c for c in leads.columns if c.lower() in ('zip','zip_code')]
    if zc:
        zagg=leads.groupby(zc[0]).agg(Leads=('email','nunique'),Premium=('Premium','sum')).reset_index()
        st.bar_chart(zagg.set_index(zc[0])['Premium'])
    else:
        st.warning('No ZIP data found.')
