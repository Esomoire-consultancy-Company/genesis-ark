import json

from genesis_control_plane.contracts import EvidenceEvent
from genesis_control_plane.evidence import EvidenceJournal


def event(event_id: str, payload=None):
    return EvidenceEvent(
        event_id=event_id,
        event_type="test.event",
        schema_version="1.0",
        occurred_at="2026-09-09T08:15:00+05:30",
        station_id="GES-ALPHA-001",
        principal_id="DM-001",
        session_id="SES-001",
        source="test",
        subject="RES-RIVER-WORKER-001",
        payload=payload or {"ok": True},
        correlation_id="CORR-001",
        causation_id=None,
        classification="internal",
    )


def test_first_and_second_records_form_hash_chain(tmp_path):
    journal = EvidenceJournal(tmp_path / "river.jsonl")
    first = journal.append(event("EVT-001"))
    second = journal.append(event("EVT-002"))
    assert first.previous_hash is None
    assert second.previous_hash == first.record_hash
    assert second.line_number == 2
    assert journal.verify_chain()


def test_tampering_breaks_chain(tmp_path):
    path = tmp_path / "river.jsonl"
    journal = EvidenceJournal(path)
    journal.append(event("EVT-001", {"value": 1}))
    journal.append(event("EVT-002", {"value": 2}))
    lines = path.read_text().splitlines()
    record = json.loads(lines[0])
    record["event"]["payload"]["value"] = 999
    lines[0] = json.dumps(record, separators=(",", ":"), sort_keys=True)
    path.write_text("\n".join(lines) + "\n")
    assert not journal.verify_chain()


def test_journal_persists_only_explicit_event_payload(tmp_path):
    path = tmp_path / "river.jsonl"
    journal = EvidenceJournal(path)
    journal.append(event("EVT-001", {"token_id": "WCT-001"}))
    persisted = path.read_text()
    assert "WCT-001" in persisted
    assert "test-secret" not in persisted
