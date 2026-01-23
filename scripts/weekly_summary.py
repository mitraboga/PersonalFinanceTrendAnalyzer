from __future__ import annotations

# .env first
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
from pipeline.schedule import NotifySettings, is_due_today, mark_sent_today


def _load_concat(glob_pattern: str) -> pd.DataFrame:
    paths = sorted(glob.glob(glob_pattern))
    if not paths:
        paths = ["data/sample_transactions.csv"]

    frames = []
    for p in paths:
        df = load_transactions(p)
        df = clean_transactions(df)
        df = categorize(df)
        frames.append(df)

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
    lines.append(f"Finance Summary (last {days} days)")
    lines.append(f"Totals: Spend {_fmt_currency(cur_spend)} (prev {_fmt_currency(prev_spend)}), "
                 f"Income {_fmt_currency(cur_income)} (prev {_fmt_currency(prev_income)})")
    lines.append("")
    lines.append("Top Categories:")
    lines.extend([f"  - {cat}: {_fmt_currency(float(amt))}" for cat, amt in cat_cur.items()] or ["  (no spend)"])
    lines.append("")
    lines.append("Top Merchants:")
    lines.extend([f"  - {desc}: {_fmt_currency(float(amt))}" for desc, amt in merch_cur.items()] or ["  (no spend)"])
    lines.append("")
    lines.append("This Month vs 3-Month Avg:")
    lines.append(f"  This Month: {_fmt_currency(this_month)}")
    lines.append(f"  3-Mo Avg : {_fmt_currency(trailing)} (Δ {delta_abs:+,.0f}; {delta_pct:+.1f}%)")
    lines.append("")
    lines.append("Critical Budget Alerts (NEAR/OVER):")
    lines.append(alerts_block)
    lines.append("")
    lines.append("— Automated by Personal Finance Trend Analyzer.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_glob", default="data/*.csv")
    ap.add_argument("--output", default="outputs")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--notify", action="store_true")
    ap.add_argument("--force", action="store_true", help="Ignore schedule and send now (CI debug)")
    args = ap.parse_args()

    os.makedirs(args.output, exist_ok=True)

    df = _load_concat(args.input_glob)
    df.to_csv(os.path.join(args.output, "weekly_processed.csv"), index=False)

    cfg = BudgetConfig.load()
    alerts = build_alerts(df, cfg)
    alerts.to_csv(os.path.join(args.output, "alerts.csv"), index=False)

    # ---- schedule gate ----
    settings = NotifySettings.load()
    due = is_due_today(settings)
    if args.notify and (args.force or due):
        # respect channel toggles
        # send_alerts currently sends both; we gate by settings here
        if settings.email or settings.telegram:
            # If only one channel enabled, we can still call send_alerts,
            # but pipeline.notify needs to honor missing creds.
            res = send_alerts(alerts, subject_prefix="Personal Finance")
            # If a channel is disabled, we treat it as intentionally skipped
            if not settings.email:
                res["email"] = "Skipped (email disabled)"
            if not settings.telegram:
                res["telegram"] = "Skipped (telegram disabled)"
            print(f"[NOTIFY] alerts: {res}")

        # weekly digest email (only if email enabled)
        if settings.email:
            body = build_weekly_email_body(df, alerts, args.days)
            err = send_email(subject=f"Finance Summary ({args.days} days)", body=body)
            print(f"[EMAIL DIGEST] {err or 'sent'}")
        else:
            print("[EMAIL DIGEST] Skipped (email disabled)")

        # persist last sent date
        mark_sent_today(settings)
        print("[SCHEDULE] Marked as sent today.")
    else:
        print(f"[SCHEDULE] Not sending. notify={args.notify} due_today={due} enabled={settings.enabled}")

    print("[DONE]")


if __name__ == "__main__":
    main()