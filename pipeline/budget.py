"""
Budget & alerts utilities:
- Load budgets.yml
- Compute current-month spend (total + per-category)
- Generate alerts vs caps (OK / NEAR / OVER)
- Compute rolling 3-month average for comparisons
"""
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import pandas as pd
import yaml

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "budgets.yml")


@dataclass
class BudgetConfig:
    monthly_total_cap: Optional[float]
    warn_threshold: float
    category_caps: Dict[str, float]

    @classmethod
    def load(cls, path: str = CONFIG_PATH) -> "BudgetConfig":
        if not os.path.exists(path):
            # Sensible defaults if file not present
            return cls(monthly_total_cap=None, warn_threshold=0.9, category_caps={})
        with open(path, "r", encoding="utf-8") as f:
            y = yaml.safe_load(f) or {}
        return cls(
            monthly_total_cap=y.get("monthly_total_cap", None),
            warn_threshold=float(y.get("warn_threshold", 0.9)),
            category_caps=y.get("categories", {}) or {},
        )


def _this_month_period(df: pd.DataFrame) -> pd.Period:
    # Use the latest date in the dataset as "current month" for reproducible historical analyses
    latest = pd.to_datetime(df["date"]).max()
    return latest.to_period("M")


def current_month_frames(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Period]:
    p = _this_month_period(df)
    cur = df[df["date"].dt.to_period("M") == p]
    return cur, p


def monthly_total_spend(df: pd.DataFrame) -> pd.Series:
    # Positive spend per month (sum of negative signed_amounts turned positive)
    m = df.set_index("date")["signed_amount"].resample("MS").sum()
    return (-m).clip(lower=0)


def monthly_category_spend(df: pd.DataFrame) -> pd.DataFrame:
    # Positive spend per month & category
    g = (df[df["signed_amount"] < 0]
         .copy())
    g["month"] = g["date"].dt.to_period("M")
    out = (g.groupby(["month", "category"])["signed_amount"]
           .sum()
           .mul(-1)
           .rename("spend")
           .reset_index())
    return out


def rolling_avg_last_n_months(series: pd.Series, n: int = 3, exclude_last: bool = True) -> float:
    # series indexed by month-start Timestamp; compute trailing mean
    if exclude_last and len(series) >= 1:
        series = series.iloc[:-1]
    if len(series) == 0:
        return 0.0
    return float(series.tail(n).mean())


def build_alerts(df: pd.DataFrame, cfg: BudgetConfig) -> pd.DataFrame:
    """
    Returns a DataFrame with alerts for TOTAL and each capped category:
    columns: scope, category, month, spend, cap, remaining, pct, status
    """
    cur, mp = current_month_frames(df)
    month_label = str(mp)

    total_spend = (-cur.loc[cur["signed_amount"] < 0, "signed_amount"].sum())
    alerts = []

    def classify(spend: float, cap: Optional[float]):
        if cap is None:
            return ("N/A", None, None)  # status, pct, remaining
        pct = spend / cap if cap > 0 else 0.0
        remaining = cap - spend
        if spend > cap:
            return ("OVER", pct, remaining)
        elif pct >= cfg.warn_threshold:
            return ("NEAR", pct, remaining)
        else:
            return ("OK", pct, remaining)

    # TOTAL
    status, pct, remaining = classify(total_spend, cfg.monthly_total_cap)
    alerts.append({
        "scope": "TOTAL",
        "category": "TOTAL",
        "month": month_label,
        "spend": float(total_spend),
        "cap": float(cfg.monthly_total_cap) if cfg.monthly_total_cap is not None else None,
        "remaining": remaining,
        "pct": pct,
        "status": status,
    })

    # Per-category
    cat_spend = (cur[cur["signed_amount"] < 0]
                 .groupby("category")["signed_amount"].sum()
                 .mul(-1)
                 .sort_values(ascending=False))

    for cat, cap in cfg.category_caps.items():
        spend = float(cat_spend.get(cat, 0.0))
        status, pct, remaining = classify(spend, cap)
        alerts.append({
            "scope": "CATEGORY",
            "category": cat,
            "month": month_label,
            "spend": spend,
            "cap": float(cap),
            "remaining": remaining,
            "pct": pct,
            "status": status,
        })

    return pd.DataFrame(alerts).sort_values(["scope", "status", "spend"], ascending=[True, True, False]).reset_index(drop=True)
