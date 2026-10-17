#!/usr/bin/env python3
import json
import os
import tempfile
from pathlib import Path

from vulnerability_report import remediation_prompt

root = Path(os.environ.get("NEWS4LEGENDS_MAINTENANCE_ROOT", "/var/lib/news4legends/maintenance"))
reports = root / "reports"


def read(name):
    try:
        value = json.loads((reports / name).read_text(encoding="utf-8"))
        return value if value.get("schema_version") == 1 else {}
    except (OSError, ValueError, TypeError):
        return {}


content = remediation_prompt(
    read("container-vulnerabilities.json"),
    read("debian-vulnerabilities.json"),
)
fd, temporary = tempfile.mkstemp(prefix=".remediation-", dir=reports)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, reports / "remediation-prompt.txt")
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
