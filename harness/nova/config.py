"""Paths and constants. Code and assets resolve from this file's location; mutable state only under --state-dir."""
from __future__ import annotations

from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = HARNESS_DIR / "assets"
DB_NAME = "nova.sqlite3"
BLOB_DIR = "blobs"
TRACE_DIR = "traces"
SCHEMA_VERSION = "1.0"
OCR_DPI = 200


def state_paths(state_dir: str | Path) -> dict[str, Path]:
    root = Path(state_dir).resolve()
    return {"root": root, "db": root / DB_NAME, "blobs": root / BLOB_DIR, "traces": root / TRACE_DIR}
