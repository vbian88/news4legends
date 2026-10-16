#!/usr/bin/env python3
"""Backup and migrate a News 4 Legends v1 SQLite database to v2."""

import argparse
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from db_bootstrap import bootstrap_database


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument("--backup-dir", type=Path, required=True)
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error("database does not exist")

    with sqlite3.connect(args.database) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise SystemExit("Source database failed integrity_check")
        if db.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise SystemExit("Source must be schema version 1")

    args.backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = args.backup_dir / f"pre-v2-{stamp}.sqlite3"
    shutil.copy2(args.database, backup)
    if not backup.stat().st_size:
        raise SystemExit("Backup is empty")

    bootstrap_database(str(args.database))
    with sqlite3.connect(args.database) as db:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    if version != 2 or integrity != "ok":
        raise SystemExit(f"Upgrade validation failed; restore {backup}")
    print(f"Upgrade complete. Verified backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
