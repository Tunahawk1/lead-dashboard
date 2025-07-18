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
    filename = uploaded_file.name.rsplit(".", 1)[0]
    parts = filename.split("_", 1)
    if len(parts) != 2:
        st.warning(f"⚠️ Filename '{uploaded_file.name}' doesn't follow 'Vendor_Campaign.csv' format. Skipping.")
        return None
    vendor, campaign = parts
    try:
        df = pd.read_csv(uploaded_file)
    except pd.errors.EmptyDataError:
        st.warning(f"⚠️ File '{uploaded_file.name}' is empty or invalid and was skipped.")
        return None

    # Standardize fields per vendor
    if vendor == "EQ":
        df = df.rename(columns={
            "email": "email",
            "cost": "cost",
            "first_name": "first_name",
            "last_name": "last_name",
            "Phone": "Phone"
        })
        df["cost"] = df["cost"].apply(lambda x: x / 100 if x > 100 else x)
    elif vendor == "SmartFinancial":
        df = df.rename(columns={
            "Email": "email",
            "First Name": "first_name",
            "Last Name": "last_name",
            "Phone": "Phone"
        })
        df["cost"] = 0.0
    else:
        st.warning(f"⚠️ Unsupported vendor '{vendor}' in file '{uploaded_file.name}'. Skipping.")
        return None

    df["vendor"] = vendor
    df["campaign"] = campaign
    df["email"] = df["email"].astype(str).str.lower().str.strip()
    df["Phone"] = (
        df["Phone"].astype(str)
        .str.replace(r"\D", "", regex=True)
        .str[-10:]
    )

    cols = ["vendor", "campaign", "email", "first_name", "last_name", "cost", "Phone"]
    if "Created Date" in df.columns:
        df["Created Date"] = pd.to_datetime(df["Created Date"], errors="coerce")
        cols.append("Created Date")
    if "Zip" in df.columns or "zip" in df.columns:
        zip_col = "Zip" if "Zip" in df.columns else "zip"
        df["Zip"] = df[zip_col]
        cols.append("Zip")
    return df[cols]

# ── Helper: parse sales data ────────────────────────────────────────────────────
def parse_sales_file(uploaded_file):
    try:
        if uploaded_file.name.lower().endswith(("xlsx", "xls")):
            df = pd.read_excel(uploaded_file)
        else:
            df = pd.read_csv(uploaded_file)
    except Exception as e:
        st.warning(f"⚠️ Could not read sales file: {e}")
        return None

    df = df.rename(columns={c: c.strip() for c in df.columns})
    if "email" in df.columns:
        df["email"] = df["email"].astype(str).str.lower().str.strip()
    elif "Email" in df.columns:
        df["email"] = df["Email"].astype(str).str.lower().str.strip()
    else:
        st.warning("⚠️ No 'email' column in sales data; merging will be incomplete.")
        df["email"] = None

    for col in ["Policy #", "Premium", "Items", "Customer", "Assigned To User"]:
        if col not in df.columns:
            df[col] = np.nan

    df["Premium"] = pd.to_numeric(df["Premium"], errors="coerce").fillna(0)
    df["Items"] = pd.to_numeric(df["Items"], errors="coerce").fillna(0)
    return df[["email", "Policy #", "Premium", "Items", "Customer", "Assigned To User"]]

# ── Main processing ──────────────────────────────────────────────────────────────
if lead_files and sales_file:
    # Parse and combine leads
    parsed = [parse_lead_file(f) for f in lead_files]
    all_leads = pd.concat([df for df in parsed if df is not None], ignore_index=True)

    # SmartFinancial manual spend adjustment
    if smart_manual_spend > 0:
        mask = all_leads["vendor"] == "SmartFinancial"
        count = mask.sum()
        if count > 0:
            per_lead_cost = smart_manual_spend / count
            all_leads.loc[mask, "cost"] = per_lead_cost

    # Merge dispositions
    if dispo_file:
        dispo_df = pd.read_csv(dispo_file)
        if "Folders" in dispo_df.columns:
            dispo_df = dispo_df[~dispo_df["Folders"].astype(str).str.contains("!")]
        dispo_df["Phone"] = (
            dispo_df["Phone"].astype(str)
            .str.replace(r"\D", "", regex=True)
            .str[-10:]
        )
        dispo_df["first_name"] = dispo_df["first_name"].astype(str).str.upper().str.strip()
        dispo_df["last_name"] = dispo_df["last_name"].astype(str).str.upper().str.strip()

        all_leads["Phone"] = (
            all_leads["Phone"].astype(str)
            .str.replace(r"\D", "", regex=True)
            .str[-10:]
        )
        all_leads["first_name"] = all_leads["first_name"].astype(str).str.upper().str.strip()
        all_leads["last_name"] = all_leads["last_name"].astype(str).str.upper().str.strip()

        merged = pd.merge(
            all_leads,
            dispo_df,
            on="Phone",
            how="left",
            suffixes=("", "_dispo")
        )
        if "Milestone" in merged.columns:
            no_phone = merged["Milestone"].isna()
            fallback = pd.merge(
                all_leads[no_phone],
                dispo_df,
                on=["first_name", "last_name"],
                how="left",
                suffixes=("", "_dispo")
            )
            all_leads = pd.concat([merged[~no_phone], fallback], ignore_index=True)
        else:
            all_leads = merged
        st.success("✅ Dispositions matched by phone and name; return reasons excluded.")

    # Merge sales data
    sales_df = parse_sales_file(sales_file)
    if sales_df is not None:
        all_leads = pd.merge(all_leads, sales_df, on="email", how="left")
        all_leads["Policy #"] = all_leads["Policy #"].fillna("")
        all_leads["Premium"] = all_leads["Premium"].fillna(0)
        all_leads["Items"] = all_leads["Items"].fillna(0)
        all_leads["Customer"] = all_leads["Customer"].fillna("")
        st.success("✅ Sales data merged by email.")

    # ── Tabs for performance ─────────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs([
        "📦 Source Performance",
        "🧑 Agent Metrics",
        "📍 ZIP Breakdown"
    ])

    # Tab 1: Source Performance
    with tab1:
        if "Milestone" in all_leads.columns:
            keywords = ["Contacted", "Quoted", "Not interested", "Xdate", "Sold"]
            all_leads["is_connected"] = all_leads["Milestone"].isin(keywords)
            all_leads["is_quoted"] = all_leads["Milestone"] == "Quoted"
        else:
            all_leads["is_connected"] = False
            all_leads["is_quoted"] = False

        if "Created Date" in all_leads.columns:
            all_leads["Month"] = all_leads["Created Date"].dt.to_period("M")
            months = sorted(all_leads["Month"].dropna().astype(str).unique().tolist())
            selected = st.selectbox("Filter by Month", ["All"] + months)
            if selected != "All":
                all_leads = all_leads[all_leads["Month"].astype(str) == selected]

        summary = all_leads.groupby(["vendor", "campaign"]).agg(
            Distinct_Customers=("email", pd.Series.nunique),
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
