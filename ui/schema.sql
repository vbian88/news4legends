-- News 4 Legends
-- Canonical SQLite schema for a fresh installation.
-- Production/test residue must never be added here.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    topic TEXT,
    minimum_source_score INTEGER,
    maximum_age_hours INTEGER,
    similarity_threshold REAL,
    llm_enabled INTEGER NOT NULL DEFAULT 1,
    llm_limit INTEGER,
    max_total_collection_seconds INTEGER,
    max_total_requests INTEGER,
    max_total_articles INTEGER,
    max_llm_calls INTEGER,
    telegram_enabled INTEGER NOT NULL DEFAULT 0,
    email_theme TEXT NOT NULL DEFAULT 'auto'
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS profile_sources (
    id INTEGER PRIMARY KEY,
    profile_id INTEGER NOT NULL,
    source_id INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    collector_type TEXT NOT NULL,
    listing_url TEXT,
    topic_focused INTEGER NOT NULL DEFAULT 0,
    credibility_score INTEGER,
    source_type TEXT,
    max_candidates INTEGER,
    max_fetches INTEGER,
    request_timeout_seconds REAL,
    max_source_runtime_seconds REAL,
    stop_after_consecutive_stale INTEGER,
    validation_status TEXT,
    validation_reason TEXT,
    validated_at TEXT,
    UNIQUE(profile_id, source_id),
    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
    FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS profile_keywords (
    profile_id INTEGER NOT NULL,
    keyword TEXT NOT NULL,
    UNIQUE(profile_id, keyword),
    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS profile_entities (
    profile_id INTEGER NOT NULL,
    entity TEXT NOT NULL,
    UNIQUE(profile_id, entity),
    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

PRAGMA user_version = 1;
