def visible_profiles(db, user):
    if user["role"] == "admin":
        return db.execute("SELECT * FROM profiles ORDER BY name").fetchall()
    return db.execute(
        """SELECT p.* FROM profiles p
           JOIN auth_profile_assignments a ON a.profile_id = p.id
           WHERE a.user_id = ? ORDER BY p.name""",
        (user["user_id"],),
    ).fetchall()


def allowed_profile(db, user, slug):
    if user["role"] == "admin":
        return db.execute(
            "SELECT id FROM profiles WHERE slug = ?", (slug,)
        ).fetchone() is not None
    return db.execute(
        """SELECT 1 FROM profiles p
           JOIN auth_profile_assignments a ON a.profile_id = p.id
           WHERE p.slug = ? AND a.user_id = ?""",
        (slug, user["user_id"]),
    ).fetchone() is not None


def can_delete(user):
    return user["role"] == "admin"
