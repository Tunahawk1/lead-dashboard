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
    filename = uploaded_file.name.rsplit('.', 1)[0]
    # Determine vendor and campaign from filename
    if '_' in filename:
        parts = filename.split('_', 1)
    elif '-' in filename:
        parts = filename.split('-', 1)
    elif ' ' in filename:
        parts = filename.split(' ', 1)
    else:
        st.warning(f"⚠️ Filename '{uploaded_file.name}' doesn't follow 'vendor_separators_campaign' format. Skipping.")
        return None
    vendor, campaign = parts

    try:
        df = pd.read_csv(uploaded_file)
    except pd.errors.EmptyDataError:
        st.warning(f"⚠️ File '{uploaded_file.name}' is empty or invalid and was skipped.")
        return None

    # Vendor-specific parsing
    if vendor == 'EQ':
        df = df.rename(columns={
            'email': 'email',
            'cost': 'cost',
            'first_name': 'first_name',
            'last_name': 'last_name',
            'Phone': 'Phone'
        })
        df['email'] = df['email'].astype(str).str.lower().str.strip()
        df['cost'] = df['cost'].apply(lambda x: x/100 if x>100 else x)
        df['first_name'] = df['first_name'].astype(str)
        df['last_name'] = df['last_name'].astype(str)
        df['Phone'] = (
            df['Phone'].astype(str)
              .str.replace(r'\D', '', regex=True)
              .str[-10:]
        )
    elif vendor == 'SmartFinancial':
        df = df.rename(columns={
            'Email': 'email',
            'First Name': 'first_name',
            'Last Name': 'last_name',
            'Phone': 'Phone'
        })
        df['email'] = df['email'].astype(str).str.lower().str.strip()
        df['cost'] = 0.0
        df['first_name'] = df['first_name'].astype(str)
        df['last_name'] = df['last_name'].astype(str)
        df['Phone'] = (
            df['Phone'].astype(str)
              .str.replace(r'\D', '', regex=True)
              .str[-10:]
        )
    else:
        # Generic parsing for other vendors
        df.rename(columns={c: c.strip() for c in df.columns}, inplace=True)
        # Email
        email_cols = [c for c in df.columns if c.lower()=='email']
        if email_cols:
            df['email'] = df[email_cols[0]].astype(str).str.lower().str.strip()
        else:
            st.warning(f"⚠️ No 'email' column found in {uploaded_file.name}.")
            df['email'] = None
        # Cost
        cost_cols = [c for c in df.columns if c.lower()=='cost']
        if cost_cols:
            df['cost'] = pd.to_numeric(df[cost_cols[0]], errors='coerce').fillna(0)
        else:
            df['cost'] = 0.0
        # Names
        first_cols = [c for c in df.columns if 'first' in c.lower()]
        last_cols = [c for c in df.columns if 'last' in c.lower()]
        df['first_name'] = df[first_cols[0]].astype(str) if first_cols else None
        df['last_name'] = df[last_cols[0]].astype(str) if last_cols else None
        # Phone
        phone_cols = [c for c in df.columns if 'phone' in c.lower()]
        if phone_cols:
            df['Phone'] = (
                df[phone_cols[0]].astype(str)
                  .str.replace(r'\D', '', regex=True)
                  .str[-10:]
            )
        else:
            df['Phone'] = None

    # Annotate vendor & campaign
    df['vendor'] = vendor
    df['campaign'] = campaign

    # Preserve Created Date and Zip if present
    cols = ['vendor','campaign','email','first_name','last_name','cost','Phone']
    if 'Created Date' in df.columns:
        df['Created Date'] = pd.to_datetime(df['Created Date'], errors='coerce')
        cols.append('Created Date')
    if 'Zip' in df.columns or 'zip' in df.columns:
        zip_col = 'Zip' if 'Zip' in df.columns else 'zip'
        df['Zip'] = df[zip_col]
        cols.append('Zip')

    return df[cols]

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

    df.rename(columns={c:c.strip() for c in df.columns}, inplace=True)
    if 'email' in df.columns:
        df['email'] = df['email'].astype(str).str.lower().str.strip()
    elif 'Email' in df.columns:
        df['email'] = df['Email'].astype(str).str.lower().str.strip()
    else:
        st.warning("⚠️ No 'email' column in sales data; merging will be incomplete.")
        df['email'] = None

    for col in ['Policy #','Premium','Items','Customer','Assigned To User']:
        if col not in df.columns:
            df[col] = np.nan

    df['Premium'] = pd.to_numeric(df['Premium'], errors='coerce').fillna(0)
    df['Items']   = pd.to_numeric(df['Items'], errors='coerce').fillna(0)
    return df[['email','Policy #','Premium','Items','Customer','Assigned To User']]

# ── Main processing ──────────────────────────────────────────────────────────────
if lead_files and sales_file:
    # Parse and combine leads
    parsed = [parse_lead_file(f) for f in lead_files]
    valid_dfs = [df for df in parsed if df is not None]
    if not valid_dfs:
        st.warning("⚠️ No valid lead files parsed. Check filenames/formats.")
        st.stop()
    all_leads = pd.concat(valid_dfs, ignore_index=True)

    # SmartFinancial spend adjustment
    if smart_manual_spend > 0:
        mask = all_leads['vendor']=='SmartFinancial'
        cnt = mask.sum()
        if cnt>0:
            all_leads.loc[mask,'cost'] = smart_manual_spend/cnt

    # Merge dispositions
    if dispo_file:
        dispo_df = pd.read_csv(dispo_file)
        if 'Folders' in dispo_df.columns:
            dispo_df = dispo_df[~dispo_df['Folders'].astype(str).str.contains('!')]
        dispo_df['Phone'] = (
            dispo_df['Phone'].astype(str)
                      .str.replace(r'\D','',regex=True)
                      .str[-10:]
        )
        dispo_df['first_name'] = dispo_df['first_name'].astype(str).str.upper().str.strip()
        dispo_df['last_name']  = dispo_df['last_name'].astype(str).str.upper().str.strip()

        all_leads['Phone']      = all_leads['Phone'].astype(str).str.replace(r'\D','',regex=True).str[-10:]
        all_leads['first_name']= all_leads['first_name'].astype(str).str.upper().str.strip()
        all_leads['last_name'] = all_leads['last_name'].astype(str).str.upper().str.strip()

        merged = pd.merge(all_leads,dispo_df,on='Phone',how='left',suffixes=('','_dispo'))
        if 'Milestone' in merged.columns:
            no_ph = merged['Milestone'].isna()
            fallback = pd.merge(
                all_leads[no_ph],dispo_df,on=['first_name','last_name'],how='left',suffixes=('','_dispo')
            )
            all_leads = pd.concat([merged[~no_ph],fallback],ignore_index=True)
        else:
            all_leads = merged
        st.success("✅ Dispositions matched; return reasons excluded.")

    # Merge sales data
    sales_df = parse_sales_file(sales_file)
    if sales_df is not None:
        all_leads = pd.merge(all_leads,sales_df,on='email',how='left')
        all_leads['Policy #'] = all_leads['Policy #'].fillna('')
        all_leads['Premium']  = all_leads['Premium'].fillna(0)
        all_leads['Items']    = all_leads['Items'].fillna(0)
        all_leads['Customer'] = all_leads['Customer'].fillna('')
        st.success("✅ Sales data merged.")

    # Tabs
    tab1,tab2,tab3 = st.tabs(['📦 Source Performance','🧑 Agent Metrics','📍 ZIP Breakdown'])

    # Source Performance
    with tab1:
        if 'Milestone' in all_leads.columns:
            kw = ['Contacted','Quoted','Not interested','Xdate','Sold']
            all_leads['is_connected']=all_leads['Milestone'].isin(kw)
            all_leads['is_quoted']=all_leads['Milestone']=='Quoted'
        else:
            all_leads['is_connected']=False
            all_leads['is_quoted']=False

        if 'Created Date' in all_leads.columns:
            all_leads['Month'] = all_leads['Created Date'].dt.to_period('M')
            mons = sorted(all_leads['Month'].dropna().astype(str).unique())
            sel = st.selectbox('Filter by Month', ['All']+mons)
            if sel!='All': all_leads=all_leads[all_leads['Month'].astype(str)==sel]

        summary=all_leads.groupby(['vendor','campaign']).agg(
            Distinct_Customers=('email',pd.Series.nunique),
            Policies_Sold=('Policy #',pd.Series.nunique),
            Premium_Sum=('Premium','sum'),
            Items_Sold=('Items','sum'),
            Total_Leads=('email','nunique'),
            Spend=('cost','sum'),
            Connects=('is_connected','sum'),
            Quotes=('is_quoted','sum')
        ).reset_index()

        # Calculate rates/ratios
        summary['CT'] = (summary['Connects']/summary['Total_Leads']*100).round(1).astype(str)+'%'
        summary['QR'] = (summary['Quotes']/summary['Total_Leads']*100).round(1).astype(str)+'%'
        summary['Avg_CPL']=summary['Spend']/summary['Total_Leads']
        summary['Spend_to_Earn']=summary['Premium_Sum']/summary['Spend']
        summary['Cost_per_Bind']=summary['Spend']/summary['Policies_Sold']

        colors={'EQ':'#2274A5','SmartFinancial':'#F75C03','QuoteWizard':'#F1C40F','EverQuote':'#D90368'}
        for _,r in summary.iterrows():
            col=colors.get(r['vendor'],'#00CC66')
            st.markdown(f"""
<div style=\"border-left:10px solid {col};padding:0.5rem;\">**{r['vendor']} - {r['campaign']}**  
- Leads: {int(r['Total_Leads'])}  
- Spend: ${r['Spend']:.2f}  
- Avg CPL: ${r['Avg_CPL']:.2f}  
- CT: {r['CT']}  QR: {r['QR']}  
- Spend→Earn: {r['Spend_to_Earn']:.1f}x  
- Cost/Bind: ${r['Cost_per_Bind']:.2f}
</div>
""",unsafe_allow_html=True)

    # Agent Metrics
    with tab2:
        if 'Assigned To User' in all_leads.columns:
            df2=all_leads.copy()
            s=st.selectbox('Filter by Campaign',options=['All']+sorted(df2['campaign'].unique()))
            if s!='All': df2=df2[df2['campaign']==s]
            df2['is_connected']=df2['Milestone'].isin(['Contacted','Quoted','Not interested','Xdate','Sold']) if 'Milestone' in df2.columns else False
            df2['is_quoted']=df2['Milestone']=='Quoted' if 'Milestone' in df2.columns else False
            ag= df2.groupby('Assigned To User').agg(
                Leads=('email','nunique'),Policies=('Policy #',pd.Series.nunique),
                Premium=('Premium','sum'),Items=('Items','sum'),Spend=('cost','sum'),
                Connects=('is_connected','sum'),Quotes=('is_quoted','sum')
            ).reset_index()
            ag['CT']=(ag['Connects']/ag['Leads']*100).round(1).astype(str)+'%'
            ag['QR']=(ag['Quotes']/ag['Leads']*100).round(1).astype(str)+'%'
            ag['CPL']=(ag['Spend']/ag['Leads']).round(2)
            st.dataframe(ag.sort_values('Leads',ascending=False))

    # ZIP Breakdown
    with tab3:
        zc=[c for c in all_leads.columns if c.lower()=='zip' or c.lower()=='zip_code']
        if zc:
            zb=all_leads.groupby(zc[0]).agg(Leads=('email','nunique'),Premium=('Premium','sum'),Spend=('cost','sum')).reset_index()
            st.bar_chart(zb.set_index(zc[0])['Premium'])
        else:
            st.warning('No ZIP data found.')

else:
    st.info('📌 Upload both lead files and sales data to populate dashboard.')
