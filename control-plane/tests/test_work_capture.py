from datetime import datetime, timedelta, timezone
import pytest

from genesis_control_plane.evidence import EvidenceJournal
from genesis_control_plane.work_capture import accept_packet, sign_packet
from genesis_control_plane.work_evidence import summarize_work_journal

SECRET = b"test-only-long-enough-local-key-not-for-production"
T = datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc)


def packet(**overrides):
    data = dict(kind="work.input", payload={
        "work_id":"W-01", "message_id":"M-1", "channel":"voice_live",
        "provenance":"observed", "nature":"narration", "modalities":["text","image"],
        "attachments":[{"asset_id":"ASSET-1","modality":"image"}], "capture_id":"CAPTURE-1"},
        station_id="GES-ALPHA-001", principal_id="DM-001", session_id="SESSION-1",
        correlation_id="CORR-1", source="approved_device", issued_at=T.isoformat())
    data.update(overrides)
    return sign_packet(data, SECRET)


def accept(journal, value):
    return accept_packet(journal, value, key=SECRET, expected_station_id="GES-ALPHA-001",
                         expected_principal_id="DM-001", expected_source="approved_device", now=T)


def test_signed_capture_recorded_and_idempotent(tmp_path):
    j = EvidenceJournal(tmp_path / "j.jsonl")
    p = packet()
    a = accept(j, p)
    b = accept(j, p)
    assert a == b
    result = summarize_work_journal(tmp_path / "j.jsonl", "W-01")
    assert result["channels_observed"] == {"voice_live": 1}
    assert result["input_messages"] == 1
    assert result["attached_assets"]["image"] == 1
    assert result["evidence_events"] == 1


def test_capture_signature_and_scope_required(tmp_path):
    j = EvidenceJournal(tmp_path / "j.jsonl")
    with pytest.raises(ValueError, match="BAD_SIGNATURE"):
        bad = packet()
        bad["payload"]["channel"] = "typed"
        accept(j, bad)
    with pytest.raises(ValueError, match="WRONG_AUTHORITY_SCOPE"):
        accept(j, packet(station_id="PROD"))
    assert not j._records()


def test_reserved_warden_events_denied(tmp_path):
    j = EvidenceJournal(tmp_path / "j.jsonl")
    with pytest.raises(ValueError, match="REQUIRES_WARDEN"):
        accept(j, packet(kind="work.approved", payload={"work_id":"W-01", "deliverable_id":"D-1", "capture_id":"C2"}))


def test_expired_capture_denied(tmp_path):
    j = EvidenceJournal(tmp_path / "j.jsonl")
    with pytest.raises(ValueError, match="EXPIRED"):
        accept(j, packet(issued_at=(T - timedelta(hours=1)).isoformat()))


def test_capture_id_conflict_denied(tmp_path):
    j = EvidenceJournal(tmp_path / "j.jsonl")
    accept(j, packet())
    changed = packet(payload={**packet()["payload"], "message_id": "M-2"})
    with pytest.raises(ValueError, match="ID_CONFLICT"):
        accept(j, changed)
