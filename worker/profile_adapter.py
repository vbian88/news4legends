import sqlite3


DEFAULT_CORROBORATION = {
    "two_sources_bonus": 5,
    "three_sources_bonus": 3,
    "four_sources_bonus": 2,
}

DEFAULT_MAX_TEXT_CHARS_PER_ARTICLE = 5000
DEFAULT_MAX_ARTICLES_PER_STORY = 3


def load_profile_from_db(
    slug,
    db_path="/config/home-ai-news.db",
):
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    try:
        profile_row = db.execute(
            """
            SELECT *
            FROM profiles
            WHERE slug = ?
            """,
            (slug,),
        ).fetchone()

        if profile_row is None:
            raise ValueError(
                f"profile not found: {slug}"
            )

        source_rows = db.execute(
            """
            SELECT
                s.name,
                ps.enabled,
                ps.credibility_score,
                ps.source_type
            FROM profile_sources ps
            JOIN sources s
              ON s.id = ps.source_id
            WHERE ps.profile_id = ?
            ORDER BY s.name
            """,
            (profile_row["id"],),
        ).fetchall()

    finally:
        db.close()

    sources = {}

    for row in source_rows:
        if not row["enabled"]:
            continue

        if row["credibility_score"] is None:
            continue

        sources[row["name"]] = {
            "score": row["credibility_score"],
            "type": row["source_type"],
        }

    profile = {
        "identity": {
            "slug": profile_row["slug"],
            "name": profile_row["name"],
        },
        "topic": profile_row["topic"],
        "enabled": bool(
            profile_row["enabled"]
        ),
        "minimum_source_score": (
            profile_row["minimum_source_score"]
        ),
        "maximum_age_hours": (
            profile_row["maximum_age_hours"]
        ),
        "clustering": {
            "title_similarity_threshold": (
                profile_row[
                    "similarity_threshold"
                ]
            ),
        },
        "corroboration": dict(
            DEFAULT_CORROBORATION
        ),
        "llm": {
            "enabled": bool(
                profile_row["llm_enabled"]
            ),
            "limit": profile_row["llm_limit"],
            "max_text_chars_per_article": (
                DEFAULT_MAX_TEXT_CHARS_PER_ARTICLE
            ),
        },
        "delivery": {
            "telegram_enabled": bool(
                profile_row["telegram_enabled"]
            ),
            "email_theme": (
                profile_row["email_theme"]
                if "email_theme" in profile_row.keys()
                else "auto"
            ),
            "max_articles_per_story": (
                DEFAULT_MAX_ARTICLES_PER_STORY
            ),
        },
        "budgets": {
            "max_total_collection_seconds": (
                profile_row[
                    "max_total_collection_seconds"
                ]
            ),
            "max_total_requests": (
                profile_row[
                    "max_total_requests"
                ]
            ),
            "max_total_articles": (
                profile_row[
                    "max_total_articles"
                ]
            ),
            "max_llm_calls": (
                profile_row[
                    "max_llm_calls"
                ]
            ),
        },
        "sources": sources,
    }

    validate_profile(profile)

    return profile


def validate_profile(profile):
    required = (
        "identity",
        "topic",
        "minimum_source_score",
        "maximum_age_hours",
        "clustering",
        "corroboration",
        "llm",
        "delivery",
        "sources",
    )

    missing = [
        key
        for key in required
        if key not in profile
    ]

    if missing:
        raise ValueError(
            "profile missing required fields: "
            + ", ".join(missing)
        )

    if not profile["identity"]["slug"]:
        raise ValueError(
            "profile slug is required"
        )

    if not profile["topic"]:
        raise ValueError(
            "profile topic is required"
        )

    if (
        profile["minimum_source_score"]
        is None
    ):
        raise ValueError(
            "minimum source weight is required"
        )

    if profile["maximum_age_hours"] is None:
        raise ValueError(
            "maximum age is required"
        )

    threshold = profile[
        "clustering"
    ]["title_similarity_threshold"]

    if threshold is None or not (
        0.0 <= threshold <= 1.0
    ):
        raise ValueError(
            "title similarity threshold "
            "must be between 0 and 1"
        )

    return True
