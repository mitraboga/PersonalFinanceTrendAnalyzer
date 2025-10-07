"""
Streamlit dashboard for Personal Finance Trend Analyzer.

What this app does:
1) Ingest your bank/UPI exports (CSV/Excel) and normalize columns.
2) Clean & enrich data (dates, signed amounts, month/year).
3) Categorize spending using rules (config/category_rules.yml) and optional ML.
4) Visualize category spend, monthly trends, and forecast the next N months.

How to run:
    streamlit run app.py
"""

from __future__ import annotations
import io
import os
import pandas as pd
import streamlit as st

# --- Internal pipeline imports (our package) ---
from pipeline.ingestion import load_transactions
from pipeline.cleaning import clean_transactions
from pipeline.categorize import categorize, load_rules
from pipeline.forecasting import forecast_monthly_spend
from pipeline.visualize import category_spend_bar, monthly_trend_line, forecast_line


# ---------- Page config & header ----------
st.set_page_config(page_title="Personal Finance Trend Analyzer", layout="wide")
st.title("💸 Personal Finance Trend Analyzer")

st.caption(
    "Upload your bank/UPI export (CSV or Excel). We'll normalize, categorize, "
    "plot trends, and forecast the next few months of spending. "
    "Rules live in `config/category_rules.yml`; an optional ML model can be trained later."
)


# ---------- Sidebar: instructions & options ----------
with st.sidebar:
    st.header("How to use")
    st.markdown(
        """
        1. **Upload** a CSV/Excel *or* click **Use sample data**.
        2. Review the **processed table** (after cleaning & categorization).
        3. Explore **KPIs** and **interactive charts**.
        4. Adjust **forecast horizon** and inspect predictions.
        5. *(Optional)* Download your processed CSV.

        **Tip:** Improve accuracy by adding merchant keywords to
        `config/category_rules.yml`. When ready, label a few examples and train the ML model.
        """
    )
    st.divider()
    st.subheader("Settings")
    show_raw = st.checkbox("Show processed data preview", value=False)
    show_rules = st.checkbox("Show active category rules", value=False)


# ---------- File input ----------
uploaded = st.file_uploader("Upload CSV/Excel", type=["csv", "xlsx", "xls"])
use_sample = st.button("Use sample data", help="Loads data/sample_transactions.csv")

# Safety: ensure we only proceed once we have data
if not uploaded and not use_sample:
    st.info("👉 Upload a file or click **Use sample data** to try the dashboard.")
    st.stop()

# ---------- Ingest ----------
# Notes:
# - For uploads, we write to a temp file so `pd.read_excel` can work.
# - The ingestion module standardizes to columns: date, description, amount, type, account, mode
try:
    if use_sample:
        input_path = "data/sample_transactions.csv"
        raw_df = load_transactions(input_path)
    else:
        tmp_path = f"/tmp/{uploaded.name}"
        with open(tmp_path, "wb") as f:
            f.write(uploaded.getvalue())
        raw_df = load_transactions(tmp_path)
except Exception as e:
    st.error(f"Could not read the file. Please check the format. Details: {e}")
    st.stop()

# ---------- Clean & categorize ----------
df = clean_transactions(raw_df)
df = categorize(df)

# Optional: show a quick peek of the processed data
if show_raw:
    with st.expander("Processed data (first 100 rows)"):
        st.dataframe(df.head(100), use_container_width=True)

# Optional: display the active keyword rules so users can tune them
if show_rules:
    rules = load_rules()
    with st.expander("Active category rules (from config/category_rules.yml)"):
        if rules:
            st.write(rules)
        else:
            st.info("No rules found. Add some keywords to config/category_rules.yml.")


# ---------- KPIs ----------
# - Spend = negative signed_amount (we display positive magnitude)
# - Income = positive signed_amount
total_spend = (-df.loc[df["signed_amount"] < 0, "signed_amount"].sum())
total_income = df.loc[df["signed_amount"] > 0, "signed_amount"].sum()
months = df["date"].dt.to_period("M").nunique()

c1, c2, c3 = st.columns(3)
c1.metric("Total Spend (₹)", f"{total_spend:,.0f}")
c2.metric("Total Income (₹)", f"{total_income:,.0f}")
c3.metric("Months Covered", int(months))


# ---------- Charts: category bar + monthly trend ----------
left, right = st.columns(2)

with left:
    st.subheader("Category breakdown")
    try:
        st.plotly_chart(category_spend_bar(df), use_container_width=True)
    except Exception as e:
        st.warning(f"Could not render category chart: {e}")

with right:
    st.subheader("Monthly spend trend")
    try:
        st.plotly_chart(monthly_trend_line(df), use_container_width=True)
    except Exception as e:
        st.warning(f"Could not render monthly trend chart: {e}")


# ---------- Forecast ----------
st.subheader("🔮 Spend forecast")
periods = st.slider("Forecast months", min_value=3, max_value=12, value=6, help="How many months ahead to predict.")
try:
    hist, fc = forecast_monthly_spend(df, periods=periods)
    st.plotly_chart(forecast_line(hist, fc), use_container_width=True)

    # Present forecast table in a friendly way
    fc_df = pd.DataFrame(
        {"Month": fc.index.strftime("%Y-%m"), "Forecast Spend (₹)": fc.values}
    )
    st.dataframe(fc_df, use_container_width=True)
except Exception as e:
    st.warning(f"Forecast unavailable (fell back to defaults or encountered an error): {e}")


# ---------- Download processed CSV ----------
# Let users download the cleaned + categorized data for their own analysis/records
st.subheader("📥 Export")
processed_csv = df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Download processed CSV",
    data=processed_csv,
    file_name="processed_transactions.csv",
    mime="text/csv",
    help="This contains standardized columns + signed_amount + category."
)

# ---------- Footer note ----------
st.caption(
    "Tip: Add/adjust keywords in `config/category_rules.yml` to improve rule-based tagging. "
    "When you have labeled examples, train the classifier with "
    "`python scripts/train_classifier.py --input data/labeled_samples.csv`."
)
