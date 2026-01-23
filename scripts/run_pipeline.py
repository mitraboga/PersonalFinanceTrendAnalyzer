"""
Batch pipeline: read input file, clean, categorize, summarize, forecast, and write outputs.
Writes: processed.csv, 3 HTML charts, monthly_category_spend.csv, alerts.csv
Optionally sends Email/Telegram alerts if --notify is set and env vars are configured.
Now auto-loads .env.

Usage:
  python -m scripts.run_pipeline --input data/sample_transactions.csv --output outputs
  python -m scripts.run_pipeline --input data/sample_transactions.csv --output outputs --notify
"""
from __future__ import annotations

# >>> .env loader first
from dotenv import load_dotenv
load_dotenv()

import argparse
import os
import pandas as pd

from pipeline.ingestion import load_transactions
from pipeline.cleaning import clean_transactions
from pipeline.categorize import categorize
from pipeline.forecasting import forecast_monthly_spend
from pipeline.visualize import category_spend_bar, monthly_trend_line, forecast_line
from pipeline.budget import BudgetConfig, build_alerts
from pipeline.notify import send_alerts


def main():
    ap = argparse.ArgumentParser(description="Personal Finance Trend Analyzer batch pipeline")
    ap.add_argument("--input", required=True, help="Path to CSV/Excel input")
    ap.add_argument("--output", default="outputs", help="Output folder (HTML charts + CSVs)")
    ap.add_argument("--notify", action="store_true", help="Send Email/Telegram alerts if critical (NEAR/OVER)")
    args = ap.parse_args()

    os.makedirs(args.output, exist_ok=True)

    df = load_transactions(args.input)
    df = clean_transactions(df)
    df = categorize(df)

    processed_path = os.path.join(args.output, "processed.csv")
    df.to_csv(processed_path, index=False)
    print(f"[OK] {processed_path}")

    # Charts
    category_spend_bar(df).write_html(os.path.join(args.output, "category_spend.html"))
    monthly_trend_line(df).write_html(os.path.join(args.output, "monthly_trend.html"))
    hist, fc = forecast_monthly_spend(df)
    forecast_line(hist, fc).write_html(os.path.join(args.output, "spend_forecast.html"))

    # Summary CSV
    (
        df[df["signed_amount"] < 0]
        .groupby(["month", "category"])["signed_amount"]
        .sum()
        .mul(-1)
        .rename("spend")
        .reset_index()
        .to_csv(os.path.join(args.output, "monthly_category_spend.csv"), index=False)
    )

    # Alerts CSV + optional notify
    cfg = BudgetConfig.load()
    alerts = build_alerts(df, cfg)
    alerts_path = os.path.join(args.output, "alerts.csv")
    alerts.to_csv(alerts_path, index=False)
    print(f"[OK] {alerts_path}")

    if args.notify:
        res = send_alerts(alerts, subject_prefix="Personal Finance")
        print(f"[NOTIFY] email={res.get('email')} telegram={res.get('telegram')}")

    print("[DONE] Pipeline complete.")


if __name__ == "__main__":
    main()
