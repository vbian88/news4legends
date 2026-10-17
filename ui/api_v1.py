import sqlite3
from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api_tokens import authenticate, list_tokens
from access import allowed_profile

router = APIRouter(prefix="/api/v1", tags=["News 4 Legends API"])
bearer = HTTPBearer(auto_error=False)


@contextmanager
def database():
    from app import get_db
    db = get_db()
    try:
        yield db
    finally:
        db.close()


def principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
):
    # API must be reached through the approved HTTPS entry point.
    # Do not trust client-supplied forwarded-protocol headers.

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            401, "Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    with database() as db:
        user = authenticate(db, credentials.credentials)

    if user is None:
        raise HTTPException(
            401, "Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_scope(scope):
    def dependency(user=Depends(principal)):
        if scope not in user["scopes"]:
            raise HTTPException(403, "Insufficient token scope")
        return user
    return dependency


@router.get("/me")
def me(user=Depends(principal)):
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "role": user["role"],
        "scopes": sorted(user["scopes"]),
    }


@router.get("/profiles")
def profiles(user=Depends(require_scope("profiles.read"))):
    with database() as db:
        if user["role"] == "admin":
            rows = db.execute(
                "SELECT id,slug,name,enabled,topic "
                "FROM profiles ORDER BY name"
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT p.id,p.slug,p.name,p.enabled,p.topic
                   FROM profiles p
                   JOIN auth_profile_assignments a
                     ON a.profile_id=p.id
                   WHERE a.user_id=?
                   ORDER BY p.name""",
                (user["user_id"],),
            ).fetchall()
        return {"items": [dict(row) for row in rows]}


@router.get("/profiles/{slug}")
def profile(slug: str, user=Depends(require_scope("profiles.read"))):
    with database() as db:
        if not allowed_profile(db, user, slug):
            raise HTTPException(404, "Profile not found")
        row = db.execute(
            "SELECT * FROM profiles WHERE slug=?", (slug,)
        ).fetchone()
        return dict(row)


@router.get("/profiles/{slug}/sources")
def profile_sources(
    slug: str,
    user=Depends(require_scope("sources.read")),
):
    with database() as db:
        if not allowed_profile(db, user, slug):
            raise HTTPException(404, "Profile not found")
        rows = db.execute(
            """SELECT ps.*,s.name AS source_name
               FROM profile_sources ps
               JOIN sources s ON s.id=ps.source_id
               JOIN profiles p ON p.id=ps.profile_id
               WHERE p.slug=?
               ORDER BY s.name""",
            (slug,),
        ).fetchall()
        return {"items": [dict(row) for row in rows]}


@router.get("/auth/tokens")
def token_metadata(user=Depends(require_scope("tokens.read"))):
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator required")
    with database() as db:
        return {"items": list_tokens(db, user["user_id"])}
