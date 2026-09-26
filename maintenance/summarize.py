#!/usr/bin/env python3
import os, re
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("NEWS4LEGENDS_MAINTENANCE_ROOT", SCRIPT_DIR))
REPORTS = Path(os.environ.get(
    "NEWS4LEGENDS_MAINTENANCE_REPORTS_DIR", ROOT / "reports"
))
src = REPORTS / "actionable.txt"
dst = REPORTS / "alert.txt"

severity_rank = {"CRITICAL":4,"HIGH":3,"MEDIUM":2,"LOW":1}
items = defaultdict(lambda: {"severity":"LOW","ids":[],"urls":[]})

current = None
for line in src.read_text().splitlines():
    m = re.match(r"^(CRITICAL|HIGH|MEDIUM|LOW): (.+?) ([0-9][^\s]*)$", line)
    if m:
        sev, service, version = m.groups()
        current = service
        d = items[service]
        d["version"] = version
        if severity_rank[sev] > severity_rank[d["severity"]]:
            d["severity"] = sev
    elif current and line.startswith("Advisory: "):
        items[current]["ids"].append(line.split(": ",1)[1])
    elif current and line.startswith("Official advisory: "):
        items[current]["urls"].append(line.split(": ",1)[1])

order = sorted(items, key=lambda x: -severity_rank[items[x]["severity"]])

out = [
    "🚨 NEWS 4 LEGENDS SECURITY",
    "",
    "Installed-version vulnerability matches were detected.",
    "No automatic upgrade has been performed.",
    ""
]

for service in order:
    d = items[service]
    out += [
        f'{d["severity"]}: {service} {d["version"]}',
        f'Applicable advisories detected: {len(set(d["ids"]))}',
    ]
    for advisory in list(dict.fromkeys(d["ids"]))[:5]:
        out.append(f'  - {advisory}')
    if len(set(d["ids"])) > 5:
        out.append(f'  + {len(set(d["ids"])) - 5} more')
    if d["urls"]:
        out.append(f'Official advisory: {d["urls"][0]}')
    out += [""]

out += [
    "Action:",
    "Review the maintenance report before upgrading.",
    "Verify backup, then upgrade one component at a time.",
    "",
    "Full report:",
    str(src),
]

dst.write_text("\n".join(out) + "\n")
print(dst.read_text())
