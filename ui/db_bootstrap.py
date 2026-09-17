from pathlib import Path
import sqlite3

SCHEMA_VERSION = 1
BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"


def bootstrap_database(db_path: str) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys = ON")
        version = db.execute("PRAGMA user_version").fetchone()[0]

        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }

        if version == 0 and not tables:
            db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            db.commit()
            return

        if version == SCHEMA_VERSION:
            return

        raise RuntimeError(
            f"Unsupported database schema version {version}; "
            f"expected {SCHEMA_VERSION}. Refusing to modify the database."
        )
