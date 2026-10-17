# Maintenance and security monitoring

News 4 Legends includes a deterministic, zero-LLM maintenance subsystem. It discovers installed container versions at run time, obtains public project advisories, classifies applicable version ranges, and writes structured current/history reports. It never installs updates or changes containers.

The results are best-effort information. `UNCERTAIN` means the published ranges, maintained branches, or version metadata do not support a safe automatic conclusion. Review the official advisory before acting.

## Configure

The public `maintenance/config.example.json` enables the n8n container shipped by this Compose project. To customize monitored services without changing tracked code:

```bash
cp maintenance/config.example.json maintenance/config.json
mkdir -p maintenance/reports maintenance/state
chmod 700 maintenance/reports maintenance/state
```

Edit `maintenance/config.json`. Each enabled service needs its official GitHub repository, container name, version command, Compose directory, and official upgrade-documentation URL. Version commands are executed inside the named running container; installed versions are not hard-coded.

Optional environment variables:

| Variable | Purpose |
| --- | --- |
| `NEWS4LEGENDS_MAINTENANCE_CONFIG` | Alternate service configuration file |
| `NEWS4LEGENDS_MAINTENANCE_REPORTS_DIR` | Report output directory |
| `NEWS4LEGENDS_MAINTENANCE_STATE_DIR` | Advisory cache and alert fingerprint directory |
| `NEWS4LEGENDS_BACKUP_LOG` | Operator-selected backup log checked before remediation |
| `GITHUB_TOKEN` | Optional GitHub API token to increase rate limits; never commit it |
| `NEWS4LEGENDS_MAINTENANCE_WEBHOOK` | Optional private JSON webhook for alerts |
| `NEWS4LEGENDS_SECURITY_URL` | Dashboard URL included in weekly alerts |
| `NEWS4LEGENDS_MAINTENANCE_OFFLINE=1` | Skip network advisory queries for offline diagnostics/tests |

The UI reads reports only. Compose mounts `${MAINTENANCE_REPORTS_DIR:-./maintenance/reports}` at `/security-reports:ro`.

## Run modes

```bash
./maintenance/run.sh manual
./maintenance/run.sh scheduled
./maintenance/run.sh weekly
```

- `manual` refreshes reports and history without sending an alert.
- `scheduled` sends only a new or changed confirmed Critical/High result. A state fingerprint prevents duplicate alerts.
- `weekly` creates and attempts to send a complete weekly status message.

If no webhook is configured, reports are still generated and the alert is explicitly skipped. No fingerprint is recorded for an unsent alert.

## Schedule safely

Use the same unprivileged operator account that can run the required read-only Docker and package commands. For example, after testing the exact absolute repository path:

```cron
17 7 * * * cd /ABSOLUTE/PATH/news4legends && ./maintenance/run.sh scheduled
30 8 * * 1 cd /ABSOLUTE/PATH/news4legends && ./maintenance/run.sh weekly
```

Do not place secrets directly in a crontab. Use a protected environment file or service-manager credentials appropriate to your host.

## Reports

- `maintenance/reports/current.json`: latest structured result.
- `maintenance/reports/history/*.json`: up to 90 structured snapshots.
- `maintenance/reports/actionable.txt`: human-readable confirmed and uncertain findings.
- `maintenance/reports/telegram-security.txt`: bounded Critical/High alert body.
- `maintenance/state/last-critical-high.sha256`: deduplication fingerprint.

Reports and state are runtime data and are ignored by Git. They may reveal installed versions or infrastructure details; do not publish them.

## Manual remediation

Follow the backup-first procedure in [Upgrading](UPGRADING.md). Confirm the installed version dynamically, validate that the advisory applies to the installed branch, verify a recent checksum-valid backup, record the current image ID, update one component, validate it, rerun `manual`, and retain the rollback path. Never convert these scripts into an automatic upgrader.

## Optional malware, container and Debian scanning

The repository also contains opt-in wrappers for ClamAV and Trivy. They do not install scanners, delete files, quarantine findings or upgrade images.

| Variable | Purpose |
| --- | --- |
| `NEWS4LEGENDS_MAINTENANCE_ROOT` | Writable reports/state root; default `/var/lib/news4legends/maintenance` |
| `N4L_CLAMAV_TARGETS` | Colon-separated scan roots; default `/app:/var/lib/news4legends` |
| `N4L_HOST_LABEL` | Public-safe label used in alerts |
| `N4L_TRIVY_IMAGE` | Scanner image; default `aquasec/trivy:latest` |
| `N4L_SECURITY_WEBHOOK_URL` | Optional JSON webhook; an unset value causes a safe explicit skip |

Run `maintenance/run_host_av.sh`, `maintenance/run_container_scan.sh` or
`maintenance/run_debian_scan.sh` only after reviewing privileges and targets.
Container scanning needs Docker access. Debian scanning mounts the host root
read-only into Trivy. Both therefore run from a dedicated administrator
context, never from the public UI.

The vulnerability scanners write:

- `container-vulnerabilities.json` and `debian-vulnerabilities.json`: separate
  current inventories with package, CVE, installed and fixed versions;
- `container-vulnerability-trends.json` and
  `debian-vulnerability-trends.json`: bounded 90-observation histories;
- `remediation-prompt.txt`: combined copyable manual-review input; and
- `*-notified.json` under state: per-event delivery fingerprints.

Critical and High events may be sent to `N4L_SECURITY_WEBHOOK_URL`. Repeating an
identical scan does not resend an identical event. Medium and Low findings
remain in dashboards and reports. No scanner applies upgrades.

To install the supplied schedule, copy `maintenance/security.env.example` to
`/etc/news4legends/security.env`, set mode `600`, replace its absolute path,
test every scanner manually, then run:

```bash
sudo ./scripts/install-security-schedule.sh
```

The generated cron file runs application advisory checks daily, container and
Debian scans weekly, and a weekly summary. Secrets remain in the protected env
file, not in crontab.

## Optional system health monitor

`health/monitor.py` records bounded 30-day host/service samples and publishes `system-health.json` for the read-only dashboard. Paths, required containers, worker URL and backup signal are configured through `N4L_HEALTH_ROOT`, `N4L_REPORT_DIR`, `N4L_MONITORED_CONTAINERS`, `NEWS4LEGENDS_WORKER_URL` and `N4L_BACKUP_LOG`. Missing optional targets produce partial/unavailable signals instead of preventing the core UI and worker from starting.

`health/alert_dispatcher.py` delivers only newly journaled incident transitions. Configure `N4L_HEALTH_WEBHOOK_URL`, `N4L_HEALTH_DASHBOARD_URL` and `TZ`; with no webhook it reports a skipped notification and does not claim delivery.
