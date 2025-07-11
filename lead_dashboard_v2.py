import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="Lead Performance Dashboard", layout="wide")
st.title("📊 Lead Performance Dashboard v2")

# Sidebar upload interface
st.sidebar.header("📁 Upload Weekly Reports")
tier1_file = st.sidebar.file_uploader("EQ Tier 1 Leads (CSV)", type="csv")
tier2_file = st.sidebar.file_uploader("EQ Tier 2 Leads (CSV)", type="csv")
dispo_file = st.sidebar.file_uploader("Lead Dispositions (CSV)", type="csv")
sales_file = st.sidebar.file_uploader("Sales Data (CSV or Excel)", type=["csv", "xlsx"])

if tier1_file and tier2_file and dispo_file and sales_file:
    # Load and merge leads
    tier1_df = pd.read_csv(tier1_file)
    tier1_df["source"] = "EQ"
    tier1_df["campaign"] = "Tier 1"

    tier2_df = pd.read_csv(tier2_file)
    tier2_df["source"] = "EQ"
    tier2_df["campaign"] = "Tier 2"

    leads_df = pd.concat([tier1_df, tier2_df], ignore_index=True)
    leads_df["email"] = leads_df["email"].str.lower().str.strip()

    # Load dispositions
    dispo_df = pd.read_csv(dispo_file)
    dispo_df["Primary Email Address"] = dispo_df["Primary Email Address"].str.lower().str.strip()

    # Merge leads + dispositions
    merged_df = pd.merge(leads_df, dispo_df, how="left", left_on="email", right_on="Primary Email Address")

    # Load sales data (CSV or Excel auto-detect)
    if sales_file.name.endswith(".csv"):
        sales_df = pd.read_csv(sales_file, encoding="utf-8", on_bad_lines="skip")
    else:
        sales_df = pd.read_excel(sales_file, sheet_name="Sheet1")

    sales_df = sales_df.dropna(subset=["Customer"])
    sales_df["Customer"] = sales_df["Customer"].str.upper().str.strip()

    # Match Customer to merged leads
    merged_df["Customer"] = (merged_df["first_name"_]()
