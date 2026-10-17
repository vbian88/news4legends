#!/bin/sh
set -eu

test "$#" -eq 1 || { echo "Usage: $0 BACKUP.sqlite3" >&2; exit 2; }
backup=$1
DB_PATH=${NEWS4LEGENDS_DB_PATH:-/data/home-ai-news.db}
test -s "$backup" || { echo "Backup is missing or empty" >&2; exit 1; }
test -f "$backup.sha256" && (cd "$(dirname "$backup")" && sha256sum -c "$(basename "$backup").sha256")

python3 - "$backup" <<'PY'
import sqlite3, sys
with sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True) as db:
    result = db.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise SystemExit(f"Backup integrity check failed: {result}")
PY

if [ -e "$DB_PATH" ] && [ "${NEWS4LEGENDS_RESTORE_CONFIRM:-}" != "RESTORE" ]; then
  echo "Refusing to overwrite $DB_PATH. Set NEWS4LEGENDS_RESTORE_CONFIRM=RESTORE." >&2
  exit 1
fi
mkdir -p "$(dirname "$DB_PATH")"
cp "$backup" "$DB_PATH.restore-tmp"
mv "$DB_PATH.restore-tmp" "$DB_PATH"
chmod 600 "$DB_PATH"
printf 'Restore complete: %s\n' "$DB_PATH"
