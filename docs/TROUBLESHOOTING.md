# Troubleshooting

Work from the outside inward and change one thing at a time:

```text
n8n -> worker API -> orchestrator -> SQLite/profile discovery
     -> collector -> pipeline -> LLM endpoint -> renderer -> delivery node
```

Use timestamp-bounded logs. Do not mistake an old traceback for the current execution, and do not start a second run while one is active.

## First five checks

```bash
cd /opt/news4legends
docker compose ps
curl --fail http://127.0.0.1:8081/health
docker compose exec news4legends-worker python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health').read().decode())"
docker top news4legends-worker -eo pid,ppid,etime,stat,cmd
docker compose logs --since=20m --timestamps --tail=200
```

## n8n HTTP node returns 500

**Fastest check:** Open execution output and read `return_code` and `stderr`.

**Expected:** HTTP 200 with delivery fields.

**Likely causes:** invalid profile settings, missing DB/schema, collector/pipeline exception, bad LLM configuration, or invalid orchestrator output.

**Least-destructive fix:** Verify worker health and SQLite first; identify the named profile/error in stderr. Do not add a request body or delete volumes.

**Don't continue until a manual HTTP-node execution returns 200.**

## Workflow appears hung or times out

**Fastest check:** `docker top news4legends-worker -eo pid,ppid,etime,stat,cmd`.

**Expected:** An orchestrator/collector/pipeline process with increasing elapsed time during a real run; completion inside n8n's 3600000 ms timeout for normal workloads.

**Likely causes:** slow/unresponsive sources, large budgets, LLM latency, or overlap. The worker itself allows up to 3600 seconds, longer than the n8n example timeout.

**Fix:** Wait for the current run; do not launch another. Review per-source/profile budgets, unreachable sites, LLM response time, and timeout mismatch. Increase a timeout only after locating the slow stage.

## Enabled profile is missing

**Fastest check:** Confirm profile is enabled in UI and has an enabled `web` source with `PASS` or accepted `WARNING` validation.

```bash
docker compose exec news4legends-ui python - <<'PY'
import sqlite3
d=sqlite3.connect('/data/home-ai-news.db')
print(d.execute('select slug,name,enabled from profiles order by name').fetchall())
PY
```

**Likely causes:** disabled profile/source, failed/unset validation, profile validation error, or no qualifying source weight.

**Fix:** Correct through UI, validate, enable, and rerun. Do not put the slug in `/run`.

## Disabled profile was expected

Disabled profiles are intentionally excluded. Enable it in UI after it has a usable validated source. No n8n edit is required.

## Collector returns zero articles

**Fastest check:** Revalidate source and inspect URL from the server.

**Likely causes:** site markup changed; anti-bot response; listing URL is an article; topic rules too narrow; articles too old/short; source below minimum weight; request/runtime budget exhausted.

**Fix:** Test one source, inspect validation reason, correct URL or topic terms, and adjust one bound at a time. Prefer another lawful accessible source over defeating site controls.

## Source validation warning or failure

`WARNING` means partial extraction or candidate limit; `FAIL` means discovery/sample extraction failed. Check the listing URL, server DNS/TLS access, response content, and failure details. Changing URL/collector clears validation and disables the source; revalidate and re-enable. Validation is not a truth assessment.

## LLM timeout

**Fastest check:** Inspect returned stderr for request timeout and test endpoint reachability from the worker without printing the key.

```bash
docker compose exec news4legends-worker python - <<'PY'
import os, urllib.parse
u=os.environ['OMNIROUTE_API_URL']
print(urllib.parse.urlsplit(u).scheme, urllib.parse.urlsplit(u).netloc)
print(os.environ.get('OMNIROUTE_MODEL'))
PY
```

The client timeout is 120 seconds. Confirm gateway/provider health, URL, model availability, Docker network/DNS, and account quota. Do not expose the API key in diagnostics.

## One LLM/story failure

The pipeline is designed to catch per-story LLM failures and fall back rather than automatically destroy the multi-profile briefing. Inspect output and stderr. If the whole run failed, look for an error outside the per-story boundary or invalid final output.

## All LLM synthesis attempts failed

**Fastest check:** Inspect the worker response or latest run log for `Systemic LLM failure: all ... synthesis attempt(s) failed`.

**Expected:** At least one attempted story synthesis succeeds. Individual failures may still use fallback output.

**If you don't see it:** Verify the endpoint, model, credentials, quota, and provider availability. Do not treat a completely fallback-only run as a healthy LLM integration.

**Don't continue until one controlled synthesis succeeds.**

## One profile fails

Inspect orchestrator stderr for the slug and failing child command. Validate that profile and its sources independently. Current worker API returns 500 when the orchestrator exits non-zero; fix the profile/root cause rather than repeatedly scheduling it.

## Telegram message too long or empty

Inspect `telegram` from the HTTP node. It should be non-empty and normally within the approximately 4,000-character combined budget. If empty, fix upstream collection/profile settings. If rejected as too long, count actual characters and review renderer/version; do not split/retry blindly and duplicate delivery.

## Email missing

Check the n8n execution, SMTP node result, recipient/BCC, spam filtering, SMTP credential and account sending limits. A successful worker run does not prove delivery. Use a controlled recipient for testing.

## Email sends plain text or visible HTML

Set the SMTP email node to HTML and use `{{ $json.email }}` as the HTML body. Test manually, then Publish.

## SMTP authentication or connection failure

Verify the SMTP hostname, port, encryption mode, username and password/App Password against the provider's current instructions. Confirm the From address is permitted. Preserve the n8n volume and credential encryption state; do not delete credentials as a first troubleshooting step. See [SMTP email](SMTP.md).

## Schedule ran but no digest

Open the exact scheduled execution. Confirm HTTP and delivery nodes both ran, at least one profile was processed, delivery node is enabled, schedule timezone is correct, and workflow is active. Check Published state.

## Editor change not reflected or workflow not Published

This is a known operational trap. Publish the intended version, manually execute it, and inspect the next scheduled execution. Saving an editor draft is insufficient.

## Docker logs look stale or show no child progress

Use `--since` and timestamps. Worker subprocess output is captured and may appear only after completion; use `docker top` for live process state. Do not restart a healthy active worker merely because logs are quiet.

Use the UI's **Download latest worker log** link for the newest retained run, or request `GET /logs` from inside the worker container. A 404 means no retained run log exists yet. Logs are kept for seven days by default and pruning occurs when the next run begins.

## UI changes are not reflected

Profile/source changes need no rebuild; refresh and verify SQLite. Code, HTML templates, static assets, schema bootstrap, and Dockerfile changes require `docker compose up -d --build news4legends-ui`. Browser cache can retain static assets. Never rebuild as a substitute for checking which kind of change was made.

## Duplicate runs

Check `docker top` and n8n execution history. Wait for or deliberately terminate only the identified duplicate after understanding impact. Disable temporary schedules/manual triggers. Duplicate runs can double requests, LLM cost, and messages.

## Backup fails

Verify destination exists, has space and restrictive permissions; resolve actual volume names by inspection; restart any service stopped for backup. Confirm every file is non-zero and checksum creation succeeds. Do not accept a partial set.

## Restore fails

Stop and preserve both original backup and failed target. Verify checksums, Git revision, SQLite integrity/version, volume target names, ownership, and that complete n8n state (including encryption material) was restored together. Test on an isolated project; never improvise destructive commands against production.

## Escalation evidence

Collect versions, timestamps, service status, sanitized error text, affected profile/source, and exact step. Redact API keys, tokens, OAuth data, recipients, chat IDs, private URLs, database content, and full workflow exports before sharing.
