"""Machine-verifiable version lock for immutable synthetic scenario contracts."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent
LOCK = ROOT / "fixture-lock.json"
FILES = ("fixtures.json", "scenarios.json")


def hashes() -> dict[str, str]:
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES}


def verify_lock() -> dict:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    if lock.get("fixture_id") != "GENESIS-SYNTHETIC-BASELINE-R01":
        raise ValueError("fixture identity mismatch")
    if lock.get("synthetic") is not True or lock.get("environment") != "synthetic-ci":
        raise ValueError("fixture lock is not synthetic-only")
    if lock.get("sha256") != hashes():
        raise ValueError("fixture integrity mismatch: regenerate lock only through review")
    return lock
