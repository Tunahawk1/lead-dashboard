import streamlit as st
import pandas as pd
import numpy as np
import os
import re

st.set_page_config(page_title="📊 Lead Dashboard v5", layout="wide")
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
    parsed_leads = [parse_lead_file(f) for f in lead_files]
    all_leads = pd.concat([df for df in parsed_leads if df is not None], ignore_index=True)

    if smart_manual_spend and smart_manual_spend > 0:
        mask = all_leads["vendor"] == "SmartFinancial"
        count = mask.sum()
        if count > 0:
            per_lead_cost = smart_manual_spend / count
            all_leads.loc[mask, "cost"] = per_lead_cost

    if dispo_file:
        dispo_df = pd.read_csv(dispo_file)
        if "Primary Email Address" in dispo_df.columns:
            dispo_df["Primary Email Address"] = dispo_df["Primary Email Address"].astype(str).str.lower().str.strip()
            all_leads = pd.merge(all_leads, dispo_df, how="left", left_on="email", right_on="Primary Email Address")
        else:
            st.warning("⚠️ Disposition file is missing 'Primary Email Address' column. Skipping merge.")

    if sales_file.name.endswith(".csv"):
        sales_df = pd.read_csv(sales_file)
    else:
        sales_df = pd.read_excel(sales_file)

    sales_df["Premium"] = pd.to_numeric(sales_df["Premium"], errors="coerce")
    sales_df["Items"] = pd.to_numeric(sales_df["Items"], errors="coerce")
    sales_df["Customer"] = sales_df["Customer"].str.upper().str.strip()

    all_leads["Customer"] = (all_leads["first_name"].fillna('') + " " + all_leads["last_name"].fillna('')).str.upper().str.strip()
    merged = pd.merge(all_leads, sales_df, how="left", on="Customer")
    merged["is_sold"] = merged["Policy #"].notna()

    summary = merged.groupby(["vendor", "campaign"]).agg(
        Distinct_Customers=("Customer", pd.Series.nunique),
        Policies_Sold=("Policy #", pd.Series.nunique),
        Premium_Sum=("Premium", "sum"),
        Items_Sold=("Items", "sum"),
        Total_Leads=("email", "nunique"),
        Spend=("cost", "sum")
    ).reset_index()

    summary["Item_Close_Rate"] = summary["Items_Sold"] / summary["Total_Leads"]
    summary["Lead_Close_Rate"] = summary["Distinct_Customers"] / summary["Total_Leads"]
    summary["Policy_Close_Rate"] = summary["Policies_Sold"] / summary["Total_Leads"]
    summary["Spend_to_Earn"] = summary["Premium_Sum"] / summary["Spend"]
    summary["Cost_Per_HH"] = summary["Spend"] / summary["Distinct_Customers"]
    summary["Cost_Per_Bind"] = summary["Spend"] / summary["Policies_Sold"]
    summary["Cost_Per_Item"] = summary["Spend"] / summary["Items_Sold"]
    summary["Avg_Cost_Per_Lead"] = summary["Spend"] / summary["Total_Leads"]

    for _, row in summary.iterrows():
        st.subheader(f"📦 {row['vendor']} - {row['campaign']}")
        cols = st.columns(4)
        cols[0].metric("Total Spend", f"${row['Spend']:.2f}")
        cols[1].metric("Total Premium", f"${row['Premium_Sum']:.2f}")
        cols[2].metric("Total Leads", int(row['Total_Leads']))
        cols[3].metric("Avg Cost per Lead", f"${row['Avg_Cost_Per_Lead']:.2f}")

        st.write("---")
        kpi_cols = st.columns(5)
        kpi_cols[0].metric("Policy Close Rate", f"{row['Policy_Close_Rate']:.2%}")
        kpi_cols[1].metric("Lead Close Rate", f"{row['Lead_Close_Rate']:.2%}")
        kpi_cols[2].metric("Item Close Rate", f"{row['Item_Close_Rate']:.2%}")
        kpi_cols[3].metric("Spend to Earn", f"{row['Spend_to_Earn']:.2f}x")
        kpi_cols[4].metric("Cost per Policy", f"${row['Cost_Per_Bind']:.2f}")
        st.write("")

else:
    st.info("⬅️ Upload at least one lead CSV and the SALES DATA file to get started.")
