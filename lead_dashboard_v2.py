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
sales_file = st.sidebar.file_uploader("Sales Data (Excel)", type=["xlsx"])

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

    # Load sales data
    sales_df = pd.read_excel(sales_file, sheet_name="Sheet1")
    sales_df = sales_df.dropna(subset=["Customer"])
    sales_df["Customer"] = sales_df["Customer"].str.upper().str.strip()

    # Match Customer to merged leads
    merged_df["Customer"] = (merged_df["first_name"].fillna('') + " " + merged_df["last_name"].fillna('')).str.upper().str.strip()
    final_df = pd.merge(merged_df, sales_df, how="left", on="Customer")
    final_df["is_sold"] = final_df["Policy #"].notna()

    # Optional filters
    st.sidebar.subheader("🔍 Filter Data")
    agent_filter = st.sidebar.selectbox("Filter by Agent", options=["All"] + sorted(final_df["Assigned To User"].dropna().unique().tolist()))
    campaign_filter = st.sidebar.selectbox("Filter by Campaign", options=["All"] + sorted(final_df["campaign"].unique()))
    zip_filter = st.sidebar.selectbox("Filter by ZIP Code", options=["All"] + sorted(final_df["zip_code"].dropna().unique().astype(str)))

    filtered_df = final_df.copy()
    if agent_filter != "All":
        filtered_df = filtered_df[filtered_df["Assigned To User"] == agent_filter]
    if campaign_filter != "All":
        filtered_df = filtered_df[filtered_df["campaign"] == campaign_filter]
    if zip_filter != "All":
        filtered_df = filtered_df[filtered_df["zip_code"].astype(str) == zip_filter]

    # --- Source Performance ---
    st.header("📦 Source Performance")
    source_perf = filtered_df.groupby(["source", "campaign"]).agg(
        leads_purchased=("email", "count"),
        leads_contacted=("Milestone", lambda x: x.notna().sum()),
        leads_sold=("is_sold", "sum"),
        total_premium=("Premium", "sum"),
        total_cost=("cost", "sum")
    ).reset_index()

    source_perf["contact_rate"] = (source_perf["leads_contacted"] / source_perf["leads_purchased"]).round(2)
    source_perf["close_rate"] = (source_perf["leads_sold"] / source_perf["leads_contacted"]).replace(np.inf, 0).round(2)
    source_perf["cost_per_sale"] = (source_perf["total_cost"] / source_perf["leads_sold"]).replace(np.inf, 0).round(2)

    st.dataframe(source_perf)

    # Export button
    csv = source_perf.to_csv(index=False).encode('utf-8')
    st.download_button("📤 Export Source Data", csv, "source_performance.csv", "text/csv")

    # Chart
    st.bar_chart(source_perf.set_index("campaign")[["leads_purchased", "leads_contacted", "leads_sold"]])

    # --- Agent Performance ---
    st.header("🧑‍💼 Agent Performance")
    agent_perf = filtered_df.groupby("Assigned To User").agg(
        leads_assigned=("email", "count"),
        leads_contacted=("Milestone", lambda x: x.notna().sum()),
        policies_sold=("is_sold", "sum"),
        total_premium=("Premium", "sum")
    ).reset_index().rename(columns={"Assigned To User": "Agent"})

    agent_perf["close_rate"] = (agent_perf["policies_sold"] / agent_perf["leads_contacted"]).replace(np.inf, 0).round(2)
    st.dataframe(agent_perf)

    agent_csv = agent_perf.to_csv(index=False).encode("utf-8")
    st.download_button("📤 Export Agent Data", agent_csv, "agent_performance.csv", "text/csv")

    st.bar_chart(agent_perf.set_index("Agent")[["total_premium"]])

    # --- ZIP Code Performance ---
    st.header("📍 ZIP Code Performance")
    zip_perf = filtered_df.groupby("zip_code").agg(
        leads_purchased=("email", "count"),
        leads_contacted=("Milestone", lambda x: x.notna().sum()),
        leads_sold=("is_sold", "sum"),
        total_premium=("Premium", "sum")
    ).reset_index()

    zip_perf["conversion_rate"] = (zip_perf["leads_sold"] / zip_perf["leads_contacted"]).replace(np.inf, 0).round(2)
    st.dataframe(zip_perf)

    zip_csv = zip_perf.to_csv(index=False).encode("utf-8")
    st.download_button("📤 Export ZIP Data", zip_csv, "zip_performance.csv", "text/csv")

    st.bar_chart(zip_perf.set_index("zip_code")[["conversion_rate"]])

else:
    st.info("👈 Upload all required files to generate your dashboard.")
