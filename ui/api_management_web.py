import html
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from api_tokens import SCOPES, issue, list_tokens, revoke, rotate, purge_token

router = APIRouter()


def esc(value):
    return html.escape(str(value), quote=True)


def render(body, status=200):
    from app import page
    return HTMLResponse(
        page(body),
        status_code=status,
        headers={"Cache-Control": "no-store"},
    )


def db_connection():
    from app import get_db
    return get_db()


def actor(request):
    user = getattr(request.state, "auth_user", None)
    if not user or user.get("role") != "admin":
        raise HTTPException(403, "Administrator required")
    return user["user_id"]


def timestamp(value):
    if value is None:
        return "—"
    return datetime.fromtimestamp(
        int(value), timezone.utc
    ).strftime("%Y-%m-%d %H:%M UTC")


def error(message, status=400):
    return render(
        '<h2>API Management</h2>'
        f'<div class="card"><p>{esc(message)}</p></div>'
        '<p><a href="/api-management">Back to API Management</a></p>',
        status,
    )


def secret_page(name, secret, action):
    # Never persist the raw token in HTML files, URLs, logs or SQLite.
    return render(f"""
      <h2>API Management — {esc(action)}</h2>
      <div class="card">
        <h3>{esc(name)}</h3>
        <p><strong>Copy this token now.</strong>
           It will not be displayed again.</p>
        <textarea readonly rows="4"
          style="width:100%;font-family:monospace"
        >{esc(secret)}</textarea>
        <p>Store it securely. Treat it like a password.</p>
        <a href="/api-management">Return to API Management</a>
      </div>
    """)



@router.get("/api-guide.pdf", include_in_schema=False)
def download_api_guide(request: Request):
    actor(request)
    from api_guide_pdf import api_guide_pdf
    return api_guide_pdf()


@router.get("/api-management")
def management(request: Request):
    user_id = actor(request)
    db = db_connection()
    try:
        tokens = list_tokens(db, user_id)
    finally:
        db.close()

    now = int(time.time())
    rows = []

    for token in tokens:
        token_id = int(token["id"])
        if token["revoked_at"] is not None:
            status = "Revoked"
        elif int(token["expires_at"]) <= now:
            status = "Expired"
        else:
            status = "Active"

        controls = ""
        if status == "Active":
            controls = f"""
              <form method="post"
                    action="/api-management/{token_id}/rotate"
                    style="display:inline-block">
                <button type="submit"
                  onclick="return confirm('Rotate this token? The old secret will stop working immediately.')">
                  Rotate
                </button>
              </form>
              <form method="post"
                    action="/api-management/{token_id}/revoke"
                    style="display:inline-block">
                <button type="submit"
                  onclick="return confirm('Revoke this token permanently?')">
                  Revoke
                </button>
              </form>
            """


        controls += f"""
          <form method="post"
                action="/api-management/{token_id}/delete"
                style="display:inline-block">
            <button type="submit"
              onclick="return confirm('PERMANENTLY DELETE this token record? This cannot be undone.')">
              Delete permanently
            </button>
          </form>
        """

        rows.append(f"""
          <div class="card">
            <h3>{esc(token["name"])}</h3>
            <p><strong>Status:</strong> {status}
               · <strong>Owner:</strong> {esc(token["username"])}
               · <strong>ID:</strong> {token_id}</p>
            <p><strong>Scopes:</strong>
               {esc(", ".join(token["scopes"]))}</p>
            <p><strong>Created:</strong>
               {timestamp(token["created_at"])}
               · <strong>Expires:</strong>
               {timestamp(token["expires_at"])}</p>
            <p><strong>Last used:</strong>
               {timestamp(token["last_used_at"])}</p>
            {controls}
          </div>
        """)

    options = "".join(
        f'<label style="display:block;margin:5px 0">'
        f'<input type="checkbox" name="scopes" value="{esc(scope)}">'
        f' {esc(scope)}</label>'
        for scope in sorted(SCOPES)
    )

    return render(f"""
      <h2>API Management</h2>
      <p><a href="/api-guide.pdf" download>📄 Download REST API Guide (PDF)</a></p>
      <p><a href="/">← Back to profiles</a></p>

      <div class="card">
        <h3>Create named API token</h3>
        <form method="post" action="/api-management/create">
          <label>Token name
            <input name="name" required minlength="1"
                   maxlength="100"
                   placeholder="e.g. Monitoring integration">
          </label>

          <label>Validity
            <select name="days">
              <option value="7">7 days</option>
              <option value="30" selected>30 days</option>
              <option value="90">90 days</option>
            </select>
          </label>

          <h4>Permissions</h4>
          {options}
          <p>Select only the permissions this integration needs.</p>
          <button type="submit">Create token</button>
        </form>
      </div>

      <h3>Existing API tokens ({len(tokens)})</h3>
      {''.join(rows) or '<p>No API tokens yet.</p>'}
    """)


@router.post("/api-management/create")
def create_token(
    request: Request,
    name: str = Form(...),
    days: int = Form(30),
    scopes: list[str] = Form([]),
):
    user_id = actor(request)

    if days not in (7, 30, 90):
        return error("Invalid token validity")

    if not scopes:
        return error("Select at least one permission")

    db = db_connection()
    try:
        result = issue(
            db, user_id, name, scopes,
            lifetime_seconds=days * 86400,
        )
    except (ValueError, PermissionError) as exc:
        return error(str(exc))
    finally:
        db.close()

    return secret_page(name.strip(), result["token"], "Token created")


@router.post("/api-management/{token_id}/revoke")
def revoke_token(request: Request, token_id: int):
    user_id = actor(request)
    db = db_connection()
    try:
        revoke(db, user_id, token_id)
    except (LookupError, PermissionError) as exc:
        return error(str(exc), 404)
    finally:
        db.close()

    return RedirectResponse("/api-management", status_code=303)


@router.post("/api-management/{token_id}/rotate")
def rotate_token(request: Request, token_id: int):
    user_id = actor(request)
    db = db_connection()
    try:
        row = db.execute(
            "SELECT name FROM api_tokens WHERE id=?",
            (token_id,),
        ).fetchone()
        if row is None:
            return error("Token not found", 404)
        name = row["name"]
        result = rotate(db, user_id, token_id)
    except (LookupError, PermissionError) as exc:
        return error(str(exc), 404)
    finally:
        db.close()

    return secret_page(name, result["token"], "Token rotated")


@router.post("/api-management/{token_id}/delete")
def delete_token(request: Request, token_id: int):
    user_id = actor(request)
    db = db_connection()
    try:
        purge_token(db, user_id, token_id)
    except LookupError as exc:
        return error(str(exc), 404)
    finally:
        db.close()
    return RedirectResponse("/api-management", status_code=303)
