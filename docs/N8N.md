# n8n scheduling and delivery

n8n schedules one generic request and routes the returned delivery bundle. It does not select profiles or run the pipeline once per profile.

## Import the example

Open n8n at `http://NEWS_SERVER_IP:31002`, use **Import from file**, and select `n8n/workflow.example.json`. The workflow is inactive and both delivery nodes are disabled.

## HTTP node contract

Configure the node exactly:

| Field | Value |
| --- | --- |
| Method | `POST` |
| URL | `http://news4legends-worker:8080/run` |
| Authentication | None |
| Query parameters | Off |
| Headers | Off |
| Body | Off |
| Timeout | `3600000` ms (1 hour) |

`/run` is deliberately bodyless. Do not add a profile slug. The worker discovers all enabled profiles from SQLite.

**What you're doing:** Testing n8n-to-worker connectivity.

**Action — n8n UI:** Execute the HTTP Request node.

**What you should see:** JSON with `profiles_processed`, `email`, and `telegram`.

**If you don't see it:** Check worker health, enabled profiles, Compose DNS, and the execution error. A run can take minutes. See [Troubleshooting](TROUBLESHOOTING.md).

**Don't continue until the HTTP node succeeds.**

## Delivery nodes

For SMTP email configure the HTML body as `{{ $json.email }}`. For Telegram use `{{ $json.telegram }}`. Enable either or both only after credentials and destination fields are set. One delivery bundle feeds both nodes; it does not repeat collection or synthesis. See [SMTP email](SMTP.md).

## Schedule, activation, and publication

Set workflow timezone and Schedule Trigger times deliberately. Manually execute the complete workflow, confirm real delivery, then activate it.

**Critical:** after changing production behavior, click **Publish**. The editor can contain a newer draft while the scheduled/published version still behaves like the old configuration.

If a scheduled run behaves unexpectedly:

1. open workflow history and identify the actual execution;
2. check the Published state/version;
3. publish the intended revision;
4. execute once manually;
5. wait for or temporarily set a safe test schedule.

## Persistence

n8n state lives in `n8n_data:/home/node/.n8n`. It contains workflows and encrypted credentials. The encryption state is recovery-critical: back up the complete volume, restrict access, and never replace it casually.

## Safe workflow exports

Exports can contain recipients, BCC fields, chat IDs, URLs, pinned data, credential identifiers, and metadata even if credential bindings are removed. Sanitize and scan every export before committing it.

## Updates and testing

The Compose image currently uses the floating `n8nio/n8n:latest` tag. A routine `docker compose pull` can therefore introduce a new n8n version. Record the current image ID/version, back up first, and use [Upgrading](UPGRADING.md). For stricter reproducibility, choose and test a pinned n8n version before publication/deployment.
