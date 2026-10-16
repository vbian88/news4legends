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

    def test_refuses_newer_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "future.sqlite3"
            with sqlite3.connect(path) as db:
                db.execute("PRAGMA user_version=999")
            with self.assertRaises(RuntimeError):
                bootstrap_database(str(path))


if __name__ == "__main__":
    unittest.main()
