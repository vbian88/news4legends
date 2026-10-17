#!/usr/bin/env python3
"""Generate the complete API PDF from the running source contract."""
import argparse
import os
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "ui"))

parser = argparse.ArgumentParser()
parser.add_argument("output", type=Path)
args = parser.parse_args()

with tempfile.TemporaryDirectory() as directory:
    os.environ["NEWS4LEGENDS_DB_PATH"] = str(Path(directory) / "api.sqlite3")
    os.environ["NEWS4LEGENDS_STATIC_DIR"] = str(Path(directory) / "static")
    from api_guide_pdf import build_api_guide
    content = build_api_guide()

if not content.startswith(b"%PDF-") or len(content) < 5_000:
    raise SystemExit("Generated API guide is not a valid non-empty PDF")
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_bytes(content)
print(args.output)
