"""Create or reset the first administrator without default credentials."""

import getpass
import os
import sqlite3

from auth import hash_password
from db_bootstrap import bootstrap_database


def main() -> int:
    db_path = os.environ.get("NEWS4LEGENDS_DB_PATH", "/data/home-ai-news.db")
    username = os.environ.get("NEWS4LEGENDS_ADMIN_USERNAME") or input("Administrator username: ").strip()
    password = os.environ.get("NEWS4LEGENDS_ADMIN_PASSWORD") or getpass.getpass("Administrator password (12+ characters): ")
    if not username or len(username) > 64:
        raise SystemExit("Username must contain 1-64 characters")

    bootstrap_database(db_path)
    password_hash = hash_password(password)
    with sqlite3.connect(db_path, timeout=30) as db:
        db.execute("PRAGMA foreign_keys=ON")
        existing = db.execute("SELECT id FROM auth_users WHERE role='admin'").fetchone()
        if existing:
            raise SystemExit("An administrator already exists; use the documented reset procedure")
        db.execute(
            "INSERT INTO auth_users(username,password_hash,role,active) VALUES (?,?, 'admin', 1)",
            (username, password_hash),
        )
        db.commit()
    print("Administrator created. The password was not written to disk.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
