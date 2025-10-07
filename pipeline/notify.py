"""
Lightweight alert notifications:
- Email via SMTP (stdlib)
- Telegram via Bot API (requires `requests`)

Configuration via environment variables:

Email (any SMTP: Gmail/Outlook/SES/etc.)
  SMTP_HOST            e.g., smtp.gmail.com
  SMTP_PORT            e.g., 587
  SMTP_USER            your login/username
  SMTP_PASS            your app password (for Gmail use App Passwords)
  EMAIL_FROM           e.g., you@domain.com
  EMAIL_TO             comma-separated list: a@x.com,b@y.com

Telegram (optional)
  TELEGRAM_BOT_TOKEN   bot token from @BotFather
  TELEGRAM_CHAT_ID     your chat id (or channel id)

Usage:
  from pipeline.notify import send_alerts
  send_alerts(alerts_df, subject_prefix="Finance Alerts")
"""
from __future__ import annotations
import os
import smtplib
from email.mime.text import MIMEText
from typing import Optional, List

import pandas as pd
import requests


def _build_email_body(alerts: pd.DataFrame) -> str:
    if alerts.empty:
        return "No alerts."
    lines: List[str] = []
    for _, r in alerts.iterrows():
        cap = "—" if pd.isna(r.get("cap")) else f"{float(r['cap']):,.0f}"
        remain = "—" if pd.isna(r.get("remaining")) else f"{float(r['remaining']):,.0f}"
        pct = "—" if pd.isna(r.get("pct")) else f"{float(r['pct']):.0%}"
        lines.append(
            f"[{r['status']}] {r['scope']} :: {r['category']} ({r['month']}) "
            f"Spend ₹{float(r['spend']):,.0f} / Cap {cap} ({pct} used, remaining {remain})"
        )
    return "\n".join(lines)


def _send_email(subject: str, body: str) -> Optional[str]:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASS")
    from_addr = os.getenv("EMAIL_FROM")
    to_list = [x.strip() for x in os.getenv("EMAIL_TO", "").split(",") if x.strip()]

    if not all([host, port, user, pwd, from_addr]) or not to_list:
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


def _send_telegram(text: str) -> Optional[str]:
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


def send_alerts(alerts: pd.DataFrame, subject_prefix: str = "Finance Alerts") -> dict:
    """
    Sends alerts via Email and Telegram if configured.
    Returns dict with 'email' and 'telegram' statuses (None = success).
    Only sends when there is at least one row with status NEAR or OVER.
    """
    critical = alerts[alerts["status"].isin(["NEAR", "OVER"])].copy()
    if critical.empty:
        return {"email": "No critical alerts to send.", "telegram": "No critical alerts to send."}

    subject = f"{subject_prefix}: {len(critical)} alert(s)"
    body = _build_email_body(critical)
    email_status = _send_email(subject, body)
    tg_status = _send_telegram(body)
    return {"email": email_status, "telegram": tg_status}
