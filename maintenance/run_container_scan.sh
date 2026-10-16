#!/bin/bash
set -Eeuo pipefail

ROOT="${NEWS4LEGENDS_MAINTENANCE_ROOT:-/var/lib/news4legends/maintenance}"
REPORTS="$ROOT/reports"
CACHE="$ROOT/state/trivy-cache"
mkdir -p "$REPORTS/container-images" "$CACHE"

SCANNER_IMAGE="${N4L_TRIVY_IMAGE:-aquasec/trivy:latest}"
docker image inspect "$SCANNER_IMAGE" >/dev/null 2>&1 ||
  docker pull "$SCANNER_IMAGE"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

docker ps -q | xargs -r docker inspect   --format '{{.Image}}' | sort -u > "$TMP/images.txt"
printf '[]\n' > "$TMP/all-alerts.json"
: > "$TMP/skipped-images.txt"

while IFS= read -r IMAGE; do
    test -n "$IMAGE" || continue
    ID=$(printf '%s' "$IMAGE" | sha256sum | cut -c1-16)
    echo "Scanning image: $IMAGE"

    if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
        echo "WARNING: image unavailable for export: $IMAGE"
        printf '%s\n' "$IMAGE" >> "$TMP/skipped-images.txt"
        continue
    fi

    if ! docker save -o "$TMP/image.tar" "$IMAGE"; then
        echo "WARNING: image export failed: $IMAGE"
        printf '%s\n' "$IMAGE" >> "$TMP/skipped-images.txt"
        rm -f "$TMP/image.tar"
        continue
    fi

    docker run --rm \
      --network bridge \
      -v "$TMP:/scan:ro" \
      -v "$CACHE:/root/.cache/" \
      "$SCANNER_IMAGE" image \
        --input /scan/image.tar \
        --scanners vuln \
        --severity HIGH,CRITICAL \
        --format json \
        --output /root/.cache/scan-result.json

    cp "$CACHE/scan-result.json" \
      "$REPORTS/container-images/$ID.json"

    python3 - "$REPORTS/container-images/$ID.json" "$IMAGE" <<'PY' > "$TMP/alerts.json"
import json, sys
report = json.load(open(sys.argv[1]))
image = sys.argv[2]
items = []

for result in report.get("Results", []):
    target = result.get("Target", "unknown")
    for vuln in result.get("Vulnerabilities") or []:
        severity = vuln.get("Severity", "").upper()
        if severity not in ("HIGH", "CRITICAL"):
            continue

        cve = vuln.get("VulnerabilityID", "Unknown")
        pkg = vuln.get("PkgName", "Unknown")
        installed = vuln.get("InstalledVersion", "Unknown")
        fixed = vuln.get("FixedVersion") or "No fix published"
        advisory = (
            vuln.get("PrimaryURL")
            or f"https://nvd.nist.gov/vuln/detail/{cve}"
        )

        items.append({
            "identity": f"{image}:{target}:{pkg}:{cve}",
            "message": (
                f"🚨 {severity} CONTAINER VULNERABILITY\n\n"
                f"Image: {image}\n"
                f"Target: {target}\n"
                f"Package: {pkg}\n"
                f"Installed: {installed}\n"
                f"Vulnerability: {cve}\n"
                f"Fixed version: {fixed}\n"
                f"Description: {vuln.get('Title') or vuln.get('Description', '')[:350]}\n"
                f"Official reference: {advisory}\n\n"
                "Review the advisory and compatible image update. "
                "Verify backups before making any change. "
                "No automatic update has been performed."
            )
        })

print(json.dumps({"items": items}))
PY
    python3 - "$TMP/all-alerts.json" "$TMP/alerts.json" <<'PYMERGE'
import json, sys
from pathlib import Path
combined = Path(sys.argv[1])
new = json.loads(Path(sys.argv[2]).read_text()).get("items", [])
items = json.loads(combined.read_text())
items.extend(new)
combined.write_text(json.dumps(items))
PYMERGE

    rm -f "$TMP/image.tar"
done < "$TMP/images.txt"

python3 - "$TMP/all-alerts.json" > "$TMP/events.json" <<'PYEVENTS'
import json, sys
print(json.dumps({"items": json.load(open(sys.argv[1]))}))
PYEVENTS

if [ -s "$TMP/skipped-images.txt" ]; then
    cp "$TMP/skipped-images.txt" "$REPORTS/container-scan-skipped-images.txt"
    rm -f "$REPORTS/container-scan-last-success.txt"
    echo "WARNING: incomplete scan coverage; skipped images:"
    cat "$TMP/skipped-images.txt"
    echo "Available-image findings will still be processed."
    SCAN_PARTIAL=1
else
    SCAN_PARTIAL=0
    rm -f "$REPORTS/container-scan-skipped-images.txt"
fi

if [ "${N4L_SCAN_VALIDATE_ONLY:-0}" = "1" ]; then
    echo "VALIDATION ONLY: Telegram delivery skipped"
else
    python3 "$ROOT/send_security_event.py" container < "$TMP/events.json"
fi

if [ "$SCAN_PARTIAL" -eq 1 ]; then
    echo "PARTIAL: available images scanned; missing images remain recorded"
    exit 2
fi

date -u +%FT%TZ > "$REPORTS/container-scan-last-success.txt"
