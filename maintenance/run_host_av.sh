#!/bin/bash
set -Eeuo pipefail
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT="${NEWS4LEGENDS_MAINTENANCE_ROOT:-$SCRIPT_DIR}"
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

NEWS4LEGENDS_MAINTENANCE_ROOT="$ROOT" "$SCRIPT_DIR/scan_host_av.sh" > "$TMP"

# Send detections even if scan also encountered an error.
NEWS4LEGENDS_MAINTENANCE_ROOT="$ROOT" \
  python3 "$SCRIPT_DIR/send_security_event.py" malware < "$TMP"

python3 - "$ROOT/reports/clamav-current.json" <<'PY'
import json, sys
report = json.load(open(sys.argv[1]))
print("ClamAV:", report["status"])
if report["exit_code"] not in (0, 1):
    raise SystemExit("ClamAV scan error; check clamav-latest.log")
PY
