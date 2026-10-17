# Upgrading

Treat an upgrade as a recoverable change, not a routine pull-and-restart.

## Before changing anything

1. Confirm UI, worker, database, n8n, and current delivery are healthy.
2. Check that no orchestrator is running with `docker top news4legends-worker -eo pid,ppid,etime,stat,cmd`.
3. Create and verify a complete backup using [Backup and restore](BACKUP-RESTORE.md).
4. Record `git rev-parse HEAD`, `docker compose images`, `docker image inspect n8nio/n8n:latest --format '{{.Id}}'`, and `docker compose version`.
5. Read release notes and schema/migration instructions.

Do not continue if the backup is missing, zero bytes, stale, checksum-invalid, or untested.

## Apply the smallest change

```bash
cd /opt/news4legends
git fetch --all --tags
git status --short
git diff -- compose.yml .env.example ui/schema.sql docker
```

Resolve local modifications rather than overwriting them. Then check out the reviewed revision and validate configuration:

### Supported database migrations

The v2 UI supports two upgrade inputs:

- the documented public schema with `PRAGMA user_version=1`; and
- the explicitly fingerprinted pre-versioned production layout with
  `PRAGMA user_version=0`, the five profile/source tables, and the existing
  authentication, session, assignment, API-token and audit tables.

The production detector compares the ordered column names and declared SQLite
types of every required table. It does **not** treat an arbitrary version-0
database as production. Additional tables, including the three known restore
test tables, are retained but are not used as proof of compatibility. An
unknown or partially matching layout is refused without modification.

Migration uses one SQLite transaction. Existing profiles, sources, per-source
settings, keywords, entities, users, password hashes, sessions, profile
assignments, API tokens, audit rows and unrelated tables are not rewritten or
deleted. The missing v2 login-throttle table and indexes are added, then
`user_version` becomes `2` only on success.

Take and verify the backup first; never rely on application startup as your
only recovery mechanism. The explicit upgrade command creates another
consistent backup with SQLite's backup API before it migrates, so committed WAL
content is included.

For a public v1 database stored at a host path, while services are stopped:

```bash
docker compose stop news4legends-ui news4legends-worker
mkdir -p ./backups
PYTHONPATH=ui python3 scripts/upgrade_v1_to_v2.py /path/to/home-ai-news.db --backup-dir ./backups
```

**What you should see:** `Upgrade complete` with the path of a non-empty pre-v2 backup, followed by schema version 2 and `PRAGMA integrity_check` reporting `ok` when inspected.

**If you don't see it:** Keep the services stopped, retain the error and restore the named pre-v2 copy. Do not rerun against the only database until the cause is understood.

**Don't continue until the backup and upgraded database both pass integrity checks.**

## Existing pre-versioned production installation

This sequence accounts for a baked UI image, bind-mounted worker source, one
shared SQLite volume, and an independently managed n8n service. It deliberately
does not start, replace or migrate n8n.

Run it only after PR review and disposable-database acceptance. Replace the
container name only if your production UI container has a different name.

### 1. Record and stop the application services

```bash
cd /opt/news4legends
export N4L_UI_CONTAINER=news4legends-ui
export N4L_DB_VOLUME="$(docker inspect "$N4L_UI_CONTAINER" --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}')"
test -n "$N4L_DB_VOLUME"
test "$(docker volume inspect "$N4L_DB_VOLUME" --format '{{.Name}}')" = "$N4L_DB_VOLUME"
docker inspect "$N4L_UI_CONTAINER" --format '{{.Image}}' > pre-v2-ui-image.txt
docker inspect news4legends-worker --format '{{.Image}}' > pre-v2-worker-image.txt
docker stop news4legends-ui news4legends-worker
```

**What you should see:** A non-empty named volume, two saved image IDs, and both
application containers stopped. The separately managed n8n container remains
running and untouched.

**If you don't see it:** Stop. Resolve the actual UI container and `/data`
volume mapping. Never guess a volume name.

**Don't continue until the exact shared database volume is confirmed.**

### 2. Run the backup-first migration from the reviewed checkout

```bash
test "$(git rev-parse HEAD)" = "REVIEWED_V2_COMMIT"
mkdir -p ./backups/production-v2
chmod 700 ./backups/production-v2
docker run --rm \
  -v "$N4L_DB_VOLUME:/data" \
  -v "$PWD/ui:/work/ui:ro" \
  -v "$PWD/scripts:/work/scripts:ro" \
  -v "$PWD/backups/production-v2:/backups" \
  -e PYTHONPATH=/work/ui \
  python:3.12-slim \
  python /work/scripts/upgrade_v1_to_v2.py \
    /data/home-ai-news.db --backup-dir /backups
```

**What you should see:** `Upgrade complete. Verified backup:` followed by a
non-empty backup filename.

**If you don't see it:** Keep UI and worker stopped. Do not start v2 and do not
rerun the migration. Preserve the error and backup directory for diagnosis.

**Don't continue until migration reports success.**

### 3. Validate the migrated database before rebuilding

```bash
docker run --rm -v "$N4L_DB_VOLUME:/data:ro" python:3.12-slim python - <<'PY'
import sqlite3
db = sqlite3.connect('file:/data/home-ai-news.db?mode=ro', uri=True)
assert db.execute('PRAGMA user_version').fetchone()[0] == 2
assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
assert db.execute('PRAGMA foreign_key_check').fetchall() == []
for table in ('profiles','sources','profile_sources','auth_users',
              'auth_sessions','auth_profile_assignments','api_tokens',
              'api_token_audit','auth_login_attempts'):
    assert db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone(), table
print('PASS: migrated schema, integrity, foreign keys and preserved tables')
PY
```

Compare sanitized row counts and stable identifiers with the pre-upgrade
record. Do not paste rows, hashes, tokens or usernames into an issue or PR.

### 4. Deploy only UI and worker

Reconcile the reviewed public files with the production-specific Compose file.
Do not add the repository's n8n service to this deployment because production
n8n is separately managed.

```bash
docker compose config --quiet
docker compose build news4legends-ui news4legends-worker
docker compose up -d --no-deps news4legends-worker news4legends-ui
docker compose ps news4legends-worker news4legends-ui
curl --fail http://127.0.0.1:8081/health
```

Then verify administrator login with the existing password, contributor
assignments, API-token authentication, the UI presentation, profile/source
settings, worker health, and one controlled bodyless `POST /run`. Confirm the
existing independent n8n workflow still receives the combined email/Telegram
result.

### Production rollback

If any migration or acceptance check fails, do not retry against the only
database. Keep n8n unchanged, stop UI and worker, preserve the failed database
for diagnosis, and restore the verified `pre-v2-*.sqlite3` backup through
SQLite into the same explicitly resolved volume:

```bash
docker stop news4legends-ui news4legends-worker
export N4L_BACKUP_FILE=/absolute/path/to/verified/pre-v2-TIMESTAMP.sqlite3
test -f "$N4L_BACKUP_FILE"
docker run --rm \
  -v "$N4L_DB_VOLUME:/data" \
  -v "$N4L_BACKUP_FILE:/restore/pre-v2.sqlite3:ro" \
  python:3.12-slim python - <<'PY'
import sqlite3
source = sqlite3.connect('file:/restore/pre-v2.sqlite3?mode=ro', uri=True)
assert source.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
target = sqlite3.connect('/data/home-ai-news.db')
source.backup(target)
target.close(); source.close()
print('PASS: pre-v2 database restored')
PY
```

Recreate UI and worker with the recorded pre-v2 image IDs and the prior
production Compose/source revision. Verify integrity, login, profiles, worker
health and scheduled delivery before declaring rollback complete.

### Additional evidence required before production approval

The supplied manifest is enough to build and test the structural compatibility
path, but production approval still requires these sanitized results:

- disposable migration using a protected copy of the production database;
- before/after table row counts and stable ID ranges, without row contents;
- `integrity_check`, `foreign_key_check` and `user_version` results;
- confirmation that existing administrator login, contributor assignments and
  API tokens work after migration;
- the UI `/data` and worker read-only database mounts refer to the same copied
  test volume;
- UI/worker image IDs and health results from the disposable deployment; and
- one bodyless run through a cloned/test n8n workflow or otherwise isolated
  delivery destinations.

Do not provide the database, hashes, credentials, environment files, private
paths, IP addresses, volume archives or Docker inspection dumps.

```bash
docker compose config --quiet
python3 -m compileall -q ui worker
python3 -m json.tool n8n/workflow.example.json >/dev/null
```

Build/pull only what changed. Because n8n currently uses `latest`, `docker compose pull n8n` can be a major application change. Prefer a tested pinned tag for repeatable deployments.

```bash
docker compose build news4legends-ui news4legends-worker
docker compose pull n8n
docker compose up -d
docker compose ps
```

## Acceptance

Verify, in order:

1. UI health and browser rendering.
2. Worker health.
3. SQLite integrity, schema version 2, and the documented application/authentication tables.
4. Existing profiles/sources/settings.
5. n8n login, workflow, credentials, timezone, activation, and Published version.
6. One controlled bodyless run with no overlap.
7. Delivery through each enabled channel.
8. Reboot persistence if Docker/host configuration changed.

Keep the old images, recorded revision, and backup until acceptance is complete.

## Rollback

If code/images changed but persistent schema/state did not, check out the recorded revision and recreate services from known images. If persistent state changed, stop services and restore the complete matched recovery set; do not mix an old n8n database with unrelated encryption state or an incompatible application schema.

Document why rollback occurred. Do not repeatedly start a failing migration against the only database.

## Manual security advisory or CVE remediation

The public repository includes a best-effort maintenance/CVE classifier, but it does not apply upgrades. Handle every reported advisory as a controlled, backup-first upgrade:

1. Read the vendor's official advisory and identify the affected component, branches, and fixed releases.
2. Discover the version actually installed; do not rely on a version copied into documentation or a script.
3. Compare the installed version and configuration with the advisory. Record the result as **confirmed affected**, **not affected**, or **uncertain**. Treat an unknown branch, vendor backport, or ambiguous version as uncertain rather than safe.
4. Select an applicable fixed release on the supported branch. Do not assume the numerically newest release is compatible.
5. Create the complete backup described in [Backup and restore](BACKUP-RESTORE.md). Confirm it is recent, non-zero, checksum-valid, and recoverable.
6. Record the current Git revision, Compose configuration, container image IDs, and dynamically reported application versions.
7. Read the release notes and migration instructions for every intervening release.
8. Apply the smallest vendor-supported change. Pull or rebuild only the affected component, then recreate only what the upgrade requires.
9. Verify container health, the installed version, SQLite integrity, profiles/sources, n8n state, one bodyless run, and each enabled delivery channel.
10. Reassess the advisory against the newly discovered installed version. Retain the backup and prior image IDs until acceptance is complete.

If any branch applicability, backport status, or fixed-version claim remains uncertain, stop and obtain vendor or qualified security review. A best-effort advisory assessment is not proof that a deployment is secure.
