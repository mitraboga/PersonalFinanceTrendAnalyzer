import pandas as pd
from pipeline.ingestion import load_transactions

def test_load_transactions():
    df = load_transactions("data/sample_transactions.csv")
    assert {"date", "description", "amount", "type", "account", "mode"}.issubset(df.columns)
    assert len(df) >= 5