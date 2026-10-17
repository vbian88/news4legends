import importlib
import os
import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ui"))


class ApplicationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        os.environ["NEWS4LEGENDS_DB_PATH"] = str(Path(cls.temp.name) / "app.sqlite3")
        os.environ["NEWS4LEGENDS_STATIC_DIR"] = str(Path(cls.temp.name) / "static")
        os.environ["NEWS4LEGENDS_COOKIE_SECURE"] = "false"
        cls.app_module = importlib.import_module("app")
        from auth import hash_password
        with cls.app_module.get_db() as db:
            db.execute(
                "INSERT INTO auth_users(username,password_hash,role,active) VALUES (?,?, 'admin',1)",
                ("admin", hash_password("integration-test-password")),
            )
            db.commit()
        cls.client = TestClient(cls.app_module.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.temp.cleanup()

    def test_health_and_authentication_boundary(self):
        self.assertEqual(200, self.client.get("/health").status_code)
        self.assertEqual(303, self.client.get("/", follow_redirects=False).status_code)

    def test_login_csrf_and_openapi_contract(self):
        page = self.client.get("/login")
        token = self.client.cookies.get("n4l_login_csrf")
        self.assertTrue(token)
        bad = self.client.post("/login", data={
            "username": "admin", "password": "integration-test-password", "csrf_token": "bad"
        }, follow_redirects=False)
        self.assertEqual(403, bad.status_code)

        page = self.client.get("/login")
        token = self.client.cookies.get("n4l_login_csrf")
        good = self.client.post("/login", data={
            "username": "admin", "password": "integration-test-password", "csrf_token": token
        }, follow_redirects=False)
        self.assertEqual(303, good.status_code)
        self.assertEqual(200, self.client.get("/").status_code)
        self.assertEqual(403, self.client.post("/logout", data={"csrf_token": "bad"}).status_code)
        home = self.client.get("/")
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', home.text).group(1)
        self.assertEqual(303, self.client.post(
            "/logout", data={"csrf_token": csrf}, follow_redirects=False
        ).status_code)

        page = self.client.get("/login")
        token = self.client.cookies.get("n4l_login_csrf")
        self.client.post("/login", data={
            "username": "admin", "password": "integration-test-password", "csrf_token": token
        }, follow_redirects=False)
        guide = self.client.get("/api-guide.pdf")
        self.assertEqual(200, guide.status_code)
        self.assertEqual("application/pdf", guide.headers["content-type"])
        self.assertTrue(guide.content.startswith(b"%PDF"))

        contract = self.app_module.app.openapi()
        operations = sum(
            method in {"get", "post", "put", "patch", "delete"}
            for methods in contract["paths"].values() for method in methods
        )
        self.assertEqual(53, len(contract["paths"]))
        self.assertEqual(69, operations)


if __name__ == "__main__":
    unittest.main()
