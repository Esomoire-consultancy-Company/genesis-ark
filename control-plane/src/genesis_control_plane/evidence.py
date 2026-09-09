from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from genesis_control_plane.canonical import canonical_json, sha256_hex
from genesis_control_plane.contracts import EvidenceEvent


@dataclass(frozen=True)
class EvidenceReceipt:
    event_id: str
    record_hash: str
    previous_hash: str | None
    line_number: int


class EvidenceJournal:
    def __init__(self, path: Path):
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _records(self) -> list[dict]:
        if not self._path.exists():
            return []
        records = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
        return records

    def verify_chain(self) -> bool:
        previous_hash: str | None = None
        try:
            for record in self._records():
                if record.get("previous_hash") != previous_hash:
                    return False
                material = {
                    "event": record["event"],
                    "previous_hash": previous_hash,
                }
                calculated = sha256_hex(canonical_json(material))
                if calculated != record.get("record_hash"):
                    return False
                previous_hash = calculated
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return False
        return True

    def append(self, event: EvidenceEvent) -> EvidenceReceipt:
        if self._path.exists() and not self.verify_chain():
            raise ValueError("EVIDENCE_CHAIN_INVALID")
        records = self._records()
        previous_hash = records[-1]["record_hash"] if records else None
        event_dict = asdict(event)
        material = {"event": event_dict, "previous_hash": previous_hash}
        record_hash = sha256_hex(canonical_json(material))
        record = {**material, "record_hash": record_hash}
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(record) + "\n")
            handle.flush()
        return EvidenceReceipt(
            event_id=event.event_id,
            record_hash=record_hash,
            previous_hash=previous_hash,
            line_number=len(records) + 1,
        )
