import streamlit as st
import pandas as pd
import numpy as np
import os
import re

st.set_page_config(page_title="📊 Lead Dashboard v4", layout="wide")
st.title("📈 Lead Marketing & Sales Dashboard")

st.sidebar.header("📁 Upload Your Files")
lead_files = st.sidebar.file_uploader("Upload Lead CSVs (Multiple Vendors)", accept_multiple_files=True, type="csv")
sales_file = st.sidebar.file_uploader("Upload SALES DATA (CSV or Excel)", type=["csv", "xlsx"])
dispo_file = st.sidebar.file_uploader("Upload Lead Dispositions (CSV)", type="csv")
smart_manual_spend = st.sidebar.number_input("SmartFinancial Total Spend (Optional)", min_value=0.0, step=1.0)

# Normalize each vendor lead file
def parse_lead_file(uploaded_file):
    filename = uploaded_file.name.replace(".csv", "")
    vendor, campaign = filename.split("_", 1)

    try:
        df = pd.read_csv(uploaded_file)
    except pd.errors.EmptyDataError:
        st.warning(f"⚠️ File '{uploaded_file.name}' is empty or invalid and was skipped.")
        return None

    if vendor == "EQ":
        df = df.rename(columns={
            "email": "email", "cost": "cost",
            "first_name": "first_name", "last_name": "last_name"
        })
        df["cost"] = df["cost"].apply(lambda x: x / 100 if x > 100 else x)
    elif vendor == "SmartFinancial":
        df = df.rename(columns={
            "Email": "email", "First Name": "first_name", "Last Name": "last_name"
        })
        df["cost"] = 0  # placeholder to fill later
    else:
        return None

    df["vendor"] = vendor
    df["campaign"] = campaign
    df["email"] = df["email"].str.lower().str.strip()
    return df[["vendor", "campaign", "email", "first_name", "last_name", "cost"]]

if lead_files and sales_file:
    # Load and normalize all leads
    parsed_leads = [parse_lead_file(f) for f in lead_files]
    all_leads = pd.concat([df for df in parsed_leads if df is not None], ignore_index=True)

    # Apply SmartFinancial spend manually if provided
    if smart_manual_spend and smart_manual_spend > 0:
        mask = all_leads["vendor"] == "SmartFinancial"
        count = mask.sum()
        if count > 0:
            per_lead_cost = smart_manual_spend / count
            all_leads.loc[mask, "cost"] = per_lead_cost

    # Load and merge dispositions if provided
    if dispo_file:
        dispo_df = pd.read_csv(dispo_file)
        dispo_df["Primary Email Address"] = dispo_df["Primary Email Address"].str.lo