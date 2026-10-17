#!/bin/sh
set -eu

DB_PATH=${NEWS4LEGENDS_DB_PATH:-/data/home-ai-news.db}
BACKUP_DIR=${NEWS4LEGENDS_BACKUP_DIR:-./backups}
mkdir -p "$BACKUP_DIR"
test -f "$DB_PATH" || { echo "Database not found: $DB_PATH" >&2; exit 1; }
stamp=$(date -u +%Y%m%dT%H%M%SZ)
destination="$BACKUP_DIR/news4legends-$stamp.sqlite3"

python3 - "$DB_PATH" "$destination" <<'PY'
import sqlite3, sys
source, destination = sys.argv[1:]
with sqlite3.connect(source, timeout=30) as src, sqlite3.connect(destination) as dst:
    src.backup(dst)
    result = dst.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise SystemExit(f"Backup integrity check failed: {result}")
PY

test -s "$destination"
sha256sum "$destination" > "$destination.sha256"
chmod 600 "$destination" "$destination.sha256"
printf 'Backup created and verified: %s\n' "$destination"
