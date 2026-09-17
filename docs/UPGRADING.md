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
3. SQLite integrity, version, and five expected tables.
4. Existing profiles/sources/settings.
5. n8n login, workflow, credentials, timezone, activation, and Published version.
6. One controlled bodyless run with no overlap.
7. Delivery through each enabled channel.
8. Reboot persistence if Docker/host configuration changed.

Keep the old images, recorded revision, and backup until acceptance is complete.

## Rollback

If code/images changed but persistent schema/state did not, check out the recorded revision and recreate services from known images. If persistent state changed, stop services and restore the complete matched recovery set; do not mix an old n8n database with unrelated encryption state or an incompatible application schema.

Document why rollback occurred. Do not repeatedly start a failing migration against the only database.

