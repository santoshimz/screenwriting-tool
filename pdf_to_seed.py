#!/usr/bin/env python3
"""
Write static/seed-import.json from a screenplay PDF URL (optional local dev helper).
For normal use, import from the app: Import PDF button.

  .venv/bin/python pdf_to_seed.py 'https://example.com/your-script.pdf'

Only use PDFs you have the right to import.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

from screenplay_import import import_pdf_bytes

APP_DIR = Path(__file__).resolve().parent
OUT_PATH = APP_DIR / "static" / "seed-import.json"


def fetch_pdf(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ScreenplayImport/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python pdf_to_seed.py <pdf-url>", file=sys.stderr)
        print("Only import PDFs you have the right to use.", file=sys.stderr)
        return 2
    url = sys.argv[1]
    print("Downloading…", file=sys.stderr)
    data = fetch_pdf(url)
    payload = import_pdf_bytes(data)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    beats = payload.get("beats") or []
    print(f"Wrote {OUT_PATH} ({len(beats)} beats)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
