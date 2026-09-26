#!/usr/bin/env python3
import json
import os
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("NEWS4LEGENDS_MAINTENANCE_ROOT", SCRIPT_DIR))
REPORTS = Path(os.environ.get(
    "NEWS4LEGENDS_MAINTENANCE_REPORTS_DIR", ROOT / "reports"
))
STATE = Path(os.environ.get(
    "NEWS4LEGENDS_MAINTENANCE_STATE_DIR", ROOT / "state"
))
CONFIG_PATH = Path(os.environ.get(
    "NEWS4LEGENDS_MAINTENANCE_CONFIG", ROOT / "config.json"
))
if not CONFIG_PATH.exists():
    CONFIG_PATH = SCRIPT_DIR / "config.example.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
SERVICES = {
    name: cfg
    for name, cfg in CONFIG.get("services", {}).items()
    if cfg.get("enabled", True)
}

def cmd(args):
    try:
        return subprocess.run(args, text=True, capture_output=True)
    except (FileNotFoundError, OSError) as exc:
        return subprocess.CompletedProcess(
            args=args,
            returncode=127,
            stdout="",
            stderr=str(exc),
        )

def get_json(url):
    if os.environ.get("NEWS4LEGENDS_MAINTENANCE_OFFLINE") == "1":
        raise RuntimeError("network checks disabled by configuration")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "News4Legends-Maintenance-Checker/1.0",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        url,
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)

now = datetime.now(timezone.utc)
lines = [
    "NEWS 4 LEGENDS - MAINTENANCE / SECURITY REPORT",
    f"Generated UTC: {now.isoformat()}",
    "",
    "NO AUTOMATIC UPGRADES ARE PERFORMED.",
    "",
]

# Host security/package updates
apt = cmd(["apt-get", "-s", "upgrade"])
updates = [x for x in apt.stdout.splitlines() if x.startswith("Inst ")]
security = [x for x in updates if "Security:" in x or "security" in x.lower()]

lines += [
    "=== DEBIAN ===",
    f"Pending package updates: {len(updates)}",
    f"Security-repository updates: {len(security)}",
]

for x in security[:30]:
    lines.append("SECURITY: " + x)

lines += [
    "",
    "Manual procedure:",
    "  apt update",
    "  apt list --upgradable",
    "  apt-get -s upgrade",
    "  # review before:",
    "  apt upgrade",
    "Validation:",
    "  systemctl --failed",
    "  docker ps",
    "Rollback: use package-specific downgrade/recovery if required;",
    "          verify backup before applying updates.",
    "Official security tracker:",
    "  https://security-tracker.debian.org/tracker/",
    "",
]

# Docker / Compose
docker = cmd(["docker", "version", "--format", "{{.Server.Version}}"]).stdout.strip()
compose = cmd(["docker", "compose", "version", "--short"]).stdout.strip()
docker = docker or "UNAVAILABLE"
compose = compose or "UNAVAILABLE"
lines += [
    "=== DOCKER ===",
    f"Installed Docker: {docker}",
    f"Installed Compose: {compose}",
    "Official releases:",
    "  https://docs.docker.com/engine/release-notes/",
    "Upgrade:",
    "  apt update",
    "  apt-cache policy docker-ce docker-ce-cli containerd.io docker-compose-plugin",
    "  # review versions, then use apt install with selected versions",
    "Validation:",
    "  docker version",
    "  docker compose version",
    "  docker ps",
    "",
]

# Running services + GitHub releases/advisories
lines.append("=== APPLICATION SERVICES ===")
advisory_state = {}
for name, cfg in SERVICES.items():
    repo = cfg["repo"]
    try:
        release = get_json(f"https://api.github.com/repos/{repo}/releases/latest")
        latest = release.get("tag_name", "UNKNOWN")
        release_url = release.get("html_url", "")
    except Exception as e:
        latest = "CHECK FAILED"
        release_url = f"GitHub query error: {e}"

    try:
        advisories = get_json(
            f"https://api.github.com/repos/{repo}/security-advisories?per_page=10"
        )
    except Exception:
        advisories = []
    advisory_state[name] = advisories

    lines += [
        "",
        f"[{name}]",
        f"Latest upstream release: {latest}",
        f"Release notes: {release_url}",
        f"Official upgrade documentation: {cfg.get('docs', '')}",
    ]

    if advisories:
        lines.append("Recent GitHub security advisories:")
        for a in advisories[:10]:
            cve = a.get("cve_id") or a.get("ghsa_id", "UNKNOWN")
            severity = a.get("severity", "unknown").upper()
            url = a.get("html_url", "")
            lines.append(f"  {severity}: {cve} - {url}")
    else:
        lines.append("GitHub security advisories: none returned / unavailable")

    lines += [
        "Manual Docker upgrade pattern:",
        f"  cd {cfg.get('compose_dir', '.')}",
        "  docker compose config",
        "  docker compose pull",
        "  docker compose up -d",
        "  docker compose ps",
        "Rollback:",
        "  restore the previously recorded image/version and recreate only this service.",
    ]

# CISA KEV
lines += ["", "=== CISA KNOWN EXPLOITED VULNERABILITIES ==="]
try:
    kev = get_json(
        "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    )
    keywords = ["docker", "debian"]
    for service_name, service_cfg in SERVICES.items():
        keywords.append(service_name)
        keywords.extend(
            service_cfg.get("repo", "").replace("-", " ").split("/")
        )
    hits = []
    for v in kev.get("vulnerabilities", []):
        text = " ".join(str(v.get(k, "")) for k in
                        ("vendorProject", "product", "vulnerabilityName")).lower()
        if any(k.lower() in text for k in keywords):
            hits.append(v)

    if hits:
        for v in hits[-30:]:
            lines.append(
                f"{v.get('cveID')} | {v.get('vendorProject')} | "
                f"{v.get('product')} | added {v.get('dateAdded')}"
            )
            lines.append(f"  {v.get('shortDescription','')}")
    else:
        lines.append("No product-name matches found in current KEV catalogue.")
except Exception as e:
    lines.append(f"CISA KEV CHECK FAILED: {e}")

# Backup prerequisite
lines += ["", "=== BACKUP PREREQUISITE ==="]
backup_log_value = os.environ.get("NEWS4LEGENDS_BACKUP_LOG", "")
backup_log = Path(backup_log_value) if backup_log_value else None
if backup_log and backup_log.exists():
    st = backup_log.stat()
    age_hours = (now.timestamp() - st.st_mtime) / 3600
    lines.append(f"Backup log age: {age_hours:.1f} hours")
    lines.append("Backup prerequisite: REVIEW LOG/CHECKSUM BEFORE ANY UPGRADE")
else:
    lines.append(
        "Backup prerequisite: REVIEW - configure NEWS4LEGENDS_BACKUP_LOG "
        "and verify the backup before any upgrade"
    )

lines += [
    "",
    "=== OPERATING RULE ===",
    "Before any upgrade:",
    "1. Verify system healthy.",
    "2. Verify recent backup exists, has reasonable size and checksum passes.",
    "3. Record current version/image ID.",
    "4. Read official release notes/advisory.",
    "5. Upgrade ONE component.",
    "6. Validate that component and News 4 Legends.",
    "7. Keep rollback path until accepted.",
]

REPORTS.mkdir(parents=True, exist_ok=True)
STATE.mkdir(parents=True, exist_ok=True)
advisories_path = STATE / "advisories.json"
advisories_path.write_text(
    json.dumps(advisory_state, indent=2) + "\n",
    encoding="utf-8",
)
report = REPORTS / f"maintenance-{now.strftime('%Y%m%dT%H%M%SZ')}.txt"
latest = REPORTS / "latest.txt"

text = "\n".join(lines) + "\n"
report.write_text(text, encoding="utf-8")
latest.write_text(text, encoding="utf-8")

print(text)
print(f"REPORT: {report}")
