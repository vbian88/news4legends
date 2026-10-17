#!/bin/bash
set -Eeuo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DATA_ROOT="${NEWS4LEGENDS_MAINTENANCE_ROOT:-$SCRIPT_DIR}"
REPORTS="$DATA_ROOT/reports"
CACHE="$DATA_ROOT/state/trivy-cache"
SCANNER_IMAGE="${N4L_TRIVY_IMAGE:-aquasec/trivy:latest}"
mkdir -p "$REPORTS" "$CACHE"

docker image inspect "$SCANNER_IMAGE" >/dev/null 2>&1 || docker pull "$SCANNER_IMAGE"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

docker run --rm --network bridge \
  -v /:/host:ro \
  -v "$CACHE:/root/.cache/" \
  "$SCANNER_IMAGE" rootfs /host \
  --scanners vuln --format json \
  --output /root/.cache/debian-result.json
cp "$CACHE/debian-result.json" "$TMP/debian-result.json"

python3 "$SCRIPT_DIR/vulnerability_report.py" \
  --source debian \
  --reports "$TMP/debian-result.json" \
  --output "$REPORTS/debian-vulnerabilities.json" \
  --history "$REPORTS/debian-vulnerability-trends.json"
NEWS4LEGENDS_MAINTENANCE_ROOT="$DATA_ROOT" \
  python3 "$SCRIPT_DIR/build_remediation_prompt.py"

python3 - "$REPORTS/debian-vulnerabilities.json" <<'PY' | \
  NEWS4LEGENDS_MAINTENANCE_ROOT="$DATA_ROOT" \
  python3 "$SCRIPT_DIR/send_security_event.py" debian
import json, sys
data=json.load(open(sys.argv[1]))
items=[]
for row in data.get("findings", []):
    if row.get("severity") not in ("CRITICAL", "HIGH"):
        continue
    items.append({
        "identity": f"{row['package']}:{row['cve']}",
        "message": (
            f"{row['severity']} DEBIAN VULNERABILITY\n"
            f"Package: {row['package']}\nCVE: {row['cve']}\n"
            f"Installed: {row['installed_version']}\n"
            f"Fixed: {row['fixed_version']}\n"
            "Manual review only; no update was applied."
        ),
    })
print(json.dumps({"items": items}))
PY
