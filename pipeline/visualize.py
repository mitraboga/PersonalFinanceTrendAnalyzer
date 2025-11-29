"""
Plotly visualizations for the dashboard and batch pipeline.
"""
from __future__ import annotations
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go

def category_spend_bar(df: pd.DataFrame):
    g = df[df["signed_amount"] < 0].groupby("category")["signed_amount"].sum().sort_values()
    g = -g  # make positive for chart
    fig = px.bar(g, title="Spend by Category (₹)", labels={"value": "₹", "category": "Category"})
    fig.update_layout(xaxis_title="Category", yaxis_title="Spend (₹)")
    return fig

def monthly_trend_line(df: pd.DataFrame):
    m = df.set_index("date")["signed_amount"].resample("MS").sum()
    spend = (-m).clip(lower=0)
    fig = px.line(spend, title="Monthly Spend Trend (₹)")
    fig.update_layout(xaxis_title="Month", yaxis_title="Spend (₹)")
    return fig

def forecast_line(history: pd.Series, forecast: pd.Series):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=history.index, y=history.values, mode="lines+markers", name="History"))
    fig.add_trace(go.Scatter(x=forecast.index, y=forecast.values, mode="lines+markers", name="Forecast"))
    fig.update_layout(title="Monthly Spend Forecast (₹)", xaxis_title="Month", yaxis_title="Spend (₹)")
    return fig

# ... keep existing imports and functions ...

def budget_donut(total_cap: float, spend: float):
    """
    Donut chart showing used vs remaining of total budget.
    If no cap provided (None), caller should skip rendering.
    """
    import plotly.express as px
    remaining = max(total_cap - spend, 0.0)
    df = pd.DataFrame({"label": ["Used", "Remaining"], "value": [spend, remaining]})
    fig = px.pie(
        df, values="value", names="label", hole=0.55,
        title="Total Budget Utilization"
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    return fig


def category_utilization_df(alerts_df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a frame with category, spend, cap, pct (0..1), status
    Filtered only to CATEGORY rows that have a cap.
    """
    cats = alerts_df[alerts_df["scope"] == "CATEGORY"].copy()
    cats = cats[pd.notna(cats["cap"])]
    return cats[["category", "spend", "cap", "pct", "status"]].reset_index(drop=True)
