# Security policy

## Supported version and reporting

News 4 Legends is a self-hosted v1 project; fixes target the latest published revision. Report vulnerabilities through **GitHub Private Vulnerability Reporting** in the repository's Security tab. Do not open a public issue containing an exploitable vulnerability, credentials, private URLs, or personal data. Include the affected revision, deployment context, reproduction steps, impact, and any proposed mitigation.

Private Vulnerability Reporting is enabled for this repository.

## Best-effort security information and disclaimer

All security-related features, checks, classifications, alerts, dashboards, documentation, advisory links and remediation guidance supplied by News 4 Legends are provided on a **best-effort, informational basis only**. They may be incomplete, delayed, inaccurate, outdated or affected by differences in vendor data, version formats, deployment configuration and advisory metadata.

A reported finding does not establish that a particular installation is exploitable. The absence of a finding, warning or alert does not establish that an installation is secure. News 4 Legends is not a substitute for professional security assessment, continuous monitoring, vendor support or independent review of the relevant official advisory.

The software does not automatically apply security updates. The operator is responsible for securing the host and network, protecting credentials and backups, reviewing official advisories, determining whether findings apply, testing changes, maintaining recovery procedures and deciding whether or when to remediate.

To the maximum extent permitted by applicable law, the software and all security-related information are provided **"AS IS" and "AS AVAILABLE", without warranty of any kind**, including any warranty that security checks will identify every vulnerability, correctly determine exploitability or prevent compromise, data loss, service interruption or other harm. The authors and contributors disclaim liability for losses or damages arising from use of, inability to use, or reliance on the software or its security-related output. This section supplements the [MIT License](LICENSE); it does not replace it and does not exclude any liability that cannot lawfully be excluded.

## Deployment boundary

The supplied deployment is for a trusted LAN or private network. The UI and worker API have no user authentication. The example sets `N8N_SECURE_COOKIE=false` for private-LAN HTTP access; that is unsuitable for direct public exposure.

Do not expose the UI, worker API, or n8n directly to the Internet. For remote access, use a VPN or a deliberately configured reverse proxy with TLS, strong authentication, authorization, rate limiting, and firewall rules.

## Never publish

- `.env`, LLM keys, bearer tokens, OAuth secrets/tokens, Gmail credentials, or Telegram tokens
- n8n credential records, encryption keys, or persistent state
- production databases, SSH private keys, personal addresses/chat IDs, logs, runtime data, or backups

Store the LLM key in `secrets/llm_api_key` with mode `600`. n8n credential encryption state is recovery-critical; protect the complete `n8n_data` volume and do not rotate its encryption material casually.

## Untrusted content

Sources are untrusted Internet inputs. Use bounded settings and validate before enabling. `PASS` means bounded extraction worked during the check; it is not a truth or safety certificate. LLM summaries can be incomplete or wrong; open and evaluate linked sources for consequential decisions.

## Export and backup hygiene

Removing credential bindings does not sanitize an n8n export. Parameters may contain recipients, BCC lists, chat IDs, URLs, pinned data, and metadata. Inspect JSON as text.

Backups can contain credentials and private state. The documented backup method is not inherently encrypted. Restrict access and add suitable encryption. A backup is incomplete until restoration is tested.

## Release check

Before each public release, scan all files for secrets and identities; confirm no databases, logs, runtime data, or backups exist; inspect `.env.example` and n8n JSON manually; and validate Python, JSON, Compose, links, and paths.

See [Backup and restore](docs/BACKUP-RESTORE.md), [Operations](docs/OPERATIONS.md), and [Upgrading](docs/UPGRADING.md).
