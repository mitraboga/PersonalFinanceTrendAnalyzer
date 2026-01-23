"""
Ingestion: Load transactions from CSV/Excel and map to a standard schema.
"""
from __future__ import annotations
import pandas as pd
from typing import Union
from .utils import normalize_colname

STANDARD_COLS = ["date", "description", "amount", "type", "account", "mode"]

# Synonym map for common export headers across banks/wallets
SYNONYMS = {
    "date": {"date", "txn_date", "transaction_date", "posting_date"},
    "description": {"description", "narration", "merchant", "details"},
    "amount": {"amount", "amt", "inr", "value"},
    "type": {"type", "dr_cr", "credit_debit", "transaction_type"},
    "account": {"account", "account_no", "account_number", "acct"},
    "mode": {"mode", "channel", "payment_mode", "method"},
}

def _map_columns(df: pd.DataFrame) -> pd.DataFrame:
    orig = {normalize_colname(c): c for c in df.columns}
    mapped = {}
    for std, alias_set in SYNONYMS.items():
        # find any alias present
        found = None
        for alias in alias_set:
            if normalize_colname(alias) in orig:
                found = orig[normalize_colname(alias)]
                break
        if found is None:
            # try direct presence of std
            if normalize_colname(std) in orig:
                found = orig[normalize_colname(std)]
        if found is not None:
            mapped[std] = found

    # Build standardized frame
    out = pd.DataFrame()
    for col in STANDARD_COLS:
        if col in mapped:
            out[col] = df[mapped[col]]
        else:
            out[col] = pd.NA
    # include any extra columns
    extras = [c for c in df.columns if c not in mapped.values()]
    for c in extras:
        out[c] = df[c]
    return out

def load_transactions(path_or_buffer: Union[str, bytes]) -> pd.DataFrame:
    """
    Load a CSV or Excel into the standard schema.
    """
    path = str(path_or_buffer)
    if path.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)
    df = _map_columns(df)
    return df