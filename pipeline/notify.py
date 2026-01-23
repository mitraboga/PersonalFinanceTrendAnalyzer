from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


@dataclass
class SmtpConfig:
    host: str
    port: int
    user: str
    password: str
    from_addr: str
    use_tls: bool = True  # STARTTLS

    @staticmethod
    def from_env() -> "SmtpConfig":
        host = os.getenv("SMTP_HOST", "").strip()
        port = int(os.getenv("SMTP_PORT", "587").strip())
        user = os.getenv("SMTP_USER", "").strip()
        password = os.getenv("SMTP_PASS", "").strip()
        from_addr = os.getenv("SMTP_FROM", "").strip() or user
        use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() in ("1", "true", "yes", "y", "on")

        if not host:
            raise ValueError("Missing SMTP_HOST")
        if not user:
            raise ValueError("Missing SMTP_USER")
        if not password:
            raise ValueError("Missing SMTP_PASS")
        if not from_addr:
            raise ValueError("Missing SMTP_FROM (or SMTP_USER)")

        return SmtpConfig(host=host, port=port, user=user, password=password, from_addr=from_addr, use_tls=use_tls)


def _parse_recipients(raw: str) -> List[str]:
    # Supports comma/semicolon separated recipient lists
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace(";", ",").split(",")]
    return [p for p in parts if p]


def _default_recipients(raw: str) -> List[str]:
    """
    Resolve recipients from ALERT_EMAIL_TO, with fallback to SMTP_FROM/SMTP_USER.
    """
    recipients = _parse_recipients(raw)
    if recipients:
        return recipients
    fallback = os.getenv("SMTP_FROM", "").strip() or os.getenv("SMTP_USER", "").strip()
    return _parse_recipients(fallback)


def _alerts_to_message_tables(alerts_df: pd.DataFrame) -> Tuple[str, str]:
    """
    Build plain text + HTML message bodies from alerts_df (already filtered).
    Expected columns: scope, category, month, spend, cap, remaining, pct, status
    """
    # Create a compact copy with formatted values for human readability
    df = alerts_df.copy()

    def _fmt_money(x):
        try:
            return f"₹{float(x):,.0f}"
        except Exception:
            return "—"

    def _fmt_pct(x):
        try:
            return f"{float(x) * 100:.0f}%"
        except Exception:
            return "—"

    # Ensure columns exist (avoid KeyErrors)
    for col in ["scope", "category", "month", "spend", "cap", "remaining", "pct", "status"]:
        if col not in df.columns:
            df[col] = ""

    df["spend"] = df["spend"].map(_fmt_money)
    df["cap"] = df["cap"].map(lambda v: _fmt_money(v) if pd.notna(v) else "—")
    df["remaining"] = df["remaining"].map(lambda v: _fmt_money(v) if pd.notna(v) else "—")
    df["pct"] = df["pct"].map(lambda v: _fmt_pct(v) if pd.notna(v) else "—")

    # Plain text
    lines = ["Personal Finance Alerts (NEAR/OVER)", "-" * 36]
    for _, r in df.iterrows():
        lines.append(
            f"[{r['status']}] {r['scope']} {r['category']} | Month: {r['month']} | "
            f"Spend: {r['spend']} | Cap: {r['cap']} | Remaining: {r['remaining']} | Util: {r['pct']}"
        )
    text_body = "\n".join(lines)

    # HTML table with light styling
    html_rows = []
    for _, r in df.iterrows():
        status = str(r["status"]).upper()
        bg = "#ffe8e8" if status == "OVER" else ("#fff3d9" if status == "NEAR" else "#ffffff")
        html_rows.append(
            f"""
            <tr style="background:{bg}">
              <td style="padding:8px;border:1px solid #ddd">{r['status']}</td>
              <td style="padding:8px;border:1px solid #ddd">{r['scope']}</td>
              <td style="padding:8px;border:1px solid #ddd">{r['category']}</td>
              <td style="padding:8px;border:1px solid #ddd">{r['month']}</td>
              <td style="padding:8px;border:1px solid #ddd">{r['spend']}</td>
              <td style="padding:8px;border:1px solid #ddd">{r['cap']}</td>
              <td style="padding:8px;border:1px solid #ddd">{r['remaining']}</td>
              <td style="padding:8px;border:1px solid #ddd">{r['pct']}</td>
            </tr>
            """
        )

    html_body = f"""
    <div style="font-family: Arial, sans-serif;">
      <h2 style="margin:0 0 10px 0;">Personal Finance Alerts</h2>
      <p style="margin:0 0 14px 0;">These items are <b>NEAR</b> or <b>OVER</b> the configured caps.</p>

      <table style="border-collapse:collapse; width:100%; font-size:14px;">
        <thead>
          <tr>
            <th style="text-align:left;padding:8px;border:1px solid #ddd;">Status</th>
            <th style="text-align:left;padding:8px;border:1px solid #ddd;">Scope</th>
            <th style="text-align:left;padding:8px;border:1px solid #ddd;">Category</th>
            <th style="text-align:left;padding:8px;border:1px solid #ddd;">Month</th>
            <th style="text-align:left;padding:8px;border:1px solid #ddd;">Spend</th>
            <th style="text-align:left;padding:8px;border:1px solid #ddd;">Cap</th>
            <th style="text-align:left;padding:8px;border:1px solid #ddd;">Remaining</th>
            <th style="text-align:left;padding:8px;border:1px solid #ddd;">Util</th>
          </tr>
        </thead>
        <tbody>
          {''.join(html_rows)}
        </tbody>
      </table>

      <p style="margin-top:14px;color:#666;font-size:12px;">
        Sent by Personal Finance Trend Analyzer.
      </p>
    </div>
    """

    return text_body, html_body


def send_email_alerts(
    alerts_df: pd.DataFrame,
    subject: str,
    recipients: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Send an email for NEAR/OVER alerts. Returns a status dict for UI display.
    """
    try:
        cfg = SmtpConfig.from_env()
    except Exception as e:
        return {"ok": False, "error": f"SMTP config error: {e}"}

    to_list = recipients if recipients else _default_recipients(os.getenv("ALERT_EMAIL_TO", ""))
    if not to_list:
        return {
            "ok": False,
            "error": "No recipients configured. Set ALERT_EMAIL_TO or SMTP_FROM/SMTP_USER in env/.env.",
        }

    # Filter only actionable alerts
    actionable = (
        alerts_df[alerts_df["status"].isin(["NEAR", "OVER"])].copy()
        if "status" in alerts_df.columns
        else pd.DataFrame()
    )
    if actionable.empty:
        return {"ok": True, "skipped": True, "message": "No NEAR/OVER alerts to send."}

    text_body, html_body = _alerts_to_message_tables(actionable)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg.from_addr
    msg["To"] = ", ".join(to_list)

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if cfg.use_tls:
            with smtplib.SMTP(cfg.host, cfg.port, timeout=20) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(cfg.user, cfg.password)
                server.sendmail(cfg.from_addr, to_list, msg.as_string())
        else:
            # If your provider uses SSL on 465, set SMTP_PORT=465 and SMTP_USE_TLS=false,
            # then switch to SMTP_SSL here.
            with smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=20, context=ssl.create_default_context()) as server:
                server.login(cfg.user, cfg.password)
                server.sendmail(cfg.from_addr, to_list, msg.as_string())

        return {"ok": True, "sent_to": to_list, "count": int(len(actionable))}
    except Exception as e:
        return {"ok": False, "error": f"SMTP send failed: {e}"}


def send_email(subject: str, body: str, recipients: Optional[List[str]] = None) -> Optional[str]:
    """
    Send a plain-text email. Returns None on success, or an error string.
    """
    try:
        cfg = SmtpConfig.from_env()
    except Exception as e:
        return f"SMTP config error: {e}"

    to_list = recipients if recipients else _default_recipients(os.getenv("ALERT_EMAIL_TO", ""))
    if not to_list:
        return "No recipients configured. Set ALERT_EMAIL_TO or SMTP_FROM/SMTP_USER in env/.env."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg.from_addr
    msg["To"] = ", ".join(to_list)
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        if cfg.use_tls:
            with smtplib.SMTP(cfg.host, cfg.port, timeout=20) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(cfg.user, cfg.password)
                server.sendmail(cfg.from_addr, to_list, msg.as_string())
        else:
            with smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=20, context=ssl.create_default_context()) as server:
                server.login(cfg.user, cfg.password)
                server.sendmail(cfg.from_addr, to_list, msg.as_string())
        return None
    except Exception as e:
        return f"SMTP send failed: {e}"


def send_telegram(message: str) -> Dict[str, Any]:
    """
    Send a Telegram message. Returns a status dict for UI display.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return {"ok": False, "error": "Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID."}

    try:
        import requests

        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=20,
        )
        if resp.ok:
            return {"ok": True}
        return {"ok": False, "error": f"Telegram send failed: {resp.status_code} {resp.text}"}
    except Exception as e:
        return {"ok": False, "error": f"Telegram send failed: {e}"}


def send_alerts(alerts_df: pd.DataFrame, subject_prefix: str = "Personal Finance") -> Dict[str, Any]:
    """
    Main entrypoint used by app.py.
    Email (SMTP) + Telegram (if configured).
    """
    recipients = _default_recipients(os.getenv("ALERT_EMAIL_TO", ""))
    subject = f"{subject_prefix} - Budget Alerts"

    email_res = send_email_alerts(alerts_df, subject=subject, recipients=recipients)

    actionable = (
        alerts_df[alerts_df["status"].isin(["NEAR", "OVER"])].copy()
        if "status" in alerts_df.columns
        else pd.DataFrame()
    )
    if actionable.empty:
        telegram_res = {"ok": True, "skipped": True, "message": "No NEAR/OVER alerts to send."}
    else:
        text_body, _ = _alerts_to_message_tables(actionable)
        telegram_res = send_telegram(text_body)

    return {"email": email_res, "telegram": telegram_res}
