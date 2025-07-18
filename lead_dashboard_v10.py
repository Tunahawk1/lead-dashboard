import streamlit as st
import pandas as pd
import numpy as np
import os
import re
import altair as alt

st.set_page_config(page_title="📊 Lead Dashboard v10", layout="wide")

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
        df = df.rename(columns={"email": "email", "cost": "cost", "first_name": "first_name", "last_name": "last_name", "Phone": "Phone"})
        df["cost"] = df["cost"].apply(lambda x: x / 100 if x > 100 else x)
    elif vendor == "SmartFinancial":
        df = df.rename(columns={"Email": "email", "First Name": "first_name", "Last Name": "last_name", "Phone": "Phone"})
        df["cost"] = 0
    else:
        return None

    df["vendor"] = vendor
    df["campaign"] = campaign
    df["email"] = df["email"].str.lower().str.strip()
    df["Phone"] = df["Phone"].astype(str).str.replace(r'\D', '', regex=True).str[-10:]
    return df[["vendor", "campaign", "email", "first_name", "last_name", "cost", "Phone"]]

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

        if "Folders" in dispo_df.columns:
            dispo_df = dispo_df[~dispo_df["Folders"].astype(str).str.contains("!")]

        dispo_df["Phone"] = dispo_df["Phone"].astype(str).str.replace(r'\D', '', regex=True).str[-10:]
        dispo_df["first_name"] = dispo_df["first_name"].astype(str).str.upper().str.strip()
        dispo_df["last_name"] = dispo_df["last_name"].astype(str).str.upper().str.strip()

        all_leads["Phone"] = all_leads["Phone"].astype(str).str.replace(r'\D', '', regex=True).str[-10:]
        all_leads["first_name"] = all_leads["first_name"].astype(str).str.upper().str.strip()
        all_leads["last_name"] = all_leads["last_name"].astype(str).str.upper().str.strip()

        merged_dispo = pd.merge(all_leads, dispo_df, on="Phone", how="left", suffixes=("", "_dispo"))

        no_phone_match = merged_dispo["Milestone"].isna()
        fallback = pd.merge(
            all_leads[no_phone_match],
            dispo_df,
            on=["first_name", "last_name"],
            how="left",
            suffixes=("", "_dispo")
        )

        all_leads = pd.concat([merged_dispo[~no_phone_match], fallback], ignore_index=True)

    st.success("✅ Dispositions matched by phone and name; returns excluded.")

tab1, tab2, tab3 = st.tabs(["📦 Source Performance", "🧑 Agent Metrics", "📍 ZIP Breakdown"])

with tab1:
    if "Milestone" in all_leads.columns:
        connect_keywords = ["Contacted", "Quoted", "Not interested", "Xdate", "Sold"]
        all_leads["is_connected"] = all_leads["Milestone"].isin(connect_keywords)
        all_leads["is_quoted"] = all_leads["Milestone"] == "Quoted"
    else:
        all_leads["is_connected"] = False
        all_leads["is_quoted"] = False

    if "Created Date" in all_leads.columns:
        all_leads["Created Date"] = pd.to_datetime(all_leads["Created Date"], errors="coerce")
        all_leads["Month"] = all_leads["Created Date"].dt.to_period("M")
        month_options = ["All"] + sorted(all_leads["Month"].dropna().astype(str).unique().tolist())
        selected_month = st.selectbox("Filter by Month", options=month_options)
        if selected_month != "All":
            all_leads = all_leads[all_leads["Month"].astype(str) == selected_month]

    summary = all_leads.groupby(["vendor", "campaign"]).agg(
        Distinct_Customers=("Customer", pd.Series.nunique),
        Policies_Sold=("Policy #", pd.Series.nunique),
        Premium_Sum=("Premium", "sum"),
        Items_Sold=("Items", "sum"),
        Total_Leads=("email", "nunique"),
        Spend=("cost", "sum"),
        Connects=("is_connected", "sum"),
        Quotes=("is_quoted", "sum")
    ).reset_index()

    summary["Item_Close_Rate"] = summary["Items_Sold"] / summary["Total_Leads"]
    summary["Lead_Close_Rate"] = summary["Distinct_Customers"] / summary["Total_Leads"]
    summary["Policy_Close_Rate"] = summary["Policies_Sold"] / summary["Total_Leads"]
    summary["Connect Rate"] = (summary["Connects"] / summary["Total_Leads"] * 100).round(1).astype(str) + "%"
    summary["Quote Rate"] = (summary["Quotes"] / summary["Total_Leads"] * 100).round(1).astype(str) + "%"
    summary["Spend_to_Earn"] = summary["Premium_Sum"] / summary["Spend"]
    summary["Cost_Per_HH"] = summary["Spend"] / summary["Distinct_Customers"]
    summary["Cost_Per_Bind"] = summary["Spend"] / summary["Policies_Sold"]
    summary["Cost_Per_Item"] = summary["Spend"] / summary["Items_Sold"]
    summary["Avg_Cost_Per_Lead"] = summary["Spend"] / summary["Total_Leads"]

    color_map = {
        'EQ': '#2274A5',
        'SmartFinancial': '#F75C03',
        'QuoteWizard': '#F1C40F',
        'EverQuote': '#D90368'
    }

    for _, row in summary.iterrows():
        vendor_color = color_map.get(row['vendor'], '#00CC66')
        st.markdown(f"""
            <div class=\"metric-card\" style=\"border-left: 10px solid {vendor_color};\">
            <div class=\"metric-title\">📦 {row['vendor']} - {row['campaign']}</div>
            <div style=\"display: flex; gap: 2rem;\">
                <div><strong>Total Spend</strong><br>${row['Spend']:.2f}</div>
                <div><strong>Total Premium</strong><br>${row['Premium_Sum']:.2f}</div>
                <div><strong>Total Leads</strong><br>{int(row['Total_Leads'])}</div>
                <div><strong>Avg Cost per Lead</strong><br>${row['Avg_Cost_Per_Lead']:.2f}</div>
            </div>
            <hr style=\"margin:1rem 0;\">
            <div style=\"display: flex; gap: 2rem;\">
                <div><strong>Policy Close Rate</strong><br>{row['Policy_Close_Rate']:.2%}</div>
                <div><strong>Lead Close Rate</strong><br>{row['Lead_Close_Rate']:.2%}</div>
                <div><strong>Item Close Rate</strong><br>{row['Item_Close_Rate']:.2%}</div>
                <div><strong>Connect Rate</strong><br>{row['Connect Rate']}</div>
                <div><strong>Quote Rate</strong><br>{row['Quote Rate']}</div>
                <div><strong>Spend to Earn</strong><br>{row['Spend_to_Earn']:.2f}x</div>
                <div><strong>Cost per Policy</strong><br>${row['Cost_Per_Bind']:.2f}</div>
            </div>
            </div>
        """, unsafe_allow_html=True)

with tab2:
    if "Assigned To User" in all_leads.columns:
        source_filter = st.selectbox("Filter by Source/Campaign", options=["All"] + sorted(all_leads["campaign"].dropna().unique().tolist()))
        filtered = all_leads.copy()
        if source_filter != "All":
            filtered = filtered[filtered["campaign"] == source_filter]

        connect_keywords = ["Contacted", "Quoted", "Not interested", "Xdate", "Sold"]
        filtered["is_connected"] = filtered["Milestone"].isin(connect_keywords)
        filtered["is_quoted"] = filtered["Milestone"] == "Quoted"

        agent_summary = filtered.groupby("Assigned To User").agg(
            Leads=("email", "nunique"),
            Policies=("Policy #", pd.Series.nunique),
            Premium=("Premium", "sum"),
            Items=("Items", "sum"),
            Spend=("cost", "sum"),
            Connects=("is_connected", "sum"),
            Quotes=("is_quoted", "sum")
        ).reset_index()

        agent_summary["Connect Rate"] = (agent_summary["Connects"] / agent_summary["Leads"] * 100).round(1).astype(str) + "%"
        agent_summary["Quote Rate"] = (agent_summary["Quotes"] / agent_summary["Leads"] * 100).round(1).astype(str) + "%"
        agent_summary["Lead Close Rate"] = (agent_summary["Policies"] / agent_summary["Leads"] * 100).round(1).astype(str) + "%"
        agent_summary["Warm Close Rate"] = (agent_summary["Policies"] / agent_summary["Quotes"]).replace([np.inf, np.nan], 0) * 100
        agent_summary["Warm Close Rate"] = agent_summary["Warm Close Rate"].round(1).astype(str) + "%"
        agent_summary["Cost Per Lead"] = (agent_summary["Spend"] / agent_summary["Leads"]).round(2)
        agent_summary["Spend to Earn"] = (agent_summary["Premium"] / agent_summary["Spend"]).replace([np.inf, np.nan], 0).round(2)

        sort_col = st.selectbox("Sort table by column", options=agent_summary.columns.tolist())
        agent_summary = agent_summary.sort_values(by=sort_col, ascending=False)

        st.subheader("Agent Performance")
        st.dataframe(agent_summary)

with tab3:
    zip_col = None
    for col in all_leads.columns:
        if col.strip().lower() in ["zip", "zip_code"]:
            zip_col = col
            break

    if zip_col:
        zip_summary = all_leads.groupby(zip_col).agg(
            Leads=("email", "nunique"),
            Policies=("Policy #", pd.Series.nunique),
            Premium=("Premium", "sum"),
            Spend=("cost", "sum")
        ).reset_index()
        st.subheader("ZIP Code Performance")
        st.bar_chart(zip_summary.set_index(zip_col)["Premium"])
    else:
        st.warning("No ZIP code data found. Please check your lead file for a 'Zip' or 'Zip_Code' column.")