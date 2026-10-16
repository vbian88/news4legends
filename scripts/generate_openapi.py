#!/usr/bin/env python3
"""Generate a deterministic OpenAPI contract without production data."""

import json
import os
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "ui"))

with tempfile.TemporaryDirectory() as directory:
    os.environ["NEWS4LEGENDS_DB_PATH"] = str(Path(directory) / "openapi.sqlite3")
    os.environ["NEWS4LEGENDS_STATIC_DIR"] = str(Path(directory) / "static")
    import app
    contract = app.app.openapi()

output = root / "docs" / "openapi.json"
output.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(output)
