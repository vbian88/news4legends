#!/bin/bash
set -Eeuo pipefail
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT="${NEWS4LEGENDS_MAINTENANCE_ROOT:-$SCRIPT_DIR}"
REPORTS="$ROOT/reports"
mkdir -p "$REPORTS"

LOG="$REPORTS/clamav-latest.log"
JSON="$REPORTS/clamav-current.json"
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

set +e
IFS=':' read -r -a TARGETS <<< "${N4L_CLAMAV_TARGETS:-/app:/var/lib/news4legends}"
clamscan --recursive --infected \
  --exclude='\.db$|\.sqlite3?$|\.sqlite3?-(wal|shm)$' \
  --exclude-dir='/(node_modules|__pycache__|\.git)(/|$)' \
  "${TARGETS[@]}" \
  > "$TMP" 2>&1
RC=$?
set -e

cp "$TMP" "$LOG"

python3 - "$TMP" "$JSON" "$RC" <<'PY'
import datetime, json, os, pathlib, re, sys

log = pathlib.Path(sys.argv[1]).read_text(errors="replace")
destination = pathlib.Path(sys.argv[2])
rc = int(sys.argv[3])
detections = []

for line in log.splitlines():
    if line.endswith(" FOUND") and ": " in line:
        path, detection = line.rsplit(": ", 1)
        detections.append({
            "path": path,
            "detection": detection.removesuffix(" FOUND")
        })

report = {
    "timestamp": datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat(),
    "exit_code": rc,
    "status": "infected" if detections else (
        "clean" if rc == 0 else "error"
    ),
    "detections": detections,
    "targets": os.environ.get("N4L_CLAMAV_TARGETS", "/app:/var/lib/news4legends").split(":")
}
destination.write_text(json.dumps(report, indent=2) + "\n")

items = []
for d in detections:
    items.append({
        "identity": d["path"] + ":" + d["detection"],
        "message": (
            "🚨 NEWS 4 LEGENDS — MALWARE DETECTED\n\n"
            f"Host: {os.environ.get('N4L_HOST_LABEL', 'News 4 Legends host')}\n"
            f"Detection: {d['detection']}\n"
            f"File: {d['path']}\n\n"
            "Reference: https://www.clamav.net/\n"
            "Action: verify detection and affected component, "
            "preserve evidence, isolate if necessary, and follow "
            "vendor removal guidance.\n"
            "No file has been automatically deleted or quarantined."
        )
    })

print(json.dumps({"items": items}))
PY
