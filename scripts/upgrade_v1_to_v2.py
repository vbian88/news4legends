#!/usr/bin/env python3
"""Backup and migrate a supported News 4 Legends database to v2."""

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from db_bootstrap import bootstrap_database, is_known_production_v0


def _verified_backup(source: Path, destination: Path) -> None:
    """Create a consistent SQLite backup, including committed WAL content."""
    with sqlite3.connect(source, timeout=30) as source_db:
        with sqlite3.connect(destination, timeout=30) as backup_db:
            source_db.backup(backup_db)
    with sqlite3.connect(destination, timeout=30) as backup_db:
        if backup_db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            destination.unlink(missing_ok=True)
            raise SystemExit("Backup failed integrity_check")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument("--backup-dir", type=Path, required=True)
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error("database does not exist")

    with sqlite3.connect(args.database, timeout=30) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise SystemExit("Source database failed integrity_check")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version != 1 and not is_known_production_v0(db):
            raise SystemExit(
                "Source must be public schema version 1 or the explicitly "
                "supported pre-versioned production layout"
            )

    args.backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = args.backup_dir / f"pre-v2-{stamp}.sqlite3"
    _verified_backup(args.database, backup)
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
