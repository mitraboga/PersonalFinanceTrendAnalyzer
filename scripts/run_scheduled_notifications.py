"""
Run scheduled summaries based on state/notify_state.json.

This is intended for GitHub Actions. It evaluates schedule settings in UTC
and triggers weekly_summary.py when a schedule is due.
"""
from __future__ import annotations

# >>> .env loader first
from dotenv import load_dotenv
load_dotenv()

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from pipeline.schedule import load_notify_state, due_summaries


SCHEDULE_CONFIG = {
    "weekly": {"days": 7, "label": "Weekly"},
    "biweekly": {"days": 14, "label": "Bi-Weekly"},
    "monthly": {"days": 30, "label": "Monthly"},
}


def _run_summary(label: str, days: int, input_glob: str, output: str) -> int:
    env = os.environ.copy()
    env["SUMMARY_LABEL"] = label
    cmd = [
        sys.executable,
        "scripts/weekly_summary.py",
        "--input_glob",
        input_glob,
        "--output",
        output,
        "--days",
        str(days),
        "--notify",
    ]
    print(f"[RUN] {label} summary ({days} days)")
    return subprocess.call(cmd, env=env)


def main() -> int:
    ap = argparse.ArgumentParser(description="Scheduled notifications runner")
    ap.add_argument("--state_path", default="state/notify_state.json", help="Path to notify_state.json")
    ap.add_argument("--input_glob", default="data/*.csv", help="Glob for CSV/Excel files")
    ap.add_argument("--output", default="outputs", help="Output folder for artifacts")
    ap.add_argument("--grace_minutes", type=int, default=15, help="Grace window after scheduled time")
    args = ap.parse_args()

    state = load_notify_state(Path(args.state_path))
    schedule = state.get("schedule", {})
    now = datetime.now(timezone.utc)
    due = due_summaries(schedule, now=now, grace_minutes=args.grace_minutes)
    if not due:
        print("[SKIP] No scheduled summaries due.")
        return 0

    exit_code = 0
    for key in due:
        meta = SCHEDULE_CONFIG.get(key)
        if not meta:
            print(f"[WARN] Unknown schedule key: {key}")
            continue
        rc = _run_summary(meta["label"], meta["days"], args.input_glob, args.output)
        if rc != 0:
            exit_code = rc
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
