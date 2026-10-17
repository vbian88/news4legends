import re
import sqlite3
from contextlib import contextmanager
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from access import allowed_profile
from api_v1 import require_scope

router = APIRouter(prefix="/api/v1", tags=["Profile and source CRUD"])

PROFILE_FIELDS = {
    "name", "topic", "enabled", "minimum_source_score",
    "maximum_age_hours", "similarity_threshold", "llm_enabled",
    "llm_limit", "max_total_collection_seconds", "max_total_requests",
    "max_total_articles", "max_llm_calls", "telegram_enabled",
    "email_theme",
}

SOURCE_FIELDS = {
    "enabled", "collector_type", "listing_url", "topic_focused",
    "credibility_score", "source_type", "max_candidates",
    "max_fetches", "request_timeout_seconds",
    "max_source_runtime_seconds", "stop_after_consecutive_stale",
}

BOOL_FIELDS = {
    "enabled", "llm_enabled", "telegram_enabled", "topic_focused",
}

NONNEGATIVE_FIELDS = {
    "minimum_source_score", "maximum_age_hours", "llm_limit",
    "max_total_collection_seconds", "max_total_requests",
    "max_total_articles", "max_llm_calls", "credibility_score",
    "max_candidates", "max_fetches", "request_timeout_seconds",
    "max_source_runtime_seconds", "stop_after_consecutive_stale",
}

class Payload(BaseModel):
    model_config = ConfigDict(extra="allow")

class ProfileCreate(Payload):
    slug: str
    name: str
    topic: str

class SourceCreate(Payload):
    name: str | None = None
    source_id: int | None = None
    listing_url: str
    collector_type: str

class ConfirmDelete(BaseModel):
    confirm: bool = False

@contextmanager
def database(write=False):
    from app import get_db
    db = get_db()
    try:
        if write:
            db.execute("BEGIN IMMEDIATE")
        yield db
        if write:
            db.commit()
    except Exception:
        if write:
            db.rollback()
        raise
    finally:
        db.close()

def admin(user):
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator required")

def check_profile(db, user, slug):
    if not allowed_profile(db, user, slug):
        raise HTTPException(404, "Profile not found")
    row = db.execute(
        "SELECT * FROM profiles WHERE slug=?", (slug,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Profile not found")
    return row

def values(payload, allowed):
    data = payload.model_dump(exclude_unset=True)
    unknown = set(data) - allowed
    if unknown:
        raise HTTPException(
            422, f"Unknown or read-only fields: {sorted(unknown)}"
        )
    if not data:
        raise HTTPException(422, "At least one field is required")
    for key, value in data.items():
        if value is None:
            raise HTTPException(422, f"{key} cannot be null")
        if key in BOOL_FIELDS and not isinstance(value, bool):
            raise HTTPException(422, f"{key} must be boolean")
        if key in NONNEGATIVE_FIELDS:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise HTTPException(422, f"{key} must be numeric")
            if value < 0:
                raise HTTPException(422, f"{key} cannot be negative")
        if isinstance(value, (dict, list)):
            raise HTTPException(422, f"{key} must be scalar")
    if "llm_limit" in data and not 1 <= data["llm_limit"] <= 10:
        raise HTTPException(422, "llm_limit must be between 1 and 10")
    if "maximum_age_hours" in data and data["maximum_age_hours"] < 1:
        raise HTTPException(422, "maximum_age_hours must be at least 1")
    if "credibility_score" in data and not 0 <= data["credibility_score"] <= 100:
        raise HTTPException(422, "credibility_score must be between 0 and 100")
    if "similarity_threshold" in data and not 0 <= data["similarity_threshold"] <= 1:
        raise HTTPException(422, "similarity_threshold must be between 0 and 1")
    if "collector_type" in data and data["collector_type"] not in {"web", "freshrss", "social"}:
        raise HTTPException(422, "Unsupported collector_type")
    if "email_theme" in data and data["email_theme"] not in {
        "auto", "burgundy_gold", "navy_cyan", "emerald", "purple", "orange", "monochrome"
    }:
        raise HTTPException(422, "Unsupported email_theme")
    return data

def update(db, table, data, where, params):
    assignments = ", ".join(f"{key}=?" for key in data)
    db.execute(
        f"UPDATE {table} SET {assignments} WHERE {where}",
        (*data.values(), *params),
    )

def source_row(db, profile_id, source_id):
    row = db.execute(
        """SELECT ps.*,s.name AS source_name
           FROM profile_sources ps
           JOIN sources s ON s.id=ps.source_id
           WHERE ps.profile_id=? AND ps.id=?""",
        (profile_id, source_id),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Profile source not found")
    return row

def conflict(exc):
    raise HTTPException(409, "Record conflicts with existing data") from exc

@router.post("/profiles", status_code=201)
def create_profile(
    payload: ProfileCreate,
    user=Depends(require_scope("profiles.write")),
):
    admin(user)
    slug = payload.slug.strip()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise HTTPException(422, "Invalid profile slug")
    data = values(payload, PROFILE_FIELDS | {"slug"})
    data["slug"] = slug
    data["enabled"] = False
    with database(write=True) as db:
        try:
            columns = ", ".join(data)
            placeholders = ", ".join("?" for _ in data)
            db.execute(
                f"INSERT INTO profiles ({columns}) VALUES ({placeholders})",
                tuple(data.values()),
            )
        except sqlite3.IntegrityError as exc:
            conflict(exc)
        row = db.execute(
            "SELECT * FROM profiles WHERE slug=?", (slug,)
        ).fetchone()
        return dict(row)

@router.patch("/profiles/{slug}")
def patch_profile(
    slug: str,
    payload: Payload,
    user=Depends(require_scope("profiles.write")),
):
    admin(user)
    data = values(payload, PROFILE_FIELDS)
    with database(write=True) as db:
        check_profile(db, user, slug)
        update(db, "profiles", data, "slug=?", (slug,))
        return dict(check_profile(db, user, slug))

@router.delete("/profiles/{slug}")
def delete_profile(
    slug: str,
    confirm: bool = Query(False),
    user=Depends(require_scope("profiles.write")),
):
    admin(user)
    with database(write=confirm) as db:
        profile = check_profile(db, user, slug)
        pid = profile["id"]
        counts = {}
        for table in (
            "profile_sources", "profile_keywords",
            "profile_entities", "auth_profile_assignments",
        ):
            counts[table] = db.execute(
                f"SELECT COUNT(*) FROM {table} WHERE profile_id=?",
                (pid,),
            ).fetchone()[0]
        if not confirm:
            return {
                "dry_run": True,
                "profile": dict(profile),
                "associations_to_remove": counts,
                "global_sources_preserved": True,
            }
        for table in counts:
            db.execute(f"DELETE FROM {table} WHERE profile_id=?", (pid,))
        db.execute("DELETE FROM profiles WHERE id=?", (pid,))
        return {"deleted": True, "slug": slug, "removed": counts}

@router.post("/profiles/{slug}/sources", status_code=201)
def create_source(
    slug: str,
    payload: SourceCreate,
    user=Depends(require_scope("sources.write")),
):
    admin(user)
    data = payload.model_dump(exclude_unset=True)
    name = data.pop("name", None)
    global_id = data.pop("source_id", None)
    config = values(Payload.model_validate(data), SOURCE_FIELDS)
    config["enabled"] = False

    with database(write=True) as db:
        profile = check_profile(db, user, slug)
        if global_id is not None:
            if db.execute(
                "SELECT 1 FROM sources WHERE id=?", (global_id,)
            ).fetchone() is None:
                raise HTTPException(404, "Global source not found")
        else:
            if not name or not name.strip():
                raise HTTPException(422, "Source name required")
            existing = db.execute(
                "SELECT id FROM sources WHERE name=?", (name.strip(),)
            ).fetchone()
            if existing:
                global_id = existing["id"]
            else:
                global_id = db.execute(
                    "INSERT INTO sources(name) VALUES (?)",
                    (name.strip(),),
                ).lastrowid

        if db.execute(
            "SELECT 1 FROM profile_sources WHERE profile_id=? AND source_id=?",
            (profile["id"], global_id),
        ).fetchone():
            raise HTTPException(409, "Source already assigned to profile")

        config["profile_id"] = profile["id"]
        config["source_id"] = global_id
        columns = ", ".join(config)
        placeholders = ", ".join("?" for _ in config)
        try:
            source_id = db.execute(
                f"INSERT INTO profile_sources ({columns}) "
                f"VALUES ({placeholders})",
                tuple(config.values()),
            ).lastrowid
        except sqlite3.IntegrityError as exc:
            conflict(exc)
        return dict(source_row(db, profile["id"], source_id))

@router.get("/profiles/{slug}/sources/{source_id}")
def get_source(
    slug: str,
    source_id: int,
    user=Depends(require_scope("sources.read")),
):
    with database() as db:
        profile = check_profile(db, user, slug)
        return dict(source_row(db, profile["id"], source_id))

@router.patch("/profiles/{slug}/sources/{source_id}")
def patch_source(
    slug: str,
    source_id: int,
    payload: Payload,
    user=Depends(require_scope("sources.write")),
):
    admin(user)
    data = values(payload, SOURCE_FIELDS)
    with database(write=True) as db:
        profile = check_profile(db, user, slug)
        source_row(db, profile["id"], source_id)
        update(
            db, "profile_sources", data,
            "id=? AND profile_id=?", (source_id, profile["id"]),
        )
        return dict(source_row(db, profile["id"], source_id))

@router.delete("/profiles/{slug}/sources/{source_id}")
def delete_source(
    slug: str,
    source_id: int,
    user=Depends(require_scope("sources.write")),
):
    admin(user)
    with database(write=True) as db:
        profile = check_profile(db, user, slug)
        source_row(db, profile["id"], source_id)
        db.execute(
            "DELETE FROM profile_sources WHERE id=? AND profile_id=?",
            (source_id, profile["id"]),
        )
        return {
            "deleted": True,
            "profile_source_id": source_id,
            "global_source_preserved": True,
        }

def terms(db, profile_id, table, field):
    return [
        row[0] for row in db.execute(
            f"SELECT {field} FROM {table} WHERE profile_id=? "
            f"ORDER BY {field}", (profile_id,),
        )
    ]

for _kind, _table, _field in (
    ("keywords", "profile_keywords", "keyword"),
    ("entities", "profile_entities", "entity"),
):
    def register(kind, table, field):
        @router.get(f"/profiles/{{slug}}/{kind}")
        def list_terms(
            slug: str,
            user=Depends(require_scope("profiles.read")),
        ):
            with database() as db:
                profile = check_profile(db, user, slug)
                return {"items": terms(db, profile["id"], table, field)}

        @router.post(f"/profiles/{{slug}}/{kind}", status_code=201)
        def add_term(
            slug: str,
            payload: dict[str, Any],
            user=Depends(require_scope("profiles.write")),
        ):
            admin(user)
            if set(payload) != {field}:
                raise HTTPException(422, f"Expected only '{field}'")
            value = payload[field]
            if not isinstance(value, str) or not value.strip():
                raise HTTPException(422, "Value must be non-empty text")
            value = value.strip()
            with database(write=True) as db:
                profile = check_profile(db, user, slug)
                exists = db.execute(
                    f"SELECT 1 FROM {table} "
                    f"WHERE profile_id=? AND {field}=?",
                    (profile["id"], value),
                ).fetchone()
                if exists:
                    raise HTTPException(409, "Already present")
                db.execute(
                    f"INSERT INTO {table}(profile_id,{field}) VALUES (?,?)",
                    (profile["id"], value),
                )
                return {"added": value, "items": terms(
                    db, profile["id"], table, field,
                )}

        @router.delete(f"/profiles/{{slug}}/{kind}/{{value}}")
        def delete_term(
            slug: str,
            value: str,
            user=Depends(require_scope("profiles.write")),
        ):
            admin(user)
            with database(write=True) as db:
                profile = check_profile(db, user, slug)
                cursor = db.execute(
                    f"DELETE FROM {table} "
                    f"WHERE profile_id=? AND {field}=?",
                    (profile["id"], value),
                )
                if not cursor.rowcount:
                    raise HTTPException(404, "Value not found")
                return {"deleted": value, "items": terms(
                    db, profile["id"], table, field,
                )}
    register(_kind, _table, _field)
