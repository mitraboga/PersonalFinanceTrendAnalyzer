from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import yaml
from zoneinfo import ZoneInfo


@dataclass
class NotifySettings:
    enabled: bool
    email: bool
    telegram: bool
    frequency: str            # weekly | biweekly | monthly
    timezone: str             # e.g., Asia/Kolkata
    monthly_day: int          # 1-28 recommended
    weekly_weekday: int       # 0=Mon ... 6=Sun

    @staticmethod
    def load(path: str = "config/notify_settings.yml") -> "NotifySettings":
        p = Path(path)
        if not p.exists():
            # safe defaults
            return NotifySettings(
                enabled=False,
                email=False,
                telegram=False,
                frequency="weekly",
                timezone="Asia/Kolkata",
                monthly_day=1,
                weekly_weekday=0,
            )

        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        channels = data.get("channels", {}) or {}
        return NotifySettings(
            enabled=bool(data.get("enabled", True)),
            email=bool(channels.get("email", True)),
            telegram=bool(channels.get("telegram", True)),
            frequency=str(data.get("frequency", "weekly")).lower().strip(),
            timezone=str(data.get("timezone", "Asia/Kolkata")),
            monthly_day=int(data.get("monthly_day", 1)),
            weekly_weekday=int(data.get("weekly_weekday", 0)),
        )

    def save(self, path: str = "config/notify_settings.yml") -> None:
        out = {
            "enabled": self.enabled,
            "channels": {"email": self.email, "telegram": self.telegram},
            "frequency": self.frequency,
            "timezone": self.timezone,
            "monthly_day": self.monthly_day,
            "weekly_weekday": self.weekly_weekday,
        }
        Path(path).write_text(yaml.safe_dump(out, sort_keys=False), encoding="utf-8")


def _read_state(path: str = "state/notify_state.json") -> Optional[date]:
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        s = data.get("last_sent_date")
        if not s:
            return None
        return date.fromisoformat(s)
    except Exception:
        return None


def _write_state(last_sent: date, path: str = "state/notify_state.json") -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps({"last_sent_date": last_sent.isoformat()}, indent=2), encoding="utf-8")


def is_due_today(settings: NotifySettings, now: Optional[datetime] = None) -> bool:
    tz = ZoneInfo(settings.timezone)
    now = now.astimezone(tz) if now else datetime.now(tz)
    today = now.date()

    last = _read_state()

    # If globally disabled, never due
    if not settings.enabled:
        return False

    freq = settings.frequency
    if freq not in {"weekly", "biweekly", "monthly"}:
        freq = "weekly"

    if freq in {"weekly", "biweekly"}:
        # Only trigger on the chosen weekday
        if today.weekday() != settings.weekly_weekday:
            return False

        if freq == "weekly":
            # If we already sent today, skip
            return last != today

        # biweekly: need at least 14 days since last send (or never sent)
        if last is None:
            return True
        return (today - last).days >= 14

    # monthly
    # only trigger on monthly_day (clamp to 28 to avoid month length issues)
    day = max(1, min(int(settings.monthly_day), 28))
    if today.day != day:
        return False
    return last != today


def mark_sent_today(settings: NotifySettings, now: Optional[datetime] = None) -> None:
    tz = ZoneInfo(settings.timezone)
    now = now.astimezone(tz) if now else datetime.now(tz)
    _write_state(now.date())