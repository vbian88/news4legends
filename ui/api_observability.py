import json
import os
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from api_v1 import require_scope

router = APIRouter(prefix="/api/v1", tags=["Observability"])
REPORTS = Path(os.environ.get("NEWS4LEGENDS_REPORT_DIR", "/security-reports"))


def snapshot(name):
    p = REPORTS / name
    try:
        if not p.is_file() or p.stat().st_size > 5_000_000:
            raise ValueError("Snapshot missing or oversized")
        data = json.loads(p.read_text())
        if not isinstance(data, dict):
            raise ValueError("Invalid snapshot")
        return data
    except (OSError, ValueError, TypeError):
        raise HTTPException(503, "Monitoring snapshot unavailable")


def age(data):
    value = data.get("generated_at")
    if not isinstance(value, (int, float)):
        return None
    return max(0, int(time.time() - value))


def health_snapshot():
    data = snapshot("system-health.json")
    if data.get("schema_version") != 1:
        raise HTTPException(503, "Unsupported health snapshot")
    return data


@router.get("/monitoring/health")
def health(response: Response, user=Depends(require_scope("monitoring.read"))):
    response.headers["Cache-Control"] = "no-store"
    data = health_snapshot()
    seconds = age(data)
    return {
        "generated_at": data.get("generated_at"),
        "age_seconds": seconds,
        "stale": seconds is None or seconds > 1200,
        "active_incident_count": len(data.get("active_incidents") or {}),
        "metric_count": len(data.get("metrics") or {}),
    }


@router.get("/metrics")
def metrics(response: Response, user=Depends(require_scope("metrics.read"))):
    response.headers["Cache-Control"] = "no-store"
    data = health_snapshot()
    values = data.get("metrics")
    if not isinstance(values, dict):
        raise HTTPException(503, "Metrics unavailable")
    return {
        "generated_at": data.get("generated_at"),
        "age_seconds": age(data),
        "metrics": {
            k: v for k, v in values.items()
            if isinstance(k, str)
            and isinstance(v, (int, float))
            and not isinstance(v, bool)
        },
    }


@router.get("/monitoring/security")
def security(response: Response, user=Depends(require_scope("monitoring.read"))):
    response.headers["Cache-Control"] = "no-store"
    data = snapshot("current.json")
    return {
        "generated_at": data.get("generated_at"),
        "age_seconds": age(data),
        "counts": data.get("counts", {}),
        "finding_count": len(data.get("findings") or []),
        "manual_review_count": len(data.get("manual_review") or []),
    }


@router.get("/backups")
def backups(response: Response, user=Depends(require_scope("backups.read"))):
    response.headers["Cache-Control"] = "no-store"
    data = health_snapshot()
    values = data.get("metrics") or {}
    if not isinstance(values, dict):
        raise HTTPException(503, "Backup metrics unavailable")
    return {
        "generated_at": data.get("generated_at"),
        "age_seconds": age(data),
        "backup_monitoring": {
            k: v for k, v in values.items()
            if isinstance(k, str)
            and k.startswith("backup.")
            and isinstance(v, (int, float))
            and not isinstance(v, bool)
        },
        "archive_integrity_verified": None,
    }


@router.get("/audit/tokens")
def audit_tokens(
    response: Response,
    limit: int = 100,
    user=Depends(require_scope("audit.read")),
):
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator required")
    if not 1 <= limit <= 500:
        raise HTTPException(422, "limit must be between 1 and 500")
    response.headers["Cache-Control"] = "no-store"
    from app import get_db
    db = get_db()
    try:
        rows = db.execute(
            "SELECT id,actor_user_id,token_id,action,created_at "
            "FROM api_token_audit ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return {"items": [dict(r) for r in rows]}
    finally:
        db.close()


@router.get("/collection")
def collection(user=Depends(require_scope("collection.read"))):
    raise HTTPException(
        503,
        "Collection history source not integrated",
    )
