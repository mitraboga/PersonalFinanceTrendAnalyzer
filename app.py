"""
Streamlit dashboard for Personal Finance Trend Analyzer.

Now with:
- Budgets & alerts (total + per-category caps)
- 'This month vs 3-month average' comparison card
- Cross-platform upload handling (tempfile)
- .env auto-loading for SMTP/Telegram secrets
- ✅ 3 distinct donut charts (Category, Payment/Top Merchants, Income vs Expense)
- ✅ Notify section ALWAYS visible + TEST email button (no columns)
- ✅ Notification Settings UI (enable/disable + weekly/biweekly/monthly + channel toggles)
- ✅ DEBUG banner to prove WHICH app.py is running
"""
from __future__ import annotations

# >>> .env loader must be first so env vars are available everywhere
from dotenv import load_dotenv
load_dotenv()

import os
import sys
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
from pipeline.visualize import budget_donut, category_utilization_df
from pipeline.notify import send_alerts as _send_alerts

# ✅ scheduled notification settings support
from pipeline.schedule import NotifySettings


# ----------------------------- Build marker -----------------------------
APP_BUILD_ID = "PFTA_BUILD_2026-01-07_ALWAYS_VISIBLE_NOTIFY_SETTINGS_DEBUG_V2"


# ----------------------------- Helper functions (3 donuts) -----------------------------
def _pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _donut_plotly(labels, values, title: str):
    import plotly.express as px
    fig = px.pie(names=labels, values=values, hole=0.65)
    fig.update_layout(
        title=title,
        margin=dict(l=10, r=10, t=45, b=10),
        legend=dict(orientation="h", y=-0.2),
    )
    return fig


def _top_n_with_other(series: pd.Series, n: int = 7) -> pd.Series:
    series = series.dropna()
    if series.empty:
        return series
    series = series.sort_values(ascending=False)
    top = series.head(n)
    rest_sum = float(series.iloc[n:].sum()) if len(series) > n else 0.0
    if rest_sum > 0:
        top.loc["Other"] = rest_sum
    return top


def render_three_donuts(df: pd.DataFrame):
    if "signed_amount" not in df.columns:
        st.warning("3-donut charts skipped: column 'signed_amount' not found.")
        return

    expense_df = df[df["signed_amount"] < 0].copy()
    income_df = df[df["signed_amount"] > 0].copy()

    # 1) Expense by Category
    category_col = _pick_col(df, ["category", "Category", "txn_category", "merchant_category"])
    if category_col and not expense_df.empty:
        cat_spend = expense_df.groupby(category_col)["signed_amount"].sum().abs()
        cat_spend = _top_n_with_other(cat_spend, n=7)
        labels1, values1 = cat_spend.index.astype(str).tolist(), cat_spend.values.tolist()
    else:
        labels1, values1 = (
            ["No category data"],
            [float(expense_df["signed_amount"].abs().sum()) if not expense_df.empty else 1.0],
        )

    # 2) Expense by Payment Method (fallback to Top Merchants/Descriptions)
    method_col = _pick_col(
        df,
        ["payment_method", "Payment Method", "method", "mode", "Mode", "payment_mode", "channel", "instrument"],
    )
    merchant_fallback_col = _pick_col(
        df,
        ["merchant", "Merchant", "payee", "Payee", "description", "Description", "narration", "Narration", "remarks", "Remarks"],
    )

    if method_col and not expense_df.empty:
        pm_spend = expense_df.groupby(method_col)["signed_amount"].sum().abs()
        pm_spend = _top_n_with_other(pm_spend, n=7)
        labels2, values2 = pm_spend.index.astype(str).tolist(), pm_spend.values.tolist()
        donut2_title = "Spend by Payment Method"
    elif merchant_fallback_col and not expense_df.empty:
        top_merchants = expense_df.groupby(merchant_fallback_col)["signed_amount"].sum().abs()
        top_merchants = _top_n_with_other(top_merchants, n=7)
        labels2, values2 = top_merchants.index.astype(str).tolist(), top_merchants.values.tolist()
        donut2_title = "Top Spend Merchants"
    else:
        labels2, values2 = (
            ["No method/merchant data"],
            [float(expense_df["signed_amount"].abs().sum()) if not expense_df.empty else 1.0],
        )
        donut2_title = "Spend Split"

    # 3) Income vs Expense
    income_total = float(income_df["signed_amount"].sum()) if not income_df.empty else 0.0
    expense_total = float(expense_df["signed_amount"].abs().sum()) if not expense_df.empty else 0.0
    labels3 = ["Income", "Expense"]
    values3 = [income_total if income_total > 0 else 0.0, expense_total if expense_total > 0 else 0.0]
    if sum(values3) == 0:
        values3 = [1.0, 1.0]

    st.subheader("🍩 Quick Snapshot (3 perspectives)")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.plotly_chart(_donut_plotly(labels1, values1, "Spend by Category"), use_container_width=True)
    with c2:
        st.plotly_chart(_donut_plotly(labels2, values2, donut2_title), use_container_width=True)
    with c3:
        st.plotly_chart(_donut_plotly(labels3, values3, "Income vs Expense"), use_container_width=True)


# ---------- Page config ----------
st.set_page_config(page_title="Personal Finance Trend Analyzer", layout="wide")
st.title("💸 Personal Finance Trend Analyzer")
st.caption(
    "Upload bank/UPI CSV or Excel → normalize, categorize, visualize, and forecast. "
    "Now with budgets, per-category caps, and variance vs 3-month average."
)

# ✅ Build marker (proves this file is being used)
st.info(f"✅ Running build: `{APP_BUILD_ID}`")

# ✅ HARD DEBUG: shows exactly what file Streamlit is executing
with st.expander("🧪 Debug: Which app.py is running?", expanded=True):
    st.write("If you don’t see this expander, you are NOT running this file.")
    st.code(
        "\n".join([
            f"__file__       = {__file__}",
            f"cwd            = {os.getcwd()}",
            f"python         = {sys.executable}",
            f"streamlit_ver  = {getattr(st, '__version__', 'unknown')}",
        ])
    )
    st.caption("Tip: Stop Streamlit (Ctrl+C), then run using an absolute path:")
    st.code(r'streamlit run "C:\Users\Owner\Documents\GitHub\PersonalFinanceTrendAnalyzer\app.py"', language="powershell")


# =========================================================
# ✅ ALWAYS-VISIBLE NOTIFY + SETTINGS (BEFORE UPLOAD GATE)
# =========================================================
st.subheader("🔔 Notifications")

st.markdown("**Manual Notify** (reads SMTP/Telegram from environment or `.env`)")
st.caption("Use TEST to verify SMTP/Telegram even if you have zero alerts configured.")

# TEST is always available because it uses a dummy alert row
if st.button("Send TEST email (even if no alerts)", key="send_test_top"):
    test_df = pd.DataFrame([{
        "scope": "TOTAL",
        "category": "—",
        "month": pd.Timestamp.today().strftime("%Y-%m"),
        "spend": 12345.0,
        "cap": 15000.0,
        "remaining": 2655.0,
        "pct": 0.82,
        "status": "NEAR",
    }])
    res = _send_alerts(test_df, subject_prefix="Personal Finance (TEST)")
    st.write({"email": res.get("email"), "telegram": res.get("telegram")})

st.divider()

st.subheader("🗓️ Notification Settings (Scheduled Reports)")
st.caption(
    "These settings control automated reports (GitHub Actions / scheduled runs). "
    "They do NOT affect the manual TEST button above."
)

try:
    ns = NotifySettings.load()
except Exception as e:
    st.error(f"Failed to load notification settings: {e}")
    ns = NotifySettings(
        enabled=False,
        email=True,
        telegram=False,
        frequency="weekly",
        timezone="Asia/Kolkata",
        monthly_day=1,
        weekly_weekday=0,
    )

colA, colB, colC = st.columns(3)
with colA:
    enabled = st.toggle("Enable scheduled notifications", value=bool(ns.enabled))
with colB:
    email_on = st.toggle("Email channel", value=bool(ns.email))
with colC:
    telegram_on = st.toggle("Telegram channel", value=bool(ns.telegram))

freq = st.selectbox(
    "Frequency",
    options=["weekly", "biweekly", "monthly"],
    index=["weekly", "biweekly", "monthly"].index(
        ns.frequency if ns.frequency in ["weekly", "biweekly", "monthly"] else "weekly"
    ),
)

weekly_weekday = ns.weekly_weekday
monthly_day = ns.monthly_day

if freq in ["weekly", "biweekly"]:
    weekday_choice = st.selectbox(
        "Send on weekday",
        options=[
            ("Monday", 0), ("Tuesday", 1), ("Wednesday", 2),
            ("Thursday", 3), ("Friday", 4), ("Saturday", 5), ("Sunday", 6),
        ],
        index=[0, 1, 2, 3, 4, 5, 6].index(int(ns.weekly_weekday)),
        format_func=lambda x: x[0],
    )
    weekly_weekday = int(weekday_choice[1])
else:
    monthly_day = int(
        st.number_input("Send on day of month (1–28)", min_value=1, max_value=28, value=int(ns.monthly_day))
    )

tz = st.text_input("Timezone", value=str(ns.timezone))

if st.button("Save notification settings", key="save_notify_settings"):
    ns.enabled = bool(enabled)
    ns.email = bool(email_on)
    ns.telegram = bool(telegram_on)
    ns.frequency = str(freq)
    ns.weekly_weekday = int(weekly_weekday)
    ns.monthly_day = int(monthly_day)
    ns.timezone = str(tz)

    try:
        ns.save()
        st.success("✅ Saved to `config/notify_settings.yml`.")
    except Exception as e:
        st.error(f"Could not save settings: {e}")

st.divider()


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
    st.caption(f"Build: {APP_BUILD_ID}")

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

render_three_donuts(df)

# ---------- Variance ----------
m_series = monthly_total_spend(df)
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
st.dataframe(
    pd.DataFrame({"Month": fc.index.strftime("%Y-%m"), "Forecast Spend (₹)": fc.values}),
    use_container_width=True,
)

# ---------- Budgets & Alerts ----------
st.subheader("🚨 Budgets & Alerts")
cfg = BudgetConfig.load()
alerts_df = build_alerts(df, cfg)

st.markdown("**Notify (data-based)**")
st.caption("This button uses real alerts from your current dataset.")
if st.button("Send critical alerts (NEAR/OVER) now", key="send_critical"):
    res = _send_alerts(alerts_df, subject_prefix="Personal Finance")
    st.write({"email": res.get("email"), "telegram": res.get("telegram")})

st.divider()

# ---- Existing Budgets UI ----
if alerts_df.empty:
    st.info("No caps configured or no spend this month. Add caps in `config/budgets.yml`.")
else:
    total_row = alerts_df[alerts_df["scope"] == "TOTAL"].head(1)
    if not total_row.empty and pd.notna(total_row.iloc[0]["cap"]):
        tcap = float(total_row.iloc[0]["cap"])
        tspend = float(total_row.iloc[0]["spend"])
        st.plotly_chart(budget_donut(tcap, tspend), use_container_width=True)

    st.markdown("**Category caps progress**")
    cat_df = category_utilization_df(alerts_df)
    if cat_df.empty:
        st.caption("No per-category caps set.")
    else:
        for _, r in cat_df.iterrows():
            label = f"{r['category']} — ₹{r['spend']:,.0f} / ₹{r['cap']:,.0f} ({r['pct']:.0%}) [{r['status']}]"
            st.write(label)
            st.progress(min(max(float(r["pct"]), 0.0), 1.0))

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
        .style.apply(lambda s: [_row_style(s)] * len(s), axis=1),
        use_container_width=True
    )

# ---------- Export ----------
st.subheader("📥 Export processed data")
st.download_button(
    "Download processed CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="processed_transactions.csv",
    mime="text/csv"
)
st.caption("Tune caps in `config/budgets.yml`. Add merchant rules in `config/category_rules.yml`.")