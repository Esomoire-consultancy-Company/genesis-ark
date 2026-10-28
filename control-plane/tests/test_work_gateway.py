"""GWIEP R0.3 gateway admission security and River consistency tests."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from genesis_control_plane.work_capture import sign_packet
from genesis_control_plane.work_gateway import (
    AdmissionDenied, ConsentGrant, RegisteredSource, WorkIntakeGateway,
    issue_local_test_session, verify_local_session,
)

IDENTITY_KEY = b"test-identity-signing-only-not-for-real-use-123"
SOURCE_KEY = b"test-source-signing-unique-not-for-real-use-456"
NOW = datetime(2026, 10, 28, 8, 15, tzinfo=timezone.utc)


def setup(tmp_path, *, tenant="BNR-TENANT-001", work="GW-001", active=True,
          consent=True, expires=None, channels=None):
    source = RegisteredSource(tenant, "DM-001", "GES-ALPHA-001", "approved_device",
                              frozenset(channels or {"typed", "voice_dictation", "voice_live"}),
                              active=active)
    grant = ConsentGrant("CONSENT-001", tenant, "DM-001", "GES-ALPHA-001", "approved_device",
                         work, valid_until=expires or NOW+timedelta(hours=1), active=consent)
    ledger = tmp_path / "acceptances.sqlite"
    journal = tmp_path / "river.jsonl"
    gateway = WorkIntakeGateway(ledger_path=ledger, journal_path=journal,
                                 identity_signing_key=IDENTITY_KEY,
                                 source_signing_key=SOURCE_KEY, source=source, grant=grant)
    claims = dict(tenant_id=tenant, principal_id="DM-001", station_id="GES-ALPHA-001",
                  source="approved_device", session_id="SESSION-001",
                  audience="genesis-work-intake-alpha",
                  issued_at=(NOW-timedelta(minutes=1)).isoformat(),
                  expires_at=(NOW+timedelta(minutes=10)).isoformat())
    token = issue_local_test_session(claims, IDENTITY_KEY)
    payload = dict(tenant_id=tenant, work_id=work, message_id="MSG-001", capture_id="CAP-001",
                   channel="voice_dictation", provenance="observed", nature="command",
                   modalities=["text", "image"],
                   attachments=[{"asset_id":"IMG-001","modality":"image"}])
    unsigned = dict(kind="work.input", payload=payload,
                    station_id="GES-ALPHA-001", principal_id="DM-001",
                    session_id="SESSION-001", correlation_id="CORR-001",
                    source="approved_device", issued_at=NOW.isoformat())
    return gateway, token, sign_packet(unsigned, SOURCE_KEY)


def resign(packet):
    return sign_packet({k: v for k, v in packet.items() if k != "signature"}, SOURCE_KEY)


def test_admission_and_reconciliation_are_stable(tmp_path):
    gateway, token, packet = setup(tmp_path)
    first = gateway.admit(session_token=token, packet=packet, now=NOW)
    assert not first.duplicate
    assert first.policy_id == "WARDEN-WORK-INTAKE-ALPHA-R0.3"
    second = gateway.admit(session_token=token, packet=packet, now=NOW)
    assert second.duplicate and second.record_hash == first.record_hash
    assert gateway.reconcile() == {
        "indexed_acceptances": 1, "river_events": 1,
        "missing_receipts": [], "unindexed_river_captures": [],
        "consistent": True, "journal_hash_chain_verified": True,
    }


def test_persistent_idempotency_after_restart(tmp_path):
    gateway, token, packet = setup(tmp_path)
    receipt = gateway.admit(session_token=token, packet=packet, now=NOW)
    next_gateway, next_token, same_packet = setup(tmp_path)
    assert next_gateway.admit(session_token=next_token, packet=same_packet, now=NOW).duplicate
    assert next_gateway.reconcile()["indexed_acceptances"] == 1
    assert receipt.record_hash == next_gateway.admit(session_token=next_token, packet=same_packet, now=NOW).record_hash


def test_invalid_source_signature_rejected_even_on_cache_hit(tmp_path):
    gateway, token, packet = setup(tmp_path)
    gateway.admit(session_token=token, packet=packet, now=NOW)
    copied = dict(packet)
    copied["signature"] = "0" * 64
    with pytest.raises(AdmissionDenied, match="GATEWAY_SOURCE_PACKET_DENIED"):
        gateway.admit(session_token=token, packet=copied, now=NOW)


def test_source_replay_with_conflicting_payload_rejected(tmp_path):
    gateway, token, packet = setup(tmp_path)
    gateway.admit(session_token=token, packet=packet, now=NOW)
    changed = dict(packet, payload={**packet["payload"], "message_id": "MSG-002"})
    with pytest.raises(AdmissionDenied, match="GATEWAY_CAPTURE_ID_CONFLICT"):
        gateway.admit(session_token=token, packet=resign(changed), now=NOW)


def test_invalid_session_and_forged_tenant_denied(tmp_path):
    gateway, token, packet = setup(tmp_path)
    fake = dict(token, claims={**token["claims"], "tenant_id": "OTHER"})
    with pytest.raises(AdmissionDenied, match="GATEWAY_SESSION_SIGNATURE_INVALID"):
        gateway.admit(session_token=fake, packet=packet, now=NOW)
    valid_other = issue_local_test_session(fake["claims"], IDENTITY_KEY)
    with pytest.raises(AdmissionDenied, match="WARDEN_ACTOR_BINDING_DENIED"):
        gateway.admit(session_token=valid_other, packet=packet, now=NOW)


def test_payload_tenant_cannot_mismatch_identity(tmp_path):
    gateway, token, packet = setup(tmp_path)
    changed = dict(packet, payload={**packet["payload"], "tenant_id": "OTHER"})
    with pytest.raises(AdmissionDenied, match="WARDEN_TENANT_BINDING_DENIED"):
        gateway.admit(session_token=token, packet=resign(changed), now=NOW)


@pytest.mark.parametrize("option,expected", [
    ({"active": False}, "WARDEN_SOURCE_REVOKED"),
    ({"consent": False}, "WARDEN_CONSENT_REVOKED"),
    ({"expires": NOW-timedelta(seconds=1)}, "WARDEN_CONSENT_EXPIRED"),
    ({"channels": {"typed"}}, "WARDEN_SOURCE_CHANNEL_DENIED"),
])
def test_warden_denies_inactive_or_excess_scope(tmp_path, option, expected):
    gateway, token, packet = setup(tmp_path, **option)
    with pytest.raises(AdmissionDenied, match=expected):
        gateway.admit(session_token=token, packet=packet, now=NOW)


def test_wrong_workstream_denied(tmp_path):
    gateway, token, packet = setup(tmp_path)
    changed = dict(packet, payload={**packet["payload"], "work_id": "OTHER-WORK"})
    with pytest.raises(AdmissionDenied, match="WARDEN_WORKSTREAM_DENIED"):
        gateway.admit(session_token=token, packet=resign(changed), now=NOW)


def test_unverified_historic_origin_denied_on_live_capture(tmp_path):
    gateway, token, packet = setup(tmp_path)
    changed = dict(packet, payload={**packet["payload"],
                   "channel": "import_unknown", "provenance": "unknown"})
    with pytest.raises(AdmissionDenied, match="WARDEN_SOURCE_CHANNEL_DENIED"):
        gateway.admit(session_token=token, packet=resign(changed), now=NOW)


def test_client_cannot_approve_or_finalize_work(tmp_path):
    gateway, token, packet = setup(tmp_path)
    for kind in ("work.verified", "work.approved", "work.finalized", "work.reopened"):
        changed = dict(packet, kind=kind, payload={
            "tenant_id": "BNR-TENANT-001", "work_id": "GW-001",
            "deliverable_id": "D-1", "capture_id": "CAP-001"})
        with pytest.raises(AdmissionDenied, match="WARDEN_CAPABILITY_DENIED"):
            gateway.admit(session_token=token, packet=resign(changed), now=NOW)


def test_expired_identity_session_denied(tmp_path):
    gateway, token, packet = setup(tmp_path)
    claims = {**token["claims"], "expires_at": (NOW-timedelta(seconds=1)).isoformat()}
    expired = issue_local_test_session(claims, IDENTITY_KEY)
    with pytest.raises(AdmissionDenied, match="GATEWAY_SESSION_EXPIRED"):
        gateway.admit(session_token=expired, packet=packet, now=NOW)


def test_expired_capture_denied(tmp_path):
    gateway, token, packet = setup(tmp_path)
    expired = dict(packet, issued_at=(NOW-timedelta(hours=2)).isoformat())
    with pytest.raises(AdmissionDenied, match="GATEWAY_SOURCE_PACKET_DENIED"):
        gateway.admit(session_token=token, packet=resign(expired), now=NOW)


def test_tampered_river_detected_on_retry(tmp_path):
    gateway, token, packet = setup(tmp_path)
    gateway.admit(session_token=token, packet=packet, now=NOW)
    f = tmp_path / "river.jsonl"
    f.write_text(f.read_text().replace('"voice_dictation"', '"typed"'))
    with pytest.raises(AdmissionDenied, match="GATEWAY_RIVER_CHAIN_INVALID"):
        gateway.admit(session_token=token, packet=packet, now=NOW)


def test_reconcile_finds_orphan_event(tmp_path):
    gateway, token, packet = setup(tmp_path)
    # Simulate River append succeeding but process interruption before SQLite index.
    from genesis_control_plane.work_capture import accept_packet
    accept_packet(gateway.journal, packet, key=SOURCE_KEY, now=NOW,
                  expected_station_id="GES-ALPHA-001", expected_principal_id="DM-001",
                  expected_source="approved_device")
    r = gateway.reconcile()
    assert not r["consistent"] and len(r["unindexed_river_captures"]) == 1
    # A retry recovers the record and creates a durable index.
    gateway.admit(session_token=token, packet=packet, now=NOW)
    assert gateway.reconcile()["consistent"]


def test_reconcile_finds_orphan_index(tmp_path):
    gateway, token, packet = setup(tmp_path)
    gateway.admit(session_token=token, packet=packet, now=NOW)
    (tmp_path / "river.jsonl").unlink()
    assert not gateway.reconcile()["consistent"]
    with pytest.raises(AdmissionDenied, match="GATEWAY_RIVER_RECEIPT_MISMATCH"):
        gateway.admit(session_token=token, packet=packet, now=NOW)


def test_session_signature_required(tmp_path):
    gateway, token, packet = setup(tmp_path)
    with pytest.raises(AdmissionDenied, match="GATEWAY_SESSION_SIGNATURE_INVALID"):
        gateway.admit(session_token={"claims": token["claims"], "signature": "bad"}, packet=packet, now=NOW)


def test_identity_source_keys_cannot_be_identical(tmp_path):
    gateway, token, packet = setup(tmp_path)
    with pytest.raises(AdmissionDenied, match="GATEWAY_KEY_SEPARATION_REQUIRED"):
        WorkIntakeGateway(ledger_path=tmp_path / "second.sqlite", journal_path=tmp_path / "second.jsonl",
                          identity_signing_key=IDENTITY_KEY, source_signing_key=IDENTITY_KEY,
                          source=gateway.warden.registered_source, grant=gateway.warden.grant)
