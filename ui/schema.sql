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

CREATE TABLE IF NOT EXISTS auth_users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'contributor')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    csrf_token TEXT NOT NULL,
    expires_at INTEGER NOT NULL,
    created_at INTEGER NOT NULL DEFAULT (unixepoch()),
    FOREIGN KEY(user_id) REFERENCES auth_users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_expiry ON auth_sessions(expires_at);

CREATE TABLE IF NOT EXISTS auth_login_attempts (
    id INTEGER PRIMARY KEY,
    client_key TEXT NOT NULL,
    attempted_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_auth_login_attempts_client_time
    ON auth_login_attempts(client_key, attempted_at);

CREATE TABLE IF NOT EXISTS auth_profile_assignments (
    user_id INTEGER NOT NULL,
    profile_id INTEGER NOT NULL,
    PRIMARY KEY(user_id, profile_id),
    FOREIGN KEY(user_id) REFERENCES auth_users(id) ON DELETE CASCADE,
    FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS api_tokens (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
    token_hash TEXT NOT NULL UNIQUE,
    scopes TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    last_used_at INTEGER,
    revoked_at INTEGER,
    FOREIGN KEY(user_id) REFERENCES auth_users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_api_tokens_user ON api_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens(token_hash);

CREATE TABLE IF NOT EXISTS api_token_audit (
    id INTEGER PRIMARY KEY,
    actor_user_id INTEGER,
    token_id INTEGER,
    action TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    FOREIGN KEY(actor_user_id) REFERENCES auth_users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_api_token_audit_created
    ON api_token_audit(created_at);

PRAGMA user_version = 2;
