# Backup and restore

Protect the SQLite control plane, complete n8n state, `.env`, LLM secret, and customized repository configuration. Backups may contain credentials and private data. The procedure below does not automatically encrypt them.

## Recovery set

| Item | Why |
| --- | --- |
| SQLite database | Profiles, sources, keywords, entities, validation/settings |
| Complete `n8n_data` volume | Workflows, users, encryption state, encrypted credentials |
| `.env` | Ports, URLs, timezone, LLM routing |
| `secrets/llm_api_key` | LLM authentication |
| Repository revision/custom files | Exact code, Compose, collector settings, workflow example |

## Create a backup

Choose a protected filesystem outside the repository. This example uses `/var/backups/news4legends`.

### Identify names first

```bash
cd /opt/news4legends
docker compose ps
docker volume ls --format '{{.Name}}' | grep -E 'news4legends_(data|n8n_data)$'
```

Compose may prefix volume names with the project name. Use the names displayed; do not guess.

### Back up SQLite consistently

**What you're doing:** Using SQLite's online backup API from the UI container.

```bash
N4L_BACKUP_DIR="/var/backups/news4legends/$(date +%Y%m%d-%H%M%S)"
sudo install -d -m 700 "$N4L_BACKUP_DIR"
docker compose exec -T news4legends-ui python - <<'PY'
import sqlite3
source=sqlite3.connect('/data/home-ai-news.db')
target=sqlite3.connect('/data/home-ai-news.backup.db')
source.backup(target)
target.close(); source.close()
PY
docker cp news4legends-ui:/data/home-ai-news.backup.db /tmp/home-ai-news.backup.db
docker compose exec -T news4legends-ui rm -f /data/home-ai-news.backup.db
sudo mv /tmp/home-ai-news.backup.db "$N4L_BACKUP_DIR/home-ai-news.db"
```

This uses SQLite's backup API and removes the temporary volume copy after extracting it. Never rely on copying a busy database without a consistency mechanism.

Verify:

```bash
sudo test -s "$N4L_BACKUP_DIR/home-ai-news.db"
sudo python3 - <<PY
import sqlite3
p='$N4L_BACKUP_DIR/home-ai-news.db'
db=sqlite3.connect(p)
print(db.execute('PRAGMA integrity_check').fetchone()[0])
print(db.execute('PRAGMA user_version').fetchone()[0])
PY
```

**What you should see:** `ok` and schema version `1`.

**If you don't see it:** Discard that copy and repeat; do not label it a backup.

**Don't continue until integrity passes.**

### Back up n8n state

Stop n8n briefly to obtain a coherent volume archive:

```bash
docker compose stop n8n
N4L_N8N_VOLUME="$(docker inspect news4legends-n8n --format '{{range .Mounts}}{{if eq .Destination "/home/node/.n8n"}}{{.Name}}{{end}}{{end}}')"
test -n "$N4L_N8N_VOLUME"
docker run --rm -v "$N4L_N8N_VOLUME:/source:ro" -v "$N4L_BACKUP_DIR:/backup" alpine:3.20 tar -czf /backup/n8n-data.tar.gz -C /source .
docker compose start n8n
```

**What you should see:** n8n restarts and `n8n-data.tar.gz` is non-empty.

**If you don't see it:** Keep the failed archive separate, inspect the resolved volume name and Docker error, and restart n8n.

**Don't continue until n8n is running again and the archive is valid.**

### Back up configuration

```bash
sudo install -m 600 .env "$N4L_BACKUP_DIR/env"
sudo install -m 600 secrets/llm_api_key "$N4L_BACKUP_DIR/llm_api_key"
git rev-parse HEAD | sudo tee "$N4L_BACKUP_DIR/git-revision.txt" >/dev/null
sudo tar -czf "$N4L_BACKUP_DIR/custom-config.tar.gz" compose.yml config n8n/workflow.example.json
sudo sha256sum "$N4L_BACKUP_DIR"/* | sudo tee "$N4L_BACKUP_DIR/SHA256SUMS" >/dev/null
sudo find "$N4L_BACKUP_DIR" -maxdepth 1 -type f -printf '%f %s bytes %TY-%Tm-%Td %TH:%TM\n'
```

Verify every expected file exists, has non-zero size, and a recent timestamp. Store a copy on separate protected media. Add encryption as a separate, tested control if required; do not call these archives encrypted unless you actually encrypt them.

## Restore drill

Test in an isolated VM/host or separate Compose project. Never overwrite the only working installation merely to test.

1. Verify checksums: `sha256sum -c SHA256SUMS` from the backup directory.
2. Check out the recorded Git revision.
3. Restore `.env` and LLM key with mode `600`.
4. Create the empty named volumes by running `docker compose create`.
5. Stop all project containers.
6. Resolve the target volume names by inspection.
7. Restore n8n archive into an empty target volume.
8. Start UI once to bootstrap, stop it, then copy the database into the shared data volume as `/data/home-ai-news.db` with appropriate ownership/readability.
9. Start the stack and run health, schema, profile, n8n login/credential, and controlled delivery tests.

Example n8n extraction after resolving `N4L_TARGET_N8N_VOLUME`:

```bash
docker run --rm -v "$N4L_TARGET_N8N_VOLUME:/target" -v "$N4L_BACKUP_DIR:/backup:ro" alpine:3.20 sh -c 'find /target -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + && tar -xzf /backup/n8n-data.tar.gz -C /target'
```

This deletes content only inside the explicitly resolved isolated target volume. Validate the variable is non-empty and the target is not production.

## Restore acceptance

- SQLite integrity is `ok`, version is 1, profiles/sources are present.
- UI and worker health pass.
- n8n workflow opens and encrypted credentials remain usable.
- A bodyless manual run works.
- A test digest reaches the intended safe destination.
- Normal schedule remains disabled until the isolated test is complete.

A file that was never restored successfully is an unproven backup.
