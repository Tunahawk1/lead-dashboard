import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import re

# ── Page Config & CSS Styling ─────────────────────────────────────────────────
st.set_page_config(page_title="📊 Lead Dashboard V10", layout="wide")
st.markdown("""
    <style>
      /* Dark sidebar */
      .css-1d391kg {background-color: #0B1F3A;}
      .css-1d391kg .css-hxt7ib {color: #FFFFFF;} /* Sidebar text */
      /* KPI card styling */
      .metric-card {
        background: #ffffff;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        padding: 1rem;
        margin-bottom: 1rem;
      }
    </style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("📁 File Uploads")
lead_files   = st.sidebar.file_uploader("Lead CSVs (Multi‑Vendor)", type="csv", accept_multiple_files=True)
sales_file   = st.sidebar.file_uploader("Sales Data (CSV/Excel)", type=["csv","xlsx"])
dispo_file   = st.sidebar.file_uploader("Disposition CSV", type="csv")
manual_spend = st.sidebar.number_input("SmartFinancial Total Spend", min_value=0.0, step=1.0)
st.sidebar.markdown("---")

# ── Parsing Helpers ──────────────────────────────────────────────────────────
def parse_lead_file(f):
    name = f.name.rsplit(".",1)[0]
    for sep in ["_","-"," "]:
        if sep in name:
            vendor,campaign = name.split(sep,1)
            break
    else:
        return None
    try:
        df = pd.read_csv(f)
    except:
        return None
    df.rename(columns=lambda c: c.strip(), inplace=True)
    # Email
    emails = [c for c in df.columns if "email" in c.lower()]
    df["email"] = df[emails[0]].astype(str).str.lower().str.strip() if emails else None
    # Cost
    df["cost"] = 0.0
    if vendor.lower()=="eq" and "cost" in df.columns:
        df["cost"] = pd.to_numeric(df["cost"], errors="coerce").fillna(0)
        df["cost"] = df["cost"].apply(lambda x: x/100 if x>100 else x)
    if vendor.lower().startswith("smartfinancial") and manual_spend>0:
        df["cost"] = manual_spend/len(df) if len(df)>0 else 0
    # Names
    firsts = [c for c in df.columns if "first" in c.lower()]
    lasts  = [c for c in df.columns if "last" in c.lower()]
    df["first_name"] = df[firsts[0]].astype(str) if firsts else None
    df["last_name"]  = df[lasts[0]].astype(str) if lasts  else None
    # Phone
    phones = [c for c in df.columns if "phone" in c.lower()]
    df["Phone"] = (
        df[phones[0]].astype(str)
          .str.replace(r"\D","",regex=True)
          .str[-10:]
    ) if phones else None
    # Created Date
    dates = [c for c in df.columns if "date" in c.lower()]
    if dates:
        df["Created Date"] = pd.to_datetime(df[dates[0]], errors="coerce")
    # Zip
    zips = [c for c in df.columns if "zip" in c.lower()]
    if zips:
        df["Zip"] = df[zips[0]]
    # Annotate
    df["vendor"]   = vendor
    df["campaign"] = campaign
    cols = ["vendor","campaign","email","first_name","last_name","cost","Phone","Created Date","Zip"]
    return df[[c for c in cols if c in df.columns]]

def parse_sales_file(f):
    try:
        df = pd.read_excel(f) if f.name.lower().endswith(("xls","xlsx")) else pd.read_csv(f)
    except:
        return None
    df.rename(columns=lambda c: c.strip(), inplace=True)
    ems = [c for c in df.columns if "email" in c.lower()]
    df["email"] = df[ems[0]].astype(str).str.lower().str.strip() if ems else None
    assigns = [c for c in df.columns if "assign" in c.lower()]
    df["Assigned To User"] = df[assigns[0]].astype(str) if assigns else None
    for col in ["Policy #","Premium","Items"]:
        if col not in df.columns:
            df[col] = 0 if col!="Policy #" else ""
    df["Premium"] = pd.to_numeric(df["Premium"], errors="coerce").fillna(0)
    df["Items"]   = pd.to_numeric(df["Items"], errors="coerce").fillna(0)
    return df[["email","Policy #","Premium","Items","Assigned To User"]]

# ── Load Data ─────────────────────────────────────────────────────────────────
if not lead_files or not sales_file:
    st.warning("Upload leads + sales data from the sidebar.")
    st.stop()
leads = pd.concat([d for d in (parse_lead_file(f) for f in lead_files) if d is not None],
                   ignore_index=True)
if leads.empty:
    st.error("No valid leads parsed. Check filenames/formats.")
    st.stop()
if "Milestone" not in leads.columns:
    leads["Milestone"] = None

# ── Merge Dispositions ────────────────────────────────────────────────────────
def merge_dispo(df, path):
    dispo = pd.read_csv(path)
    if "Folders" in dispo.columns:
        dispo = dispo[~dispo["Folders"].astype(str).str.contains("!")]
    if "Phone" in dispo.columns:
        dispo["Phone"] = (dispo["Phone"].astype(str)
                              .str.replace(r"\D","",regex=True)
                              .str[-10:])
        mp = dispo.dropna(subset=["Phone"]).drop_duplicates("Phone").set_index("Phone")["Milestone"]
        df["Milestone"] = df["Phone"].map(mp).fillna(df["Milestone"])
    return df

if dispo_file:
    leads = merge_dispo(leads, dispo_file)
    st.success("✅ Dispositions merged.")

# ── Merge Sales ───────────────────────────────────────────────────────────────
sales = parse_sales_file(sales_file)
if sales is not None:
    leads = leads.merge(sales, on="email", how="left")
    st.success("✅ Sales merged.")

# ── Flags & Month ─────────────────────────────────────────────────────────────
leads["is_connected"] = leads["Milestone"].isin(["Contacted","Quoted","Not interested","Xdate","Sold"])
leads["is_quoted"]    = leads["Milestone"]=="Quoted"
if "Created Date" in leads.columns:
    leads["Mo]()
