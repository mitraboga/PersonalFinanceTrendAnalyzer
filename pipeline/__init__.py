"""
Pipeline package for Personal Finance Trend Analyzer.

This __init__ module re-exports the main public functions and classes
from the submodules so they can be imported conveniently elsewhere.

Example:
    from pipeline import load_transactions, clean_transactions, categorize
"""

from .ingestion import load_transactions
from .cleaning import clean_transactions
from .categorize import categorize, load_rules
from .forecasting import forecast_monthly_spend
from .visualize import (
    category_spend_bar,
    monthly_trend_line,
    forecast_line,
    budget_donut,
    category_utilization_df,
)
from .budget import (
    BudgetConfig,
    monthly_total_spend,
    build_alerts,
    current_month_frames,
    rolling_avg_last_n_months,
)
from .notify import send_alerts, send_email, send_telegram

__all__ = [
    # ingestion / cleaning
    "load_transactions",
    "clean_transactions",

    # categorization
    "categorize",
    "load_rules",

    # forecasting
    "forecast_monthly_spend",

    # visualization
    "category_spend_bar",
    "monthly_trend_line",
    "forecast_line",
    "budget_donut",
    "category_utilization_df",

    # budget / alerts
    "BudgetConfig",
    "monthly_total_spend",
    "build_alerts",
    "current_month_frames",
    "rolling_avg_last_n_months",

    # notifications
    "send_alerts",
    "send_email",
    "send_telegram",
]
