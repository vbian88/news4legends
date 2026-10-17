import html
import sqlite3

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from auth import hash_password

router = APIRouter()


def db_connection():
    from app import get_db
    return get_db()


def render(content, status_code=200):
    from app import page
    return HTMLResponse(page(content), status_code=status_code)


def esc(value):
    return html.escape(str(value), quote=True)


def message(text, status=400):
    return render(
        f'<h2>User Management</h2><p>{esc(text)}</p>'
        '<p><a href="/users">Back to users</a></p>',
        status,
    )


@router.get("/users")
def users_page(request: Request):
    db = db_connection()
    try:
        users = db.execute(
            "SELECT id, username, role, active FROM auth_users ORDER BY username"
        ).fetchall()
        profiles = db.execute(
            "SELECT id, name FROM profiles ORDER BY name"
        ).fetchall()
        assignments = {
            row["id"]: set()
            for row in users
        }
        for row in db.execute(
            "SELECT user_id, profile_id FROM auth_profile_assignments"
        ):
            assignments.setdefault(row["user_id"], set()).add(row["profile_id"])
    finally:
        db.close()

    rows = []
    for user in users:
        uid = user["id"]
        username = esc(user["username"])
        role = esc(user["role"])
        active = bool(user["active"])

        assigned = ", ".join(
            esc(p["name"]) for p in profiles
            if p["id"] in assignments.get(uid, set())
        ) or "None"

        controls = ""
        if user["role"] == "contributor":
            options = "".join(
                f'<label style="display:block;margin:6px 0">'
                f'<input type="checkbox" name="profile_ids" value="{p["id"]}"'
                f'{" checked" if p["id"] in assignments.get(uid, set()) else ""}>'
                f' {esc(p["name"])}</label>'
                for p in profiles
            )
            controls = f"""
            <form method="post" action="/users/{uid}/assign">
              <strong>Assigned profiles</strong>
              {options}
              <button type="submit">Save assignments</button>
            </form>
            <form method="post" action="/users/{uid}/password">
              <input type="password" name="password"
                     minlength="12" required
                     autocomplete="new-password"
                     placeholder="New password (12+ characters)">
              <button type="submit">Reset password</button>
            </form>
            <form method="post" action="/users/{uid}/active">
              <button type="submit">
                {"Deactivate" if active else "Activate"}
              </button>
            </form>
            """

        rows.append(f"""
        <div class="card">
          <h3>{username}</h3>
          <p>Role: {role} · Status: {"Active" if active else "Inactive"}</p>
          <p>Profiles: {assigned}</p>
          {controls}
        </div>
        """)

    return render(f"""
    <h2>User Management</h2>
    <p><a href="/">← Back to profiles</a></p>
    <div class="card">
      <h3>Create contributor</h3>
      <form method="post" action="/users/create">
        <label>Username
          <input name="username" maxlength="64" required>
        </label>
        <label>Password
          <input type="password" name="password" minlength="12"
                 required autocomplete="new-password">
        </label>
        <button type="submit">Create contributor</button>
      </form>
    </div>
    {''.join(rows)}
    """)


@router.post("/users/create")
def create_contributor(
    username: str = Form(...),
    password: str = Form(...),
):
    username = username.strip()
    if not username or len(username) > 64:
        return message("Username must be 1–64 characters.")
    try:
        hashed = hash_password(password)
    except ValueError as exc:
        return message(str(exc))

    db = db_connection()
    try:
        with db:
            db.execute(
                "INSERT INTO auth_users "
                "(username, password_hash, role, active) "
                "VALUES (?, ?, 'contributor', 1)",
                (username, hashed),
            )
    except sqlite3.IntegrityError:
        return message("Username already exists.", 409)
    finally:
        db.close()
    return RedirectResponse("/users", status_code=303)


@router.post("/users/{user_id}/assign")
async def assign_profiles(
    user_id: int,
    request: Request,
):
    db = db_connection()
    try:
        user = db.execute(
            "SELECT role FROM auth_users WHERE id=?", (user_id,)
        ).fetchone()
        if not user or user["role"] != "contributor":
            return message("Contributor not found.", 404)

        form = await request.form()
        submitted = form.getlist("profile_ids")
        if any(not value.isdecimal() for value in submitted):
            return message("Invalid profile selection.")

        profile_ids = {int(value) for value in submitted}
        if profile_ids:
            placeholders = ",".join("?" for _ in profile_ids)
            count = db.execute(
                f"SELECT COUNT(*) FROM profiles WHERE id IN ({placeholders})",
                tuple(profile_ids),
            ).fetchone()[0]
            if count != len(profile_ids):
                return message("Unknown profile selection.")

        with db:
            db.execute(
                "DELETE FROM auth_profile_assignments WHERE user_id=?",
                (user_id,),
            )
            db.executemany(
                "INSERT INTO auth_profile_assignments "
                "(user_id, profile_id) VALUES (?, ?)",
                [(user_id, pid) for pid in sorted(profile_ids)],
            )
        return RedirectResponse("/users", status_code=303)
    finally:
        db.close()


@router.post("/users/{user_id}/password")
def reset_contributor_password(
    user_id: int,
    password: str = Form(...),
):
    try:
        hashed = hash_password(password)
    except ValueError as exc:
        return message(str(exc))

    db = db_connection()
    try:
        with db:
            cursor = db.execute(
                "UPDATE auth_users SET password_hash=? "
                "WHERE id=? AND role='contributor'",
                (hashed, user_id),
            )
            if cursor.rowcount != 1:
                return message("Contributor not found.", 404)
            db.execute(
                "DELETE FROM auth_sessions WHERE user_id=?", (user_id,)
            )
    finally:
        db.close()
    return RedirectResponse("/users", status_code=303)


@router.post("/users/{user_id}/active")
def toggle_contributor(user_id: int):
    db = db_connection()
    try:
        with db:
            cursor = db.execute(
                "UPDATE auth_users SET active=CASE WHEN active=1 THEN 0 ELSE 1 END "
                "WHERE id=? AND role='contributor'",
                (user_id,),
            )
            if cursor.rowcount != 1:
                return message("Contributor not found.", 404)
            db.execute(
                "DELETE FROM auth_sessions WHERE user_id=?", (user_id,)
            )
    finally:
        db.close()
    return RedirectResponse("/users", status_code=303)
