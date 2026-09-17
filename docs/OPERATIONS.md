# Operations

This runbook covers routine checks, controlled executions, logs, capacity, and safe changes.

## Daily health

**Command — server:**

```bash
cd /opt/news4legends
docker compose ps
curl --fail http://127.0.0.1:8081/health
docker compose exec news4legends-worker python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health').read().decode())"
docker system df
```

**What you should see:** Three running services, two healthy responses, and adequate disk space.

**If you don't see it:** Inspect the affected service with `docker compose logs --since=30m --tail=200 SERVICE_NAME` and use [Troubleshooting](TROUBLESHOOTING.md).

**Don't launch a run until UI/database and worker health are confirmed.**

## Before a manual run

Check for an existing orchestrator/collector/pipeline process:

```bash
docker top news4legends-worker -eo pid,ppid,etime,stat,cmd
```

Do not start another expensive run while one is active. Overlap duplicates network requests and LLM cost and can confuse delivery.

## Live progress and logs

The worker API captures child stdout/stderr. Child progress may therefore not stream into `docker logs`. Use `docker top` for current processes and elapsed time. Worker API logs remain useful for request arrival and completed errors:

```bash
docker compose logs --since=15m --timestamps news4legends-worker
```

Always use a time boundary. An old traceback remaining in Docker logs is not evidence that the latest execution failed. Correlate timestamps with n8n execution start/end and current processes.

## Controlled manual run

Prefer n8n's manual execution because it tests the real integration. For worker-only diagnosis, call bodyless `/run` inside the worker container as shown in the installation guide. Never add a profile body.

Record before/after:

- enabled profile count
- start/end time
- `profiles_processed`
- email/Telegram output length
- source/LLM warnings in returned `stderr`
- delivery result in n8n

## Profile and source changes

UI data changes are persisted immediately in SQLite and do not require an image rebuild. Changing a source URL or collector type clears validation and disables it; revalidate and re-enable. Python, templates, static assets, schema bootstrap, or Dockerfile changes do require an appropriate image rebuild:

```bash
docker compose up -d --build news4legends-ui
docker compose up -d --build news4legends-worker
```

Rebuilding does not replace named volumes, but back up before code/schema changes.

## n8n changes

After editing:

1. execute the changed nodes manually;
2. execute the complete workflow;
3. confirm actual delivery;
4. verify activation and timezone;
5. click **Publish**;
6. inspect the next scheduled execution.

## Start, stop, and restart

```bash
cd /opt/news4legends
docker compose stop
docker compose start
docker compose restart SERVICE_NAME
```

Use `docker compose down` only deliberately. Without `-v`, named volumes remain; with `-v`, persistent application data is deleted. Do not use `down -v` during routine operations.

## Disk and capacity

Monitor host filesystem and Docker usage:

```bash
df -h
docker system df
docker volume ls
```

Do not prune volumes indiscriminately. Named volumes contain SQLite and n8n state. Use bounded source/profile settings to control run duration and requests. Increase budgets only after measuring.

## Reboot test

After host or Docker changes, reboot during a safe window and confirm services, profiles, n8n workflows/credentials, and a controlled delivery remain intact.

## Security routine

- Keep services on a trusted LAN/VPN.
- Patch Debian and review container/dependency updates using the upgrade runbook.
- Check secret permissions: `stat -c '%a %n' secrets/llm_api_key` should show `600`.
- Back up and test restore regularly.
- Never paste complete logs/executions publicly without redaction.

