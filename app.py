"""
Streamlit dashboard for Personal Finance Trend Analyzer.

Now with:
- Budgets & alerts (total + per-category caps)
- 'This month vs 3-month average' comparison card
- Cross-platform upload handling (tempfile)

Run:
    streamlit run app.py
"""
from __future__ import annotations
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from pipeline.ingestion import load_transactions
from pipeline.cleaning import clean_transactions
from pipeline.categorize import categorize, load_rules
from pipeline.forecasting import forecast_monthly_spend
from pipeline.visualize import category_spend_bar, monthly_trend_line, forecast_line
from pipeline.budget import BudgetConfig, monthly_total_spend, build_alerts

# ---------- Page config ----------
st.set_page_config(page_title="Personal Finance Trend Analyzer", layout="wide")
st.title("💸 Personal Finance Trend Analyzer")
st.caption(
    "Upload bank/UPI CSV or Excel → normalize, categorize, visualize, and forecast. "
    "Now with budgets, per-category caps, and variance vs 3-month average."
)

# ---------- Sidebar ----------
with st.sidebar:
    st.header("How to use")
    st.markdown(
        """
        1) Upload a CSV/Excel **or** click **Use sample data**  
        2) Review processed table (optional)  
        3) Explore KPIs & charts  
        4) Adjust **forecast months**  
        5) Configure budgets in `config/budgets.yml`
        """
    )
    st.divider()
    show_raw = st.checkbox("Show processed data preview", value=False)
    show_rules = st.checkbox("Show active category rules", value=False)

# ---------- File input ----------
uploaded = st.file_uploader("Upload CSV/Excel", type=["csv", "xlsx", "xls"])
use_sample = st.button("Use sample data")

if not uploaded and not use_sample:
    st.info("👉 Upload a file or click **Use sample data** to try the dashboard.")
    st.stop()

# ---------- Ingest ----------
try:
    if use_sample:
        input_path = "data/sample_transactions.csv"
        raw_df = load_transactions(input_path)
    else:
        tmp_path = Path(tempfile.gettempdir()) / uploaded.name
        tmp_path.write_bytes(uploaded.getvalue())
        raw_df = load_transactions(str(tmp_path))
except Exception as e:
    st.error(f"Could not read the file. Details: {e}")
    st.stop()

# ---------- Clean & categorize ----------
df = clean_transactions(raw_df)
df = categorize(df)

# ---------- Optional raw preview ----------
if show_raw:
    with st.expander("Processed data (first 100 rows)"):
        st.dataframe(df.head(100), use_container_width=True)

# ---------- Optional rules view ----------
if show_rules:
    with st.expander("Active category rules"):
        st.write(load_rules())

# ---------- KPIs ----------
total_spend = (-df.loc[df["signed_amount"] < 0, "signed_amount"].sum())
total_income = df.loc[df["signed_amount"] > 0, "signed_amount"].sum()
months = df["date"].dt.to_period("M").nunique()

c1, c2, c3 = st.columns(3)
c1.metric("Total Spend (₹)", f"{total_spend:,.0f}")
c2.metric("Total Income (₹)", f"{total_income:,.0f}")
c3.metric("Months Covered", int(months))

# ---------- Variance: This month vs 3-month average ----------
# Use monthly positive spend series
m_series = monthly_total_spend(df)  # Index = month start, values = positive spend
if len(m_series) >= 1:
    this_month_spend = float(m_series.iloc[-1])
    trailing_avg = float(m_series.iloc[:-1].tail(3).mean()) if len(m_series) > 1 else 0.0
    delta = this_month_spend - trailing_avg
    delta_pct = (delta / trailing_avg * 100.0) if trailing_avg > 0 else 0.0

    c4, c5 = st.columns(2)
    c4.metric("This Month Spend (₹)", f"{this_month_spend:,.0f}", delta=f"{delta:,.0f} vs 3-mo avg")
    c5.metric("3-Month Average (₹)", f"{trailing_avg:,.0f}", delta=f"{delta_pct:+.1f}% vs 3-mo avg")
else:
    st.info("Not enough data to compute monthly variance.")

# ---------- Charts ----------
left, right = st.columns(2)
with left:
    st.subheader("Category breakdown")
    st.plotly_chart(category_spend_bar(df), use_container_width=True)
with right:
    st.subheader("Monthly spend trend")
    st.plotly_chart(monthly_trend_line(df), use_container_width=True)

# ---------- Forecast ----------
st.subheader("🔮 Spend forecast")
periods = st.slider("Forecast months", min_value=3, max_value=12, value=6)
hist, fc = forecast_monthly_spend(df, periods=periods)
st.plotly_chart(forecast_line(hist, fc), use_container_width=True)
st.dataframe(pd.DataFrame({"Month": fc.index.strftime("%Y-%m"), "Forecast Spend (₹)": fc.values}),
             use_container_width=True)

# ---------- Budgets & Alerts ----------
st.subheader("🚨 Budgets & Alerts")
cfg = BudgetConfig.load()
alerts_df = build_alerts(df, cfg)

from pipeline.visualize import budget_donut, category_utilization_df
from pipeline.notify import send_alerts as _send_alerts

if alerts_df.empty:
    st.info("No caps configured or no spend this month. Add caps in `config/budgets.yml`.")
else:
    # Donut for total budget (if configured)
    total_row = alerts_df[alerts_df["scope"] == "TOTAL"].head(1)
    if not total_row.empty and pd.notna(total_row.iloc[0]["cap"]):
        tcap = float(total_row.iloc[0]["cap"])
        tspend = float(total_row.iloc[0]["spend"])
        st.plotly_chart(budget_donut(tcap, tspend), use_container_width=True)

    # Category progress bars
    st.markdown("**Category caps progress**")
    cat_df = category_utilization_df(alerts_df)
    if cat_df.empty:
        st.caption("No per-category caps set.")
    else:
        for _, r in cat_df.iterrows():
            label = f"{r['category']} — ₹{r['spend']:,.0f} / ₹{r['cap']:,.0f} ({r['pct']:.0%}) [{r['status']}]"
            st.write(label)
            st.progress(min(max(float(r["pct"]), 0.0), 1.0))

    # Tabular detail (color-coded)
    def _row_style(row):
        if row["status"] == "OVER":
            return "background-color: rgba(255,0,0,0.12);"
        if row["status"] == "NEAR":
            return "background-color: rgba(255,165,0,0.12);"
        return ""

    show = alerts_df.copy()
    show["cap"] = show["cap"].map(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
    show["spend"] = show["spend"].map(lambda x: f"{x:,.0f}")
    show["remaining"] = show["remaining"].map(lambda x: f"{x:,.0f}" if pd.notna(x) else "—")
    show["pct"] = show["pct"].map(lambda x: f"{x:.0%}" if pd.notna(x) else "—")

    st.dataframe(
        show[["scope", "category", "month", "spend", "cap", "remaining", "pct", "status"]]
        .style.apply(lambda s: [ _row_style(s) ] * len(s), axis=1),
        use_container_width=True
    )

    # Send alerts (Email/Telegram) if configured
    st.divider()
    st.markdown("**Notify** (uses environment variables; see README for SMTP/Telegram setup)")
    if st.button("Send critical alerts (NEAR/OVER) now"):
        res = _send_alerts(alerts_df, subject_prefix="Personal Finance")
        st.write({
            "email_status": res.get("email"),
            "telegram_status": res.get("telegram")
        })

# ---------- Export ----------
st.subheader("📥 Export processed data")
st.download_button(
    "Download processed CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="processed_transactions.csv",
    mime="text/csv"
)
st.caption("Tune caps in `config/budgets.yml`. Add merchant rules in `config/category_rules.yml`.")