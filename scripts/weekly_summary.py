"""
Weekly finance summary & notifier.

- Ingests one or more CSV/Excel files (glob).
- Cleans, categorizes, aggregates last N days (default 7).
- Generates outputs in `--output` (CSV artifacts).
- Sends alerts (NEAR/OVER) via Email/Telegram when `--notify` is passed.
- Always emails a human-friendly weekly summary when email is configured.
- Auto-loads .env.

Usage:
  python -m scripts.weekly_summary --input_glob "data/*.csv" --output outputs --days 7 --notify
"""
from __future__ import annotations

# >>> .env loader first
from dotenv import load_dotenv
load_dotenv()

import argparse
import glob
import os
from datetime import datetime, timezone

import pandas as pd

from pipeline.ingestion import load_transactions
from pipeline.cleaning import clean_transactions
from pipeline.categorize import categorize
from pipeline.budget import BudgetConfig, build_alerts, monthly_total_spend
from pipeline.notify import send_alerts, send_email


def _load_concat(glob_pattern: str) -> pd.DataFrame:
    paths = sorted(glob.glob(glob_pattern))
    if not paths:
        paths = ["data/sample_transactions.csv"]

    frames = []
    for p in paths:
        try:
            df = load_transactions(p)
            df = clean_transactions(df)
            df = categorize(df)
            frames.append(df)
        except Exception as e:
            print(f"[WARN] Skipping {p}: {e}")
    if not frames:
        raise RuntimeError("No valid input files found or all failed to load.")
    return pd.concat(frames, ignore_index=True)


def _period_filter(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    m = (df["date"] >= start) & (df["date"] < end)
    return df.loc[m].copy()


def _fmt_currency(x: float) -> str:
    return f"₹{x:,.0f}"


def build_weekly_email_body(df: pd.DataFrame, alerts_df: pd.DataFrame, days: int) -> str:
    now = datetime.now(timezone.utc)
    end = pd.Timestamp(now.date())
    start = end - pd.Timedelta(days=days)

    cur = _period_filter(df, start, end)
    prev = _period_filter(df, start - pd.Timedelta(days=days), start)

    cur_spend = float((-cur.loc[cur["signed_amount"] < 0, "signed_amount"].sum()))
    prev_spend = float((-prev.loc[prev["signed_amount"] < 0, "signed_amount"].sum()))
    cur_income = float(cur.loc[cur["signed_amount"] > 0, "signed_amount"].sum())
    prev_income = float(prev.loc[prev["signed_amount"] > 0, "signed_amount"].sum())

    cat_cur = (
        cur[cur["signed_amount"] < 0]
        .groupby("category")["signed_amount"].sum()
        .mul(-1)
        .sort_values(ascending=False)
        .head(5)
    )

    merch_cur = (
        cur[cur["signed_amount"] < 0]
        .groupby("description")["signed_amount"].sum()
        .mul(-1)
        .sort_values(ascending=False)
        .head(5)
    )

    monthly = monthly_total_spend(df)
    this_month = float(monthly.iloc[-1]) if len(monthly) else 0.0
    trailing = float(monthly.iloc[:-1].tail(3).mean()) if len(monthly) > 1 else 0.0
    delta_abs = this_month - trailing
    delta_pct = (delta_abs / trailing * 100.0) if trailing > 0 else 0.0

    critical = alerts_df[alerts_df["status"].isin(["NEAR", "OVER"])].copy()
    alerts_lines = []
    for _, r in critical.iterrows():
        cap = "—" if pd.isna(r["cap"]) else _fmt_currency(float(r["cap"]))
        remain = "—" if pd.isna(r["remaining"]) else _fmt_currency(float(r["remaining"]))
        pct = "—" if pd.isna(r["pct"]) else f"{float(r['pct']):.0%}"
        alerts_lines.append(
            f"[{r['status']}] {r['scope']}/{r['category']} ({r['month']}): "
            f"Spend {_fmt_currency(float(r['spend']))} / Cap {cap} "
            f"({pct} used, remaining {remain})"
        )
    alerts_block = "\n".join(alerts_lines) if alerts_lines else "None"

    lines = []
    lines.append(f"Weekly Finance Summary (last {days} days)")
    lines.append(f"Window: {start.date()} → {end.date()} (exclusive of end date)")
    lines.append("")
    lines.append("Totals:")
    lines.append(f"  Spend:  {_fmt_currency(cur_spend)}  (prev {_fmt_currency(prev_spend)})")
    lines.append(f"  Income: {_fmt_currency(cur_income)}  (prev {_fmt_currency(prev_income)})")
    lines.append("")
    lines.append("Top Categories:")
    if cat_cur.empty:
        lines.append("  (no spend)")
    else:
        for cat, amt in cat_cur.items():
            lines.append(f"  - {cat}: {_fmt_currency(float(amt))}")
    lines.append("")
    lines.append("Top Merchants (by Description):")
    if merch_cur.empty:
        lines.append("  (no spend)")
    else:
        for desc, amt in merch_cur.items():
            lines.append(f"  - {desc}: {_fmt_currency(float(amt))}")
    lines.append("")
    lines.append("This Month vs 3-Month Avg:")
    lines.append(f"  This Month: {_fmt_currency(this_month)}")
    lines.append(f"  3-Mo Avg : {_fmt_currency(trailing)}  (Δ {delta_abs:+,.0f}; {delta_pct:+.1f}%)")
    lines.append("")
    lines.append("Critical Budget Alerts (NEAR/OVER):")
    lines.append(f"{alerts_block}")
    lines.append("")
    lines.append("— This message was generated automatically by Personal Finance Trend Analyzer.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Weekly summary generator and notifier")
    ap.add_argument("--input_glob", default="data/*.csv", help="Glob for CSV/Excel files")
    ap.add_argument("--output", default="outputs", help="Output folder for artifacts")
    ap.add_argument("--days", type=int, default=7, help="Lookback window in days")
    ap.add_argument("--notify", action="store_true", help="Send Email/Telegram notifications")
    args = ap.parse_args()

    os.makedirs(args.output, exist_ok=True)

    df = _load_concat(args.input_glob)

    processed_path = os.path.join(args.output, "weekly_processed.csv")
    df.to_csv(processed_path, index=False)
    print(f"[OK] {processed_path}")

    cfg = BudgetConfig.load()
    alerts = build_alerts(df, cfg)

    now = datetime.now(timezone.utc)
    end = pd.Timestamp(now.date())
    start = end - pd.Timedelta(days=args.days)
    cur = _period_filter(df, start, end)

    cat_cur = (
        cur[cur["signed_amount"] < 0]
        .groupby("category")["signed_amount"].sum()
        .mul(-1)
        .rename("spend")
        .sort_values(ascending=False)
        .reset_index()
    )
    cat_csv = os.path.join(args.output, "weekly_category_spend.csv")
    cat_cur.to_csv(cat_csv, index=False)

    merch_cur = (
        cur[cur["signed_amount"] < 0]
        .groupby("description")["signed_amount"].sum()
        .mul(-1)
        .rename("spend")
        .sort_values(ascending=False)
        .reset_index()
    )
    merch_csv = os.path.join(args.output, "weekly_top_descriptions.csv")
    merch_cur.to_csv(merch_csv, index=False)

    alerts_csv = os.path.join(args.output, "alerts.csv")
    alerts.to_csv(alerts_csv, index=False)

    print(f"[OK] {cat_csv}")
    print(f"[OK] {merch_csv}")
    print(f"[OK] {alerts_csv}")

    if args.notify:
        res = send_alerts(alerts, subject_prefix="Personal Finance")
        print(f"[NOTIFY] alerts: email={res.get('email')} telegram={res.get('telegram')}")

        body = build_weekly_email_body(df, alerts, days=args.days)
        err = send_email(subject=f"Weekly Finance Summary (last {args.days} days)", body=body)
        print(f"[EMAIL DIGEST] {err or 'sent'}")


if __name__ == "__main__":
    main()
