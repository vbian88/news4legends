#!/bin/bash
set -Eeuo pipefail

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE="${N4L_SECURITY_ENV_FILE:-/etc/news4legends/security.env}"
CRON_FILE="${N4L_SECURITY_CRON_FILE:-/etc/cron.d/news4legends-security}"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo; host and Docker scanning require an administrator." >&2
    exit 1
fi
test -f "$ENV_FILE" || {
    echo "Create $ENV_FILE from maintenance/security.env.example first." >&2
    exit 1
}
test "$(stat -c %a "$ENV_FILE")" = 600 || {
    echo "$ENV_FILE must have mode 600." >&2
    exit 1
}
command -v docker >/dev/null
command -v python3 >/dev/null

cat > "$CRON_FILE" <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

17 2 * * * root set -a; source "$ENV_FILE"; set +a; cd "$ROOT" && ./maintenance/run.sh scheduled >> maintenance/reports/schedule.log 2>&1
43 2 * * 0 root set -a; source "$ENV_FILE"; set +a; cd "$ROOT" && ./maintenance/run_container_scan.sh >> maintenance/reports/container-scan.log 2>&1
13 3 * * 0 root set -a; source "$ENV_FILE"; set +a; cd "$ROOT" && ./maintenance/run_debian_scan.sh >> maintenance/reports/debian-scan.log 2>&1
30 8 * * 1 root set -a; source "$ENV_FILE"; set +a; cd "$ROOT" && ./maintenance/run.sh weekly >> maintenance/reports/weekly.log 2>&1
EOF
chmod 644 "$CRON_FILE"

echo "Installed $CRON_FILE. Review it, then verify future report timestamps."
echo "No automatic package or container upgrade is scheduled."
