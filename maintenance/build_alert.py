#!/usr/bin/env python3
import json, os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("NEWS4LEGENDS_MAINTENANCE_ROOT", SCRIPT_DIR))
REPORTS = Path(os.environ.get(
    "NEWS4LEGENDS_MAINTENANCE_REPORTS_DIR", ROOT / "reports"
))
CONFIG_PATH = Path(os.environ.get(
    "NEWS4LEGENDS_MAINTENANCE_CONFIG", ROOT / "config.json"
))
if not CONFIG_PATH.exists():
    CONFIG_PATH = SCRIPT_DIR / "config.example.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
current=json.loads((REPORTS / "current.json").read_text(encoding="utf-8"))

eligible=[
    f for f in current["findings"]
    if f["severity"] in ("CRITICAL","HIGH")
]

blocks=[]

for f in eligible:
    # current.json contains the exact vulnerability branch that the
    # classifier verified against the installed version. Use that instead
    # of unrelated patched branches returned by the advisory API.
    patches=[]
    for match in f.get("matches") or []:
        pv=str(match.get("patched") or "").strip()
        if pv and pv != "not published" and pv not in patches:
            patches.append(pv)

    compose = CONFIG["services"].get(
        f["service"], {}
    ).get("compose_dir", ".")

    block=[
        f'🚨 {f["severity"]}: {f["service"]} {f["installed"]}',
        f'{f["id"]}: {f["summary"]}',
        f'Patched version(s): {", ".join(patches) if patches else "See advisory"}',
        f'Official advisory: {f["url"]}',
        '',
        'Manual remediation:',
        '1. Verify the News Automation backup is current and checksum-valid.',
        f'2. Review {compose}/docker-compose.yml and record the current image ID.',
        f'3. Follow the vendor advisory/release guidance and update only {f["service"]}.',
        '4. Recreate only that service/container.',
        '5. Verify container health and installed version.',
        f'6. Run {SCRIPT_DIR / "run.sh"} manual again.',
        '7. Confirm this finding disappears from the Security dashboard.',
        '',
        'No automatic upgrade has been performed.',
    ]
    blocks.append("\n".join(block))

message="🛡 NEWS 4 LEGENDS SECURITY\n\n" + "\n\n".join(blocks)

# Leave margin below Telegram's message ceiling.
if len(message)>3800:
    message=message[:3700] + "\n\n[Additional details: Security dashboard]"

out=REPORTS/"telegram-security.txt"
out.write_text(message+"\n")
print(message)
print(f"\nMESSAGE_LENGTH={len(message)}")
