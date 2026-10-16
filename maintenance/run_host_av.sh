#!/bin/bash
set -Eeuo pipefail
ROOT="${NEWS4LEGENDS_MAINTENANCE_ROOT:-/var/lib/news4legends/maintenance}"
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

"$ROOT/scan_host_av.sh" > "$TMP"

# Send detections even if scan also encountered an error.
python3 "$ROOT/send_security_event.py" malware < "$TMP"

python3 - "$ROOT/reports/clamav-current.json" <<'PY'
import json, sys
report = json.load(open(sys.argv[1]))
print("ClamAV:", report["status"])
if report["exit_code"] not in (0, 1):
    raise SystemExit("ClamAV scan error; check clamav-latest.log")
PY
