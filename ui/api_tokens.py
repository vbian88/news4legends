import hashlib
import hmac
import json
import secrets
import sqlite3
import time

SCOPES = frozenset({
    "profiles.read",
    "profiles.write",
    "sources.read",
    "sources.write",
    "collection.read",
    "collection.run",
    "metrics.read",
    "monitoring.read",
    "backups.read",
    "audit.read",
    "tokens.read",
    "tokens.create",
    "tokens.rotate",
    "tokens.revoke",
    "admin.read",
    "admin.write",
})

MAX_LIFETIME = 90 * 86400


def initialize(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS api_tokens (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES auth_users(id),
        name TEXT NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        scopes TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL,
        last_used_at INTEGER,
        revoked_at INTEGER
    );

    CREATE INDEX IF NOT EXISTS idx_api_tokens_user
        ON api_tokens(user_id);

    CREATE TABLE IF NOT EXISTS api_token_audit (
        id INTEGER PRIMARY KEY,
        actor_user_id INTEGER NOT NULL,
        token_id INTEGER,
        action TEXT NOT NULL,
        created_at INTEGER NOT NULL
    );
    """)


def digest(secret):
    return hashlib.sha256(secret.encode("ascii")).hexdigest()


def audit(db, actor_user_id, token_id, action):
    db.execute(
        "INSERT INTO api_token_audit "
        "(actor_user_id,token_id,action,created_at) "
        "VALUES (?,?,?,?)",
        (actor_user_id, token_id, action, int(time.time())),
    )


def require_admin(db, user_id):
    row = db.execute(
        "SELECT id FROM auth_users "
        "WHERE id=? AND role='admin' AND active=1",
        (user_id,),
    ).fetchone()
    if row is None:
        raise PermissionError("Active administrator required")


def check_scopes(scopes):
    if not isinstance(scopes, (list, tuple, set)):
        raise ValueError("Scopes must be a list")
    if not scopes or any(not isinstance(s, str) for s in scopes):
        raise ValueError("At least one valid scope is required")
    scopes = set(scopes)
    if not scopes <= SCOPES:
        raise ValueError("Unknown permission scope")
    return sorted(scopes)


def issue(db, actor_user_id, name, scopes, lifetime_seconds=2592000):
    require_admin(db, actor_user_id)
    name = name.strip() if isinstance(name, str) else ""
    if not 1 <= len(name) <= 100:
        raise ValueError("Token name must contain 1–100 characters")
    scopes = check_scopes(scopes)
    if type(lifetime_seconds) is not int or not 1 <= lifetime_seconds <= MAX_LIFETIME:
        raise ValueError("Invalid token lifetime")

    now = int(time.time())
    secret = "n4l_" + secrets.token_urlsafe(48)
    with db:
        cursor = db.execute(
            "INSERT INTO api_tokens "
            "(user_id,name,token_hash,scopes,created_at,expires_at) "
            "VALUES (?,?,?,?,?,?)",
            (
                actor_user_id,
                name,
                digest(secret),
                json.dumps(scopes),
                now,
                now + lifetime_seconds,
            ),
        )
        token_id = cursor.lastrowid
        audit(db, actor_user_id, token_id, "create")
    return {"id": token_id, "token": secret, "expires_at": now + lifetime_seconds}


def authenticate(db, secret, required_scope=None):
    if not isinstance(secret, str) or not secret.startswith("n4l_"):
        return None
    if len(secret) > 256:
        return None

    now = int(time.time())
    row = db.execute(
        """SELECT t.id,t.user_id,t.scopes,u.username,u.role
           FROM api_tokens t
           JOIN auth_users u ON u.id=t.user_id
           WHERE t.token_hash=?
             AND t.revoked_at IS NULL
             AND t.expires_at>?
             AND u.active=1""",
        (digest(secret), now),
    ).fetchone()
    if row is None:
        return None

    scopes = set(json.loads(row["scopes"]))
    if required_scope and required_scope not in scopes:
        return None

    db.execute("UPDATE api_tokens SET last_used_at=? WHERE id=?", (now, row["id"]))
    db.commit()

    return {
        "token_id": row["id"],
        "user_id": row["user_id"],
        "username": row["username"],
        "role": row["role"],
        "scopes": sorted(scopes),
    }


def list_tokens(db, actor_user_id):
    require_admin(db, actor_user_id)
    rows = db.execute(
        """SELECT t.id,t.user_id,u.username,t.name,t.scopes,
                  t.created_at,t.expires_at,t.last_used_at,t.revoked_at
           FROM api_tokens t
           JOIN auth_users u ON u.id=t.user_id
           ORDER BY t.id DESC"""
    ).fetchall()
    return [
        {**dict(row), "scopes": json.loads(row["scopes"])}
        for row in rows
    ]


def revoke(db, actor_user_id, token_id):
    require_admin(db, actor_user_id)
    with db:
        cursor = db.execute(
            "UPDATE api_tokens SET revoked_at=? "
            "WHERE id=? AND revoked_at IS NULL",
            (int(time.time()), token_id),
        )
        if cursor.rowcount != 1:
            raise LookupError("Active token not found")
        audit(db, actor_user_id, token_id, "revoke")


def rotate(db, actor_user_id, token_id):
    require_admin(db, actor_user_id)
    now = int(time.time())
    secret = "n4l_" + secrets.token_urlsafe(48)
    with db:
        cursor = db.execute(
            """UPDATE api_tokens
               SET token_hash=?,created_at=?,last_used_at=NULL
               WHERE id=? AND revoked_at IS NULL AND expires_at>?""",
            (digest(secret), now, token_id, now),
        )
        if cursor.rowcount != 1:
            raise LookupError("Active unexpired token not found")
        audit(db, actor_user_id, token_id, "rotate")
    return {"id": token_id, "token": secret}


def purge_token(db, actor_user_id, token_id):
    """Permanently delete one token, retaining an audit tombstone."""
    require_admin(db, actor_user_id)
    with db:
        row = db.execute(
            "SELECT id FROM api_tokens WHERE id=?", (token_id,)
        ).fetchone()
        if row is None:
            raise LookupError("Token not found")
        audit(db, actor_user_id, token_id, "delete")
        result = db.execute(
            "DELETE FROM api_tokens WHERE id=?", (token_id,)
        )
        if result.rowcount != 1:
            raise RuntimeError("Token deletion failed")
    return {"deleted": True, "token_id": token_id}
