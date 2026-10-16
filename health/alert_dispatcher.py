#!/usr/bin/env python3
import argparse
import json
import os
import sqlite3
import tempfile
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(os.environ.get("N4L_HEALTH_ROOT", "/var/lib/news4legends/health"))
ROOT.mkdir(parents=True, exist_ok=True)
DB = ROOT / "metrics.sqlite3"
STATE = ROOT / "alert-dispatcher-state.json"
WEBHOOK = os.environ.get("N4L_HEALTH_WEBHOOK_URL", "")
DASHBOARD_URL = os.environ.get("N4L_HEALTH_DASHBOARD_URL", "")
TIMEZONE = os.environ.get("TZ", "UTC")

def save_state(last_id):
    fd, tmp = tempfile.mkstemp(prefix=".alert-state-", dir=ROOT)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump({"last_delivered_id": last_id}, f)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, STATE)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def send(message):
    if not WEBHOOK:
        print("Notification skipped: N4L_HEALTH_WEBHOOK_URL is not configured")
        return False
    payload = json.dumps({"message": message}).encode()
    request = urllib.request.Request(
        WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f"Webhook returned HTTP {response.status}")
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    if args.test:
        if send("🧪 NEWS 4 LEGENDS SYSTEM HEALTH\nAlert delivery test.\nNo production incident was generated."):
            print("PASS: test webhook accepted notification")
        return

    if not WEBHOOK:
        print("Notification skipped: N4L_HEALTH_WEBHOOK_URL is not configured")
        return

    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        latest = db.execute(
            "SELECT COALESCE(MAX(id),0) FROM incident_events"
        ).fetchone()[0]

        if not STATE.exists():
            save_state(latest)
            print(f"Initialized cursor at event {latest}; historical events skipped")
            return

        cursor = int(json.loads(STATE.read_text())["last_delivered_id"])
        if cursor > latest:
            raise RuntimeError("Alert cursor exceeds journal maximum; investigate database reset")

        rows = db.execute(
            """SELECT id,ts,metric,event,value,baseline,reason
               FROM incident_events
               WHERE id>?
               ORDER BY id
               LIMIT 100""",
            (cursor,),
        ).fetchall()

    for event_id, ts, metric, event, value, baseline, reason in rows:
        label = "🚨 INCIDENT OPENED" if event == "OPEN" else (
            "✅ INCIDENT RECOVERED" if event == "RECOVERED" else None
        )
        if label is None:
            raise RuntimeError(f"Unknown event type {event!r} at ID {event_id}")

        timestamp = datetime.fromtimestamp(
            ts, ZoneInfo(TIMEZONE)
        ).strftime("%Y-%m-%d %H:%M:%S %Z")

        message = (
            f"{label} — NEWS 4 LEGENDS\n"
            f"Metric: {metric}\n"
            f"Value: {value:g}\n"
            f"Reason: {reason}\n"
            f"Time: {timestamp}\n"
            f"Event ID: {event_id}\n"
            + (f"Dashboard: {DASHBOARD_URL}" if DASHBOARD_URL else "")
        )
        if send(message):
            save_state(event_id)
        print(f"Delivered {event} event {event_id}: {metric}")

    if not rows:
        print("No new incident events")

if __name__ == "__main__":
    main()
