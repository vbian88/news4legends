# Full installation guide

This guide starts with a blank Debian 12 server and finishes with a tested, scheduled News 4 Legends installation and a verified backup. It assumes no Docker knowledge. News 4 Legends lets you choose what deserves attention, then leave collection and briefing to the machine; the goal is to make it safe to consume less news.

## 1. Plan the installation

Use a private server or VM with a comfortable starting size of 2 vCPU, 4 GB RAM, and 30–40 GB disk. A smaller system may work for few sources, but collection and builds can spike CPU, memory, and disk. No GPU is needed when using a remote LLM.

You need:

- Debian 12 with an administrator account that can use `sudo`
- a stable LAN address or DHCP reservation
- SSH access from an administrator laptop
- an OpenAI-compatible chat-completions URL, model name, and API key
- optional Telegram and/or Gmail accounts

Placeholders used below:

| Placeholder | Replace with |
| --- | --- |
| `NEWS_SERVER_IP` | Server LAN IP or resolvable hostname |
| `ADMIN_USER` | Debian administrator username |
| `vbian88` | GitHub repository owner |
| `LLM_URL` | Full chat-completions URL |
| `LLM_MODEL_NAME` | Provider/gateway model identifier |

Do not paste literal placeholders into production configuration.

## 2. Prepare Debian

### Set a hostname

**What you're doing:** Giving the server a recognizable local name.

**Command — News 4 Legends server:**

```bash
sudo hostnamectl set-hostname news4legends
hostnamectl
```

**What you should see:** `Static hostname: news4legends`.

**If you don't see it:** Confirm the command used `sudo`; log out and reconnect if the shell prompt is stale.

**Don't continue until this works.**

### Stabilize the network address

Prefer a DHCP reservation in your router for the server's MAC address. Debian static-network configuration varies by installer and network manager, so do not copy an interface name blindly.

**What you're doing:** Recording the current address before reserving it.

**Command — server:**

```bash
ip -brief address
ip route
```

**What you should see:** A LAN address on the active interface and a `default via` route.

**If you don't see it:** Repair basic networking before continuing. Test `ping -c 3 deb.debian.org`.

**Don't continue until DNS and outbound Internet access work.**

### Verify SSH

**What you're doing:** Ensuring administration survives closing the VM console.

**Command — administrator laptop:**

```bash
ssh ADMIN_USER@NEWS_SERVER_IP
```

**What you should see:** A shell prompt on the server.

**If you don't see it:** On the server console run `sudo systemctl status ssh`; install with `sudo apt install openssh-server` if absent. Check the address and firewall.

**Don't continue until a new SSH session works.**

### Set timezone and update Debian

**Command — server:**

```bash
sudo timedatectl set-timezone Europe/London
timedatectl
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

Replace `Europe/London` if needed.

**What you should see:** The requested timezone, successful package operations, and SSH access after reboot.

**If you don't see it:** Resolve apt errors or boot/network issues at the console.

**Don't continue until the server is current and reachable after reboot.**

## 3. Install Docker Engine and Compose

These commands follow Docker's official Debian apt-repository method. Docker packaging can change; compare with the current official Docker Debian instructions before a future publication.

### Remove conflicting packages

**Command — server:**

```bash
for pkg in docker.io docker-doc docker-compose docker-buildx podman-docker containerd runc; do sudo apt-get remove -y "$pkg"; done
```

It is acceptable for apt to say some packages are not installed.

### Add Docker's signing key and repository

**Command — server:**

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt-get update
```

**What you should see:** `apt-get update` reads `download.docker.com` without key errors.

**If you don't see it:** Check system time, DNS, `/etc/os-release`, the key file, and repository line.

**Don't continue until apt accepts the repository.**

Docker-published ports can bypass some `ufw`/`firewalld` expectations. Keep the services on a trusted network and design firewall policy with Docker's `DOCKER-USER` chain rather than assuming a host firewall automatically protects published container ports.

### Install and verify Docker

**Command — server:**

```bash
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin git
sudo systemctl enable --now docker
sudo systemctl status docker --no-pager
sudo docker run --rm hello-world
sudo docker compose version
```

**What you should see:** Docker is `active (running)`, Hello World succeeds, and Compose prints a v2 version.

**If you don't see it:** Inspect `sudo journalctl -u docker --no-pager -n 100`. Do not install the obsolete standalone `docker-compose` binary as a workaround.

**Don't continue until both verification commands pass.**

Optional non-root access:

```bash
sudo usermod -aG docker "$USER"
```

Log out and in, then run `docker version`. Membership in the `docker` group is effectively root-level access; omit it and retain `sudo` if that is preferable. Remaining commands assume your account can run `docker`.

## 4. Obtain and inspect the repository

**What you're doing:** Checking out the public source into `/opt/news4legends`.

**Command — server, after publication:**

```bash
sudo git clone https://github.com/vbian88/news4legends.git /opt/news4legends
sudo chown -R "$USER":"$USER" /opt/news4legends
cd /opt/news4legends
find . -maxdepth 2 -type f | sort
```

**What you should see:** `compose.yml`, `.env.example`, `config`, `docker`, `ui`, `worker`, `n8n`, and `docs`.

**If you don't see it:** Confirm repository URL/access and that `/opt/news4legends` was not already a non-empty directory.

**Don't continue until the expected tree is present.**

If using the pre-publication archive, securely copy it to the server, extract it, move the extracted `news4legends-public` directory to `/opt/news4legends`, and set ownership. Do not initialize or clone into a production source tree.

## 5. Configure the environment and secret

### Create `.env`

**Command — server:**

```bash
cd /opt/news4legends
cp .env.example .env
nano .env
```

Set at least:

```dotenv
NEWS4LEGENDS_UI_PORT=8081
N8N_PORT=31002
TZ=Europe/London
LLM_API_URL=LLM_URL
LLM_MODEL=LLM_MODEL_NAME
N8N_EDITOR_BASE_URL=http://NEWS_SERVER_IP:31002
WEBHOOK_URL=http://NEWS_SERVER_IP:31002/
```

OmniRoute is a known working gateway but is not mandatory. The endpoint must accept OpenAI-compatible chat-completions requests. Internal code receives these public variables as historical `OMNIROUTE_*` environment names.

**What you should see:** `grep -n 'NEWS_SERVER_IP\|LLM_URL\|LLM_MODEL_NAME' .env` returns nothing.

**If you don't see it:** Reopen `.env` and replace every placeholder. Do not print the API key here; it belongs in the secret file.

**Don't continue until all placeholders are replaced.**

### Create the LLM key file

**Command — server:**

```bash
mkdir -p secrets
read -rsp 'LLM API key: ' N4L_LLM_KEY; printf '\n'
printf '%s' "$N4L_LLM_KEY" > secrets/llm_api_key
unset N4L_LLM_KEY
chmod 600 secrets/llm_api_key
test -s secrets/llm_api_key
stat -c '%a %n' secrets/llm_api_key
```

**What you should see:** `600 secrets/llm_api_key`; `test` prints nothing and exits successfully.

**If you don't see it:** Recreate the file without a trailing newline and correct its permissions.

**Don't continue until it is non-empty, mode 600, and excluded by `git check-ignore secrets/llm_api_key`.**

## 6. Validate and start the stack

**Command — server:**

```bash
cd /opt/news4legends
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
```

**What you should see:** All three services running: `news4legends-ui`, `news4legends-worker`, and `n8n`.

**If you don't see it:** Run `docker compose logs --tail=100 SERVICE_NAME`. Common causes are a missing secret, malformed `.env`, occupied host ports, or failed dependency installation.

**Don't continue until all services remain running.**

### Verify UI and database bootstrap

**Command — server:**

```bash
curl --fail http://127.0.0.1:8081/health
docker compose exec news4legends-ui python - <<'PY'
import sqlite3
db=sqlite3.connect('/data/home-ai-news.db')
print(db.execute('PRAGMA user_version').fetchone()[0])
print([r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")])
PY
```

**What you should see:** A healthy response, schema version `1`, and exactly `profile_entities`, `profile_keywords`, `profile_sources`, `profiles`, `sources`.

**If you don't see it:** Read UI logs. The bootstrap deliberately refuses unexpected schemas instead of modifying them blindly.

**Don't continue until schema version and table list are correct.**

The UI path `/data/home-ai-news.db` and worker path `/config/home-ai-news.db` address the same Docker volume; the worker mount is read-only.

### Verify worker health

**Command — server:**

```bash
docker compose exec news4legends-worker python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health').read().decode())"
```

**What you should see:** JSON containing `"status": "ok"`.

**If you don't see it:** Run `docker compose logs --tail=100 news4legends-worker` and verify the container is running.

**Don't continue until health succeeds.**

## 7. Create the first profile

On a laptop, open `http://NEWS_SERVER_IP:8081`.

1. Create a neutral test profile such as `Local News`.
2. Set a unique slug, topic, keywords, and entities.
3. Keep conservative budgets and a sensible maximum age.
4. Add a source name and its listing page URL (not an individual article URL).
5. Set collector type `web`, user-defined source weight, and limits.
6. Validate the source.
7. Review the result. `WARNING` can be usable but demands review; `FAIL` must not be relied upon.
8. Enable the source, then enable the profile.

Changing a source's listing URL or collector type disables it and clears validation. Revalidate it. See [Profiles and sources](PROFILES-AND-SOURCES.md).

**What you should see:** The profile is enabled and has at least one enabled source with `PASS` or deliberately accepted `WARNING`.

**If you don't see it:** Use the UI guidance; confirm the source is reachable from the server and is a conventional HTML listing page.

**Don't continue until a valid source allows the profile to be enabled.**

## 8. Run the intelligence pipeline once

First check that no run is already active:

```bash
docker top news4legends-worker -eo pid,ppid,etime,stat,cmd
```

Then invoke the bodyless endpoint from the control network:

```bash
docker compose exec news4legends-worker python - <<'PY'
import json, urllib.request
r=urllib.request.Request('http://127.0.0.1:8080/run', method='POST', data=b'')
with urllib.request.urlopen(r, timeout=3700) as x:
    d=json.load(x)
print('profiles_processed:', d.get('profiles_processed'))
print('email characters:', len(d.get('email','')))
print('telegram characters:', len(d.get('telegram','')))
PY
```

**What you should see:** At least one processed profile and non-empty delivery content when matching articles exist.

**If you don't see it:** Do not add a profile body. Follow [Troubleshooting](TROUBLESHOOTING.md) through profile discovery, collection, and LLM access. Worker child output is captured, so use `docker top` to see live process state.

**Don't continue until a controlled run succeeds.**

## 9. Configure n8n

Open `http://NEWS_SERVER_IP:31002` and complete n8n's owner setup. Protect the account credentials.

Import `n8n/workflow.example.json`. Verify the HTTP node exactly:

- Method: `POST`
- URL: `http://news4legends-worker:8080/run`
- Authentication: none
- Query parameters, headers, and body: off
- Timeout: `360000` ms

Both delivery nodes are intentionally disabled. Configure [Telegram](TELEGRAM.md), [Gmail](GMAIL-OAUTH.md), or both. For Gmail use HTML mode and `{{ $json.email }}`; for Telegram use `{{ $json.telegram }}`.

Execute the HTTP node manually.

**What you should see:** `profiles_processed`, `email`, and `telegram` in output JSON.

**If you don't see it:** Verify the worker health from within its container and the service DNS name. A complete run can take minutes.

**Don't continue until the HTTP node succeeds.**

Configure and manually test at least one delivery node. Then set the desired schedule and timezone, activate the workflow, and click **Publish**. An editor change is not guaranteed to affect scheduled execution until published.

## 10. Gmail private-LAN OAuth bootstrap

If using Gmail, follow the complete [Gmail OAuth guide](GMAIL-OAUTH.md). In summary:

1. Enable Gmail API in a Google Cloud project.
2. Configure consent/branding and the minimum scope needed to send.
3. Create a Web application OAuth client.
4. Register `http://localhost:5678/rest/oauth2-credential/callback`.
5. Temporarily set both n8n URLs in `.env` to `http://localhost:5678` (webhook URL ends `/`) and recreate n8n.
6. From the laptop, create an example local tunnel: `ssh -L 5678:127.0.0.1:31002 ADMIN_USER@NEWS_SERVER_IP`.
7. Complete OAuth at `http://localhost:5678`.
8. Close the tunnel, restore normal LAN URLs, recreate n8n, and retest Gmail.

The exact tunnel target depends on port publication. This command is a template, not a recovered historical command.

## 11. Reboot acceptance test

**Command — server:**

```bash
sudo reboot
```

After reconnecting:

```bash
cd /opt/news4legends
docker compose ps
curl --fail http://127.0.0.1:8081/health
docker compose exec news4legends-worker python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health').status)"
```

**What you should see:** All services restarted automatically; both checks pass; profiles and n8n workflow/credentials remain present.

**If you don't see it:** Check Docker service state, container logs, volume mounts, and restart policies.

**Don't continue until persistence survives reboot.**

## 12. Create and verify a backup

Follow [Backup and restore](BACKUP-RESTORE.md). At minimum protect SQLite, the full n8n volume, `.env`, the LLM secret, and customized files. Use SQLite's backup API rather than copying a live database blindly, and stop n8n while archiving its volume.

For every output verify existence, non-zero size, recent timestamp, and checksum. Then perform the documented isolated restore drill. Backup archives contain credentials and are not automatically encrypted.

## 13. Final acceptance checklist

- [ ] Debian is updated and SSH works after reboot.
- [ ] Docker Engine and Compose v2 pass verification.
- [ ] `.env` has no placeholders; secret is non-empty and mode 600.
- [ ] Compose validates and three services stay running.
- [ ] UI and worker health checks pass.
- [ ] SQLite schema version is 1 with exactly five application tables.
- [ ] At least one enabled profile has a validated, enabled source.
- [ ] A bodyless `/run` processes the profile.
- [ ] Chosen delivery channel succeeds manually.
- [ ] Schedule/timezone are correct; workflow is active and Published.
- [ ] State survives a reboot.
- [ ] Backup files are non-empty, recent, checksummed, and access-restricted.
- [ ] An isolated restore test has succeeded.
- [ ] UI, worker, and n8n are not directly exposed to the public Internet.

The system is not accepted merely because containers are green: accept it only after a real briefing arrives through the chosen channel and a restore has been tested.
