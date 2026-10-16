"""Interactive administrator password recovery for the local operator."""

import getpass
import os
import sqlite3

from auth import hash_password


def main() -> int:
    db_path = os.environ.get("NEWS4LEGENDS_DB_PATH", "/data/home-ai-news.db")
    username = os.environ.get("NEWS4LEGENDS_ADMIN_USERNAME") or input("Administrator username: ").strip()
    password = os.environ.get("NEWS4LEGENDS_ADMIN_PASSWORD") or getpass.getpass("New password (12+ characters): ")
    with sqlite3.connect(db_path, timeout=30) as db:
        row = db.execute(
            "SELECT id FROM auth_users WHERE username=? AND role='admin'", (username,)
        ).fetchone()
        if not row:
            raise SystemExit("Administrator not found; no changes made")
        with db:
            db.execute("UPDATE auth_users SET password_hash=?,active=1 WHERE id=?", (hash_password(password), row[0]))
            db.execute("DELETE FROM auth_sessions WHERE user_id=?", (row[0],))
    print("Password reset and existing sessions revoked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
