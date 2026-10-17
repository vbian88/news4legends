import sqlite3
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ui"))

from auth import create_session, get_session, hash_password, verify_password
from api_tokens import authenticate, issue, revoke
from db_bootstrap import bootstrap_database
from access import allowed_profile, visible_profiles


class AuthTokenTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "test.sqlite3"
        bootstrap_database(str(self.path))
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute(
            "INSERT INTO auth_users(username,password_hash,role,active) VALUES (?,?, 'admin',1)",
            ("admin", hash_password("a-secure-test-password")),
        )
        self.user_id = self.db.execute("SELECT id FROM auth_users").fetchone()[0]
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_password_session_and_scope(self):
        stored = self.db.execute("SELECT password_hash FROM auth_users").fetchone()[0]
        self.assertTrue(verify_password(stored, "a-secure-test-password"))
        token, _ = create_session(self.db, self.user_id)
        self.db.commit()
        self.assertEqual("admin", get_session(self.db, token)["role"])
        created = issue(self.db, self.user_id, "test", ["profiles.read"], 60)
        self.assertIsNotNone(authenticate(self.db, created["token"], "profiles.read"))
        self.assertIsNone(authenticate(self.db, created["token"], "profiles.write"))
        revoke(self.db, self.user_id, created["id"])
        self.assertIsNone(authenticate(self.db, created["token"]))

    def test_contributor_profile_boundary(self):
        self.db.execute("INSERT INTO profiles(slug,name,topic) VALUES ('one','One','one'),('two','Two','two')")
        self.db.execute(
            "INSERT INTO auth_users(username,password_hash,role,active) VALUES (?,?, 'contributor',1)",
            ("contributor", hash_password("another-secure-password")),
        )
        contributor = self.db.execute("SELECT id FROM auth_users WHERE username='contributor'").fetchone()[0]
        profile = self.db.execute("SELECT id FROM profiles WHERE slug='one'").fetchone()[0]
        self.db.execute("INSERT INTO auth_profile_assignments(user_id,profile_id) VALUES (?,?)", (contributor, profile))
        self.db.commit()
        principal = {"user_id": contributor, "role": "contributor"}
        self.assertTrue(allowed_profile(self.db, principal, "one"))
        self.assertFalse(allowed_profile(self.db, principal, "two"))
        self.assertEqual(["one"], [row["slug"] for row in visible_profiles(self.db, principal)])


if __name__ == "__main__":
    unittest.main()
