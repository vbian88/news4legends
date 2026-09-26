#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT="${NEWS4LEGENDS_MAINTENANCE_ROOT:-$SCRIPT_DIR}"
STATE="${NEWS4LEGENDS_MAINTENANCE_STATE_DIR:-$ROOT/state}"
REPORTS="${NEWS4LEGENDS_MAINTENANCE_REPORTS_DIR:-$ROOT/reports}"
WEBHOOK="${NEWS4LEGENDS_MAINTENANCE_WEBHOOK:-}"

MODE="${1:-manual}"
case "$MODE" in
    manual|scheduled|weekly) ;;
    *) printf 'Usage: %s [manual|scheduled|weekly]\n' "$0" >&2; exit 2 ;;
esac

mkdir -p "$STATE" "$REPORTS"

"$SCRIPT_DIR/check.py" > "$REPORTS/weekly.txt"
"$SCRIPT_DIR/classify.py" > "$REPORTS/classifier-run.txt"
"$SCRIPT_DIR/summarize.py" > "$REPORTS/summary-run.txt"
"$SCRIPT_DIR/build_alert.py" > "$REPORTS/build-alert-run.txt"

COUNTS=$(jq -c '.counts' "$REPORTS/current.json")
CRITICAL=$(jq -r '.counts.critical // 0' "$REPORTS/current.json")
HIGH=$(jq -r '.counts.high // 0' "$REPORTS/current.json")
MEDIUM=$(jq -r '.counts.medium // 0' "$REPORTS/current.json")
LOW=$(jq -r '.counts.low // 0' "$REPORTS/current.json")
REVIEW=$(jq -r '.counts.uncertain // .counts.review // 0' "$REPORTS/current.json")

# Fingerprint ONLY confirmed Critical/High findings.
FINGERPRINT=$(
    jq -S -c '
      [.findings[]
       | select((.severity|ascii_upcase)=="CRITICAL"
             or (.severity|ascii_upcase)=="HIGH")
       | {service,installed,id,severity,matches}]
      | sort_by(.service,.id)
    ' "$REPORTS/current.json" | sha256sum | awk '{print $1}'
)

OLD=$(cat "$STATE/last-critical-high.sha256" 2>/dev/null || true)

send_message() {
    MSGFILE="$1"
    if [ -z "$WEBHOOK" ]; then
        printf 'ALERT=SKIPPED REASON=WEBHOOK_NOT_CONFIGURED\n'
        return 1
    fi
    jq -Rs '{message:.}' < "$MSGFILE" |
        curl -fsS --max-time 20 \
          -H 'Content-Type: application/json' \
          --data-binary @- \
          "$WEBHOOK" >/dev/null
}

if [ "$MODE" = "weekly" ]; then
    {
        printf '🛡 NEWS 4 LEGENDS — WEEKLY SECURITY\n\n'
        printf 'Critical: %s\nHigh: %s\nMedium: %s\nLow: %s\nManual review: %s\n' \
          "$CRITICAL" "$HIGH" "$MEDIUM" "$LOW" "$REVIEW"
        if [ "$CRITICAL" -gt 0 ] || [ "$HIGH" -gt 0 ]; then
            printf '\n'
            cat "$REPORTS/telegram-security.txt"
        else
            printf '\nNo confirmed Critical/High findings.\n'
        fi
        printf '\nSecurity dashboard: %s\n' \
          "${NEWS4LEGENDS_SECURITY_URL:-http://localhost:8081/security}"
        printf 'Best-effort monitoring: validate applicability against the linked vendor advisory before making changes.\n'
        printf 'No automatic upgrade has been performed.\n'
    } > "$REPORTS/weekly-telegram.txt"

    if send_message "$REPORTS/weekly-telegram.txt"; then
        printf '%s\n' "$FINGERPRINT" > "$STATE/last-critical-high.sha256"
        printf 'ALERT=YES TYPE=WEEKLY\n'
    fi

elif [ "$MODE" = "scheduled" ]; then
    if { [ "$CRITICAL" -gt 0 ] || [ "$HIGH" -gt 0 ]; } &&
       [ "$FINGERPRINT" != "$OLD" ]; then
        if send_message "$REPORTS/telegram-security.txt"; then
            printf '%s\n' "$FINGERPRINT" > "$STATE/last-critical-high.sha256"
            printf 'ALERT=YES TYPE=URGENT_NEW_OR_CHANGED_CRITICAL_HIGH\n'
        fi
    else
        printf 'ALERT=NO\n'
    fi

else
    # Manual runs deliberately update reports/UI/history only.
    printf 'ALERT=NO MODE=MANUAL\n'
fi

printf 'COUNTS=%s\n' "$COUNTS"
