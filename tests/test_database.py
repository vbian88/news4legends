import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ui"))

from db_bootstrap import SCHEMA_VERSION, bootstrap_database


EXPECTED_TABLES = {
    "profiles", "sources", "profile_sources", "profile_keywords",
    "profile_entities", "auth_users", "auth_sessions",
    "auth_login_attempts", "auth_profile_assignments", "api_tokens",
    "api_token_audit",
}


PRODUCTION_V0_SCHEMA = """
CREATE TABLE profiles (id INTEGER, slug TEXT, name TEXT, enabled INTEGER, topic TEXT, minimum_source_score INTEGER, maximum_age_hours INTEGER, similarity_threshold REAL, llm_enabled INTEGER, llm_limit INTEGER, max_total_collection_seconds INTEGER, max_total_requests INTEGER, max_total_articles INTEGER, max_llm_calls INTEGER, telegram_enabled INTEGER, email_theme TEXT);
CREATE TABLE sources (id INTEGER, name TEXT);
CREATE TABLE profile_sources (id INTEGER, profile_id INTEGER, source_id INTEGER, enabled INTEGER, collector_type TEXT, listing_url TEXT, topic_focused INTEGER, credibility_score INTEGER, source_type TEXT, max_candidates INTEGER, max_fetches INTEGER, request_timeout_seconds REAL, max_source_runtime_seconds REAL, stop_after_consecutive_stale INTEGER, validation_status TEXT, validation_reason TEXT, validated_at TEXT);
CREATE TABLE profile_keywords (profile_id INTEGER, keyword TEXT);
CREATE TABLE profile_entities (profile_id INTEGER, entity TEXT);
CREATE TABLE auth_users (id INTEGER, username TEXT, password_hash TEXT, role TEXT, active INTEGER, created_at TEXT);
CREATE TABLE auth_sessions (token_hash TEXT, user_id INTEGER, csrf_token TEXT, expires_at TEXT);
CREATE TABLE auth_profile_assignments (user_id INTEGER, profile_id INTEGER);
CREATE TABLE api_tokens (id INTEGER, user_id INTEGER, name TEXT, token_hash TEXT, scopes TEXT, created_at INTEGER, expires_at INTEGER, last_used_at INTEGER, revoked_at INTEGER);
CREATE TABLE api_token_audit (id INTEGER, actor_user_id INTEGER, token_id INTEGER, action TEXT, created_at INTEGER);
CREATE TABLE _budget_test_restore (profile_source_id INTEGER, max_candidates INTEGER, max_fetches INTEGER);
CREATE TABLE _profile_runtime_restore (profile_id INTEGER, runtime REAL);
CREATE TABLE _runtime_test_restore (profile_source_id INTEGER, runtime REAL);
"""


def create_production_v0(path):
    with sqlite3.connect(path) as db:
        db.executescript(PRODUCTION_V0_SCHEMA)
        db.execute("INSERT INTO profiles VALUES (1,'roma','Roma',1,'football',60,24,0.8,1,7,120,80,25,4,1,'roma')")
        db.execute("INSERT INTO sources VALUES (2,'Example Source')")
        db.execute("INSERT INTO profile_sources VALUES (3,1,2,1,'web','https://example.invalid/news',1,75,'news',10,8,12.5,45.0,4,'PASS','verified','2026-09-26')")
        db.execute("INSERT INTO profile_keywords VALUES (1,'transfer news')")
        db.execute("INSERT INTO profile_entities VALUES (1,'AS Roma')")
        db.execute("INSERT INTO auth_users VALUES (4,'admin','$argon2id$preserved','admin',1,'2026-09-01')")
        db.execute("INSERT INTO auth_sessions VALUES ('session-hash',4,'csrf','4102444800')")
        db.execute("INSERT INTO auth_profile_assignments VALUES (4,1)")
        db.execute("INSERT INTO api_tokens VALUES (5,4,'automation','token-hash','[\"profiles.read\"]',1,4102444800,NULL,NULL)")
        db.execute("INSERT INTO api_token_audit VALUES (6,4,5,'create',1)")
        db.execute("INSERT INTO _budget_test_restore VALUES (3,10,8)")
        db.execute("INSERT INTO _profile_runtime_restore VALUES (1,12.5)")
        db.execute("INSERT INTO _runtime_test_restore VALUES (3,4.5)")
        db.commit()


class DatabaseTests(unittest.TestCase):
    def test_fresh_bootstrap_and_idempotence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fresh.sqlite3"
            bootstrap_database(str(path))
            bootstrap_database(str(path))
            with sqlite3.connect(path) as db:
                tables = {row[0] for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )}
                self.assertEqual(EXPECTED_TABLES, tables)
                self.assertEqual(SCHEMA_VERSION, db.execute("PRAGMA user_version").fetchone()[0])
                self.assertEqual("ok", db.execute("PRAGMA integrity_check").fetchone()[0])

    def test_v1_upgrade_preserves_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "upgrade.sqlite3"
            schema = (ROOT / "ui" / "schema.sql").read_text()
            v1 = schema.split("CREATE TABLE IF NOT EXISTS auth_users", 1)[0] + "PRAGMA user_version=1;"
            with sqlite3.connect(path) as db:
                db.executescript(v1)
                db.execute("INSERT INTO profiles(slug,name,enabled,topic) VALUES ('test','Test',1,'testing')")
                db.execute("INSERT INTO sources(name) VALUES ('Example')")
                db.commit()
            bootstrap_database(str(path))
            bootstrap_database(str(path))
            with sqlite3.connect(path) as db:
                self.assertEqual(2, db.execute("PRAGMA user_version").fetchone()[0])
                self.assertEqual(("test", "Test"), db.execute("SELECT slug,name FROM profiles").fetchone())
                self.assertEqual("Example", db.execute("SELECT name FROM sources").fetchone()[0])
                self.assertEqual("ok", db.execute("PRAGMA foreign_key_check").fetchone() or "ok")

    def test_generic_orchestrator_discovers_only_enabled_profiles(self):
        worker = ROOT / "worker"
        sys.path.insert(0, str(worker))
        import orchestrator
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.sqlite3"
            bootstrap_database(str(path))
            with sqlite3.connect(path) as db:
                db.execute("INSERT INTO profiles(slug,name,enabled,topic) VALUES ('enabled','Enabled',1,'test')")
                db.execute("INSERT INTO profiles(slug,name,enabled,topic) VALUES ('disabled','Disabled',0,'test')")
                db.commit()
            original = orchestrator.PROFILE_DB
            orchestrator.PROFILE_DB = str(path)
            try:
                self.assertEqual(["enabled"], orchestrator.enabled_profiles())
            finally:
                orchestrator.PROFILE_DB = original

    def test_refuses_newer_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "future.sqlite3"
            with sqlite3.connect(path) as db:
                db.execute("PRAGMA user_version=999")
            with self.assertRaises(RuntimeError):
                bootstrap_database(str(path))

    def test_production_v0_upgrade_preserves_all_existing_data_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "production-v0.sqlite3"
            create_production_v0(path)
            with sqlite3.connect(path) as db:
                before = {
                    table: db.execute(f'SELECT * FROM "{table}"').fetchall()
                    for table in (
                        "profiles", "sources", "profile_sources",
                        "profile_keywords", "profile_entities", "auth_users",
                        "auth_sessions", "auth_profile_assignments", "api_tokens",
                        "api_token_audit", "_budget_test_restore",
                        "_profile_runtime_restore", "_runtime_test_restore",
                    )
                }
            bootstrap_database(str(path))
            bootstrap_database(str(path))
            with sqlite3.connect(path) as db:
                self.assertEqual(2, db.execute("PRAGMA user_version").fetchone()[0])
                self.assertEqual("ok", db.execute("PRAGMA integrity_check").fetchone()[0])
                self.assertIn("auth_login_attempts", {
                    row[0] for row in db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                })
                for table, rows in before.items():
                    self.assertEqual(rows, db.execute(f'SELECT * FROM "{table}"').fetchall())

    def test_rejects_unknown_version_zero_layout_without_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unknown-v0.sqlite3"
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE profiles(id INTEGER, unexpected TEXT)")
                before = db.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
            with self.assertRaises(RuntimeError):
                bootstrap_database(str(path))
            with sqlite3.connect(path) as db:
                self.assertEqual(0, db.execute("PRAGMA user_version").fetchone()[0])
                self.assertEqual(before, db.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall())

    def test_production_v0_migration_rolls_back_on_schema_failure(self):
        import db_bootstrap
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            path = directory / "production-v0.sqlite3"
            bad_schema = directory / "bad-schema.sql"
            create_production_v0(path)
            bad_schema.write_text(
                "CREATE TABLE should_roll_back(id INTEGER);\n"
                "THIS IS NOT SQL;\nPRAGMA user_version=2;\n"
            )
            original = db_bootstrap.SCHEMA_PATH
            db_bootstrap.SCHEMA_PATH = bad_schema
            try:
                with self.assertRaises(sqlite3.Error):
                    bootstrap_database(str(path))
            finally:
                db_bootstrap.SCHEMA_PATH = original
            with sqlite3.connect(path) as db:
                self.assertEqual(0, db.execute("PRAGMA user_version").fetchone()[0])
                self.assertIsNone(db.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='should_roll_back'"
                ).fetchone())
                self.assertEqual("$argon2id$preserved", db.execute(
                    "SELECT password_hash FROM auth_users WHERE id=4"
                ).fetchone()[0])


if __name__ == "__main__":
    unittest.main()
