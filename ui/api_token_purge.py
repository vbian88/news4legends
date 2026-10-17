from fastapi import APIRouter, Depends, HTTPException

from api_v1 import require_scope
from api_tokens import purge_token

router = APIRouter(prefix="/api/v1")


@router.delete("/auth/tokens/{token_id}")
def delete_api_token(
    token_id: int,
    user=Depends(require_scope("tokens.revoke")),
):
    from app import get_db

    db = get_db()
    try:
        return purge_token(db, user["user_id"], token_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Token not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Administrator required")
    finally:
        db.close()


from fastapi import Response
from pydantic import BaseModel, ConfigDict, Field
from api_tokens import issue, rotate, revoke


class TokenCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    scopes: list[str]
    days: int = Field(default=30, ge=1, le=90)


class TokenCreateResponse(BaseModel):
    id: int
    token: str
    expires_at: int


class TokenRotateResponse(BaseModel):
    id: int
    token: str


class TokenRevokeResponse(BaseModel):
    revoked: bool
    token_id: int


@router.post(
    "/auth/tokens",
    status_code=201,
    response_model=TokenCreateResponse,
)
def create_api_token(
    payload: TokenCreateRequest,
    response: Response,
    user=Depends(require_scope("tokens.create")),
):
    from app import get_db

    response.headers["Cache-Control"] = "no-store"
    db = get_db()
    try:
        try:
            return issue(
                db,
                user["user_id"],
                payload.name,
                payload.scopes,
                lifetime_seconds=payload.days * 86400,
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(403, "Administrator required") from exc
    finally:
        db.close()


@router.post(
    "/auth/tokens/{token_id}/rotate",
    response_model=TokenRotateResponse,
)
def rotate_api_token(
    token_id: int,
    response: Response,
    user=Depends(require_scope("tokens.rotate")),
):
    from app import get_db

    response.headers["Cache-Control"] = "no-store"
    db = get_db()
    try:
        try:
            return rotate(db, user["user_id"], token_id)
        except LookupError as exc:
            raise HTTPException(404, "Active unexpired token not found") from exc
        except PermissionError as exc:
            raise HTTPException(403, "Administrator required") from exc
    finally:
        db.close()


@router.post(
    "/auth/tokens/{token_id}/revoke",
    response_model=TokenRevokeResponse,
)
def revoke_api_token(
    token_id: int,
    user=Depends(require_scope("tokens.revoke")),
):
    from app import get_db

    db = get_db()
    try:
        try:
            revoke(db, user["user_id"], token_id)
            return {"revoked": True, "token_id": token_id}
        except LookupError as exc:
            raise HTTPException(404, "Active token not found") from exc
        except PermissionError as exc:
            raise HTTPException(403, "Administrator required") from exc
    finally:
        db.close()
