#!/usr/bin/env python3
import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

root = Path(os.environ.get("NEWS4LEGENDS_MAINTENANCE_ROOT", "/var/lib/news4legends/maintenance"))
state = root / "state"
state.mkdir(parents=True, exist_ok=True)

kind = sys.argv[1]
payload = json.load(sys.stdin)
items = payload.get("items", [])
webhook = os.environ.get("N4L_SECURITY_WEBHOOK_URL", "")

if not items:
    print(f"{kind}: no urgent findings")
    sys.exit(0)

if not webhook:
    print(f"{kind}: notification skipped; N4L_SECURITY_WEBHOOK_URL is not configured")
    sys.exit(0)

# Fingerprint individual events to avoid repeat alerts.
sent = state / f"{kind}-notified.json"
previous = json.loads(sent.read_text()) if sent.exists() else {}
current = {}

for item in items:
    fingerprint = hashlib.sha256(
        json.dumps(item, sort_keys=True).encode()
    ).hexdigest()
    key = hashlib.sha256(
        (kind + ":" + item["identity"]).encode()
    ).hexdigest()
    current[key] = fingerprint

    if previous.get(key) == fingerprint:
        continue

    message = item["message"][:3500]
    body = json.dumps({"message": message}).encode()
    request = urllib.request.Request(
        webhook,
        data=body,
        headers={"Content-Type": "application/json"},
    )

    # Record delivery only after the webhook accepts the request.
    with urllib.request.urlopen(request, timeout=30) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Webhook HTTP {response.status}")

    previous[key] = fingerprint
    sent.write_text(json.dumps(previous, indent=2) + "\n")
    print(f"{kind}: webhook accepted event {item['identity']}")

# Forget resolved events, allowing future recurrence to alert again.
sent.write_text(json.dumps(
    {k: v for k, v in previous.items() if k in current},
    indent=2
) + "\n")
