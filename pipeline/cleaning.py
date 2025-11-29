"""
Cleaning & normalization: parse dates, amounts; derive signed_amount.
"""
from __future__ import annotations
import pandas as pd
import numpy as np

def clean_transactions(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # Parse date
    out["date"] = pd.to_datetime(out["date"], errors="coerce")

    # Normalize type
    out["type"] = out["type"].astype(str).str.upper().str.strip()
    out["type"] = out["type"].replace({
        "D": "DEBIT", "DR": "DEBIT", "DEB": "DEBIT",
        "C": "CREDIT", "CR": "CREDIT", "CRE": "CREDIT"
    })

    # Amount as float
    out["amount"] = (
        out["amount"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.extract(r"([0-9]*\.?[0-9]+)")
        .astype(float)
    )

    # Signed amount: negative for DEBIT (spend), positive for CREDIT (income)
    sign = np.where(out["type"].eq("CREDIT"), 1, -1)
    out["signed_amount"] = out["amount"] * sign

    # Fill optional fields
    for col in ["description", "account", "mode"]:
        if col in out.columns:
            out[col] = out[col].astype(str).fillna("")

    # Drop rows with no date/amount
    out = out.dropna(subset=["date", "amount"])

    # Add helpful derived columns
    out["year"] = out["date"].dt.year
    out["month"] = out["date"].dt.to_period("M").astype(str)
    out["day"] = out["date"].dt.date

    return out
