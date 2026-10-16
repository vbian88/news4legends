import hmac
import html
import os
import secrets
import sqlite3

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from auth import (
    COOKIE_NAME, SESSION_SECONDS, create_session,
    get_session, hash_token, revoke_session, verify_password,
)

router = APIRouter()
LOGIN_CSRF_COOKIE = "n4l_login_csrf"
COOKIE_SECURE = os.environ.get("NEWS4LEGENDS_COOKIE_SECURE", "true").lower() in {"1", "true", "yes"}
LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_MAX_FAILURES = 5


def login_html(token, error=""):
    message = (
        f'<p style="color:#ffd75c">{html.escape(error)}</p>'
        if error else ""
    )
    return f"""<!doctype html>
<html lang="en"><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>News 4 Legends — Login</title>
<style>
body {{ background:linear-gradient(135deg,#24080d,#5b101d);
color:#edf0f2;font-family:system-ui;min-height:100vh;
display:grid;place-items:center;margin:0 }}
main {{ background:#18070b;padding:32px;border:1px solid #f0bc2d;
border-radius:12px;width:min(360px,85vw) }}
h1 {{ color:#ffd75c }}
input {{ display:block;width:100%;box-sizing:border-box;
padding:10px;margin:8px 0 18px }}
button {{ background:#f0bc2d;padding:12px;border:0;
cursor:pointer;font-weight:bold }}
</style></head><body><main>
<h1>News 4 Legends</h1><h2>Sign in</h2>
{message}
<form method="post" action="/login">
<input type="hidden" name="csrf_token" value="{html.escape(token)}">
<label>Username<input name="username" required autocomplete="username"></label>
<label>Password<input type="password" name="password"
required autocomplete="current-password"></label>
<button type="submit">Sign in</button>
</form>
<p style="margin-top:18px"><small>Forgotten passwords must be reset by an
administrator using the documented recovery procedure.</small></p>
</main></body></html>"""


def login_response(error="", status_code=200):
    token = secrets.token_urlsafe(32)
    response = HTMLResponse(login_html(token, error), status_code=status_code)
    response.set_cookie(
        LOGIN_CSRF_COOKIE, token, max_age=600,
        secure=COOKIE_SECURE, httponly=True, samesite="lax", path="/login",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/login")
def login_page(request: Request):
    return login_response()


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
):

    # Imported here so this module uses the application's DB configuration.
    from app import get_db

    db = get_db()
    try:
        expected_csrf = request.cookies.get(LOGIN_CSRF_COOKIE, "")
        if not expected_csrf or not hmac.compare_digest(expected_csrf, csrf_token):
            return login_response("Invalid login request.", 403)

        client_key = request.client.host if request.client else "unknown"
        now = int(__import__("time").time())
        db.execute("DELETE FROM auth_login_attempts WHERE attempted_at < ?", (now - LOGIN_WINDOW_SECONDS,))
        failures = db.execute(
            "SELECT COUNT(*) FROM auth_login_attempts WHERE client_key=?",
            (client_key,),
        ).fetchone()[0]
        if failures >= LOGIN_MAX_FAILURES:
            db.commit()
            return login_response("Too many failed attempts. Try again later.", 429)

        user = db.execute(
            """SELECT id, password_hash FROM auth_users
               WHERE username=? AND active=1""",
            (username.strip(),),
        ).fetchone()

        if not user or not verify_password(user["password_hash"], password):
            db.execute(
                "INSERT INTO auth_login_attempts(client_key,attempted_at) VALUES (?,?)",
                (client_key, now),
            )
            db.commit()
            return login_response("Invalid username or password.", 401)

        db.execute("DELETE FROM auth_login_attempts WHERE client_key=?", (client_key,))
        token, _ = create_session(db, user["id"])
        db.commit()
    finally:
        db.close()

    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        COOKIE_NAME, token, max_age=SESSION_SECONDS,
        secure=COOKIE_SECURE, httponly=True, samesite="lax", path="/",
    )
    response.delete_cookie(LOGIN_CSRF_COOKIE, path="/login")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/logout")
def logout(request: Request):
    from app import get_db

    token = request.cookies.get(COOKIE_NAME)
    db = get_db()
    try:
        revoke_session(db, token)
        db.commit()
    finally:
        db.close()

    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE_NAME, path="/")
    response.headers["Cache-Control"] = "no-store"
    return response
