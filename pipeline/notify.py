"""
Notifications:
- Email via SMTP (stdlib)
- Telegram via Bot API (requests)

Env Vars (set locally or as GitHub Action secrets):
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_FROM, EMAIL_TO (comma-separated)
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

APIs:
  send_email(subject, body) -> Optional[str]
  send_telegram(text) -> Optional[str]
  send_alerts(alerts_df, subject_prefix) -> dict  # only NEAR/OVER rows
"""
from __future__ import annotations
import os
import smtplib
from email.mime.text import MIMEText
from typing import Optional, List

import pandas as pd
import requests


def send_email(subject: str, body: str) -> Optional[str]:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASS")
    from_addr = os.getenv("EMAIL_FROM")
    to_list = [x.strip() for x in os.getenv("EMAIL_TO", "").split(",") if x.strip()]

    if not all([host, user, pwd, from_addr]) or not to_list:
        return "Email not configured (missing SMTP_* or EMAIL_* env vars)."

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_list)

    try:
        with smtplib.SMTP(host, port) as s:
            s.starttls()
            s.login(user, pwd)
            s.sendmail(from_addr, to_list, msg.as_string())
        return None
    except Exception as e:
        return f"Email send error: {e}"


def send_telegram(text: str) -> Optional[str]:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return "Telegram not configured (missing TELEGRAM_BOT_TOKEN/CHAT_ID)."
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=15
        )
        if r.status_code != 200:
            return f"Telegram send error: {r.status_code} {r.text}"
        return None
    except Exception as e:
        return f"Telegram send error: {e}"


def _build_alerts_body(alerts: pd.DataFrame) -> str:
    if alerts.empty:
        return "No alerts."
    lines: List[str] = []

    def _fmt_amount(value) -> str:
        if pd.isna(value):
            return "N/A"
        return f"INR {float(value):,.0f}"

    def _fmt_pct(value) -> str:
        if pd.isna(value):
            return "N/A"
        return f"{float(value):.0%}"

    for _, r in alerts.iterrows():
        cap = _fmt_amount(r.get("cap"))
        remain = _fmt_amount(r.get("remaining"))
        pct = _fmt_pct(r.get("pct"))
        spend = _fmt_amount(r.get("spend"))
        lines.append(
            f"[{r['status']}] {r['scope']} :: {r['category']} ({r['month']}) "
            f"Spend {spend} / Cap {cap} (used {pct}, remaining {remain})"
        )
    return "\n".join(lines)


def send_alerts(alerts: pd.DataFrame, subject_prefix: str = "Finance Alerts") -> dict:
    """
    Sends alerts via Email and Telegram if configured.
    Only includes NEAR/OVER rows.
    Returns dict with 'email' and 'telegram' statuses (None = success).
    """
    critical = alerts[alerts["status"].isin(["NEAR", "OVER"])].copy()
    if critical.empty:
        return {"email": "No critical alerts to send.", "telegram": "No critical alerts to send."}

    subject = f"{subject_prefix}: {len(critical)} alert(s)"
    body = _build_alerts_body(critical)
    email_status = send_email(subject, body)
    tg_status = send_telegram(body)
    return {"email": email_status, "telegram": tg_status}

