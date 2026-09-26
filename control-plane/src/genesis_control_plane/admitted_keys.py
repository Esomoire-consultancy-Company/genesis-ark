"""Local Alpha trust snapshot for signed requests.

The operator provisions this file independently of request input. It is a
development adapter; a Genesis governed key registry is needed for deployment.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class FileActorKeyResolver:
    def __init__(self, path: Path):
        self._path = path

    def active_ed25519_key(self, principal_id: str, key_id: str, at: datetime) -> bytes | None:
        # Reload for each decision and each gateway check; removed keys fail closed.
        rows = json.loads(self._path.read_text(encoding="utf-8"))["keys"]
        matched = [r for r in rows if r["principal_id"] == principal_id and r["key_id"] == key_id]
        if len(matched) != 1:
            return None
        row = matched[0]
        if row["state"] != "active":
            return None
        start = datetime.fromisoformat(row["valid_from"])
        end = datetime.fromisoformat(row["valid_until"])
        if at.tzinfo is None or start.tzinfo is None or end.tzinfo is None:
            return None
        if not start <= at < end:
            return None
        return bytes.fromhex(row["public_key_hex"])
