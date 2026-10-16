from pathlib import Path
import sqlite3

SCHEMA_VERSION = 2
BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"


V1_TABLES = {
    "profiles", "sources", "profile_sources",
    "profile_keywords", "profile_entities",
}


def _migrate_v1_to_v2(db: sqlite3.Connection) -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    # CREATE IF NOT EXISTS statements add the v2 objects while preserving v1
    # rows. PRAGMA user_version is applied only after the transaction succeeds.
    db.executescript("BEGIN IMMEDIATE;\n" + schema.replace(
        "PRAGMA user_version = 2;", ""
    ) + "\nPRAGMA user_version = 2;\nCOMMIT;")


def bootstrap_database(db_path: str) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path, timeout=30) as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 30000")
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

        if version == 1 and V1_TABLES <= tables:
            _migrate_v1_to_v2(db)
            return

        if version > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {version} is newer than supported "
                f"version {SCHEMA_VERSION}. Refusing to modify it."
            )

        raise RuntimeError(
            f"Unsupported database schema version {version}; "
            f"expected {SCHEMA_VERSION}. Refusing to modify the database."
        )
