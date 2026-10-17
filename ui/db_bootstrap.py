from pathlib import Path
import sqlite3

SCHEMA_VERSION = 2
BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"


V1_TABLES = {
    "profiles", "sources", "profile_sources",
    "profile_keywords", "profile_entities",
}

# Fingerprint of the authenticated production layout that predates formal
# PRAGMA user_version tracking.  Column order and declared types are checked so
# an arbitrary version-0 database cannot be mistaken for this known layout.
PRODUCTION_V0_COLUMNS = {
    "profiles": (("id", "INTEGER"), ("slug", "TEXT"), ("name", "TEXT"),
                 ("enabled", "INTEGER"), ("topic", "TEXT"),
                 ("minimum_source_score", "INTEGER"),
                 ("maximum_age_hours", "INTEGER"),
                 ("similarity_threshold", "REAL"), ("llm_enabled", "INTEGER"),
                 ("llm_limit", "INTEGER"),
                 ("max_total_collection_seconds", "INTEGER"),
                 ("max_total_requests", "INTEGER"),
                 ("max_total_articles", "INTEGER"),
                 ("max_llm_calls", "INTEGER"),
                 ("telegram_enabled", "INTEGER"), ("email_theme", "TEXT")),
    "sources": (("id", "INTEGER"), ("name", "TEXT")),
    "profile_sources": (
        ("id", "INTEGER"), ("profile_id", "INTEGER"),
        ("source_id", "INTEGER"), ("enabled", "INTEGER"),
        ("collector_type", "TEXT"), ("listing_url", "TEXT"),
        ("topic_focused", "INTEGER"), ("credibility_score", "INTEGER"),
        ("source_type", "TEXT"), ("max_candidates", "INTEGER"),
        ("max_fetches", "INTEGER"), ("request_timeout_seconds", "REAL"),
        ("max_source_runtime_seconds", "REAL"),
        ("stop_after_consecutive_stale", "INTEGER"),
        ("validation_status", "TEXT"), ("validation_reason", "TEXT"),
        ("validated_at", "TEXT")),
    "profile_keywords": (("profile_id", "INTEGER"), ("keyword", "TEXT")),
    "profile_entities": (("profile_id", "INTEGER"), ("entity", "TEXT")),
    "auth_users": (("id", "INTEGER"), ("username", "TEXT"),
                   ("password_hash", "TEXT"), ("role", "TEXT"),
                   ("active", "INTEGER"), ("created_at", "TEXT")),
    "auth_sessions": (("token_hash", "TEXT"), ("user_id", "INTEGER"),
                      ("csrf_token", "TEXT"), ("expires_at", "TEXT")),
    "auth_profile_assignments": (("user_id", "INTEGER"),
                                 ("profile_id", "INTEGER")),
    "api_tokens": (("id", "INTEGER"), ("user_id", "INTEGER"),
                   ("name", "TEXT"), ("token_hash", "TEXT"),
                   ("scopes", "TEXT"), ("created_at", "INTEGER"),
                   ("expires_at", "INTEGER"), ("last_used_at", "INTEGER"),
                   ("revoked_at", "INTEGER")),
    "api_token_audit": (("id", "INTEGER"),
                        ("actor_user_id", "INTEGER"),
                        ("token_id", "INTEGER"), ("action", "TEXT"),
                        ("created_at", "INTEGER")),
}


def _columns(db: sqlite3.Connection, table: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        (row[1], (row[2] or "").upper())
        for row in db.execute(f'PRAGMA table_info("{table}")')
    )


def is_known_production_v0(db: sqlite3.Connection) -> bool:
    """Return true only for the explicitly supported pre-versioned layout."""
    if db.execute("PRAGMA user_version").fetchone()[0] != 0:
        return False
    return all(
        _columns(db, table) == expected
        for table, expected in PRODUCTION_V0_COLUMNS.items()
    )


def _migrate_v1_to_v2(db: sqlite3.Connection) -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    # CREATE IF NOT EXISTS statements add the v2 objects while preserving v1
    # rows. PRAGMA user_version is applied only after the transaction succeeds.
    db.executescript("BEGIN IMMEDIATE;\n" + schema.replace(
        "PRAGMA user_version = 2;", ""
    ) + "\nPRAGMA user_version = 2;\nCOMMIT;")


def _migrate_production_v0_to_v2(db: sqlite3.Connection) -> None:
    # The known production tables already contain the accepted application,
    # authentication and API data.  CREATE IF NOT EXISTS leaves them and any
    # unrelated/test tables untouched, while adding only missing v2 objects.
    _migrate_v1_to_v2(db)


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

        if version == 0 and is_known_production_v0(db):
            _migrate_production_v0_to_v2(db)
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
