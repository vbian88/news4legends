import hashlib
import hmac
import secrets
import time

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

SESSION_SECONDS = 12 * 60 * 60
COOKIE_NAME = "n4l_session"
password_hasher = PasswordHasher()


def hash_password(password):
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters")
    return password_hasher.hash(password)


def verify_password(stored_hash, password):
    try:
        return password_hasher.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, ValueError):
        return False


def hash_token(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def create_session(db, user_id):
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    expires = int(time.time()) + SESSION_SECONDS
    db.execute(
        "INSERT INTO auth_sessions (token_hash,user_id,csrf_token,expires_at) VALUES (?,?,?,?)",
        (hash_token(token), user_id, csrf, expires),
    )
    return token, csrf


def get_session(db, token):
    if not token:
        return None
    return db.execute(
        """SELECT s.user_id, s.csrf_token, u.username, u.role
           FROM auth_sessions s
           JOIN auth_users u ON u.id = s.user_id
           WHERE s.token_hash = ? AND s.expires_at > ? AND u.active = 1""",
        (hash_token(token), int(time.time())),
    ).fetchone()


def verify_csrf(session, submitted_token):
    return bool(session and submitted_token and
                hmac.compare_digest(session["csrf_token"], submitted_token))

def revoke_session(db, token):
    if token:
        db.execute("DELETE FROM auth_sessions WHERE token_hash=?", (hash_token(token),))
