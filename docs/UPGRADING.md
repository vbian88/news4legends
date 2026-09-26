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
