"""GWIEP R0.5 synthetic consent/outbox/projection acceptance and denial tests."""
import json
from datetime import timedelta

import pytest

from genesis_control_plane.evidence import EvidenceJournal
from genesis_control_plane.work_evidence import append_work_event
from genesis_control_plane.work_gateway import AdmissionDenied
from genesis_control_plane.work_r05 import WorkEvidenceStaging

from test_work_identity_r04 import NOW, SOURCE_KEY, administrator, env, mint, packet, provision


@pytest.fixture
def stage(env):
    return WorkEvidenceStaging(
        db_path=env["tmp_path"] / "staging.sqlite",
        river_path=env["tmp_path"] / "staged-river.jsonl",
        verifier=env["verifier"], warden_store=env["store"],
        source_key_resolver=lambda tenant, source:
            SOURCE_KEY if tenant == "BNR-T1" and source == "APP-01" else None,
    )


def access(env, *, tenant="BNR-T1", sub="DM-001", scopes="work:consent work:capture work:read",
           jti="JTI-01"):
    return mint(env, tenant=tenant, sub=sub, scopes=scopes, jti=jti)


def optin(stage, env, work="GW-001"):
    return stage.opt_in(access_token=access(env), work_id=work,
                        expires_at=NOW+timedelta(days=1), now=NOW)


def test_no_implicit_consent_or_river_side_effect(stage, env):
    provision(env)
    with pytest.raises(AdmissionDenied, match="R05_SUBJECT_CONSENT_REQUIRED"):
        stage.admit(access_token=access(env), packet=packet(), now=NOW)
    assert not stage.river_path.exists()


def test_subject_opt_in_outbox_projection_and_counts(stage, env):
    provision(env)
    receipt = optin(stage, env)
    assert receipt["status"] == "opted_in" and receipt["generation"] == 1
    accepted = stage.admit(access_token=access(env), packet=packet(), now=NOW)
    assert accepted == {"status": "pending", "duplicate": False, "capture_id": "CAP-001"}
    assert not stage.river_path.exists()
    before = stage.private_progress(access_token=access(env), work_id="GW-001", now=NOW)
    assert before["pending"] == 1 and before["projected"] == 0
    assert before["submitted_input_messages"] == 1 and before["input_messages"] == 0
    assert before["channels"] == {}
    result = stage.drain(now=NOW)
    assert result == {"projected": 1, "blocked": 0}
    after = stage.private_progress(access_token=access(env), work_id="GW-001", now=NOW)
    assert after["projected"] == 1 and after["pending"] == 0
    assert after["channels"]["voice_dictation"] == 1
    assert stage.reconcile()["consistent"]
    assert stage.drain(now=NOW) == {"projected": 0, "blocked": 0}
    assert len(EvidenceJournal(stage.river_path)._records()) == 1


def test_opt_in_audit_is_scoped_and_does_not_publish_raw_token(stage, env):
    provision(env)
    optin(stage, env)
    with __import__("sqlite3").connect(stage.db_path) as db:
        records = db.execute("SELECT action,generation,token_id_hash FROM consent_audit").fetchall()
    assert len(records) == 1
    assert records[0][0:2] == ("OPT_IN", 1)
    assert records[0][2] != "JTI-01" and len(records[0][2]) == 64


def test_withdraw_blocks_queued_work_and_future_intake(stage, env):
    provision(env)
    optin(stage, env)
    stage.admit(access_token=access(env), packet=packet(), now=NOW)
    result = stage.withdraw(access_token=access(env), work_id="GW-001", now=NOW)
    assert result["status"] == "withdrawn" and result["generation"] == 2
    assert stage.drain(now=NOW) == {"projected": 0, "blocked": 0}
    after = stage.private_progress(access_token=access(env), work_id="GW-001", now=NOW)
    assert after["blocked"] == 1
    assert after["input_messages"] == 0 and after["submitted_input_messages"] == 1
    assert after["channels"] == {}
    assert not stage.river_path.exists()
    with pytest.raises(AdmissionDenied, match="R05_SUBJECT_CONSENT_REQUIRED"):
        stage.admit(access_token=access(env), packet=packet(message="MSG-2", capture="CAP-2"), now=NOW)


def test_reconsent_cannot_resurrect_old_blocked_capture(stage, env):
    provision(env)
    optin(stage, env)
    stage.admit(access_token=access(env), packet=packet(), now=NOW)
    stage.withdraw(access_token=access(env), work_id="GW-001", now=NOW)
    new = optin(stage, env)
    assert new["generation"] == 3
    assert stage.drain(now=NOW) == {"projected": 0, "blocked": 0}
    retry = stage.admit(access_token=access(env), packet=packet(), now=NOW)
    assert retry["duplicate"] and retry["status"] == "blocked"
    fresh = stage.admit(access_token=access(env), packet=packet(message="MSG-2", capture="CAP-2"), now=NOW)
    assert fresh["status"] == "pending"
    assert stage.drain(now=NOW) == {"projected": 1, "blocked": 0}


def test_queue_fails_closed_if_warden_grant_revoked_before_drain(stage, env):
    _, grant = provision(env)
    optin(stage, env)
    stage.admit(access_token=access(env), packet=packet(), now=NOW)
    env["store"].revoke_grant(administrator(), grant.consent_id)
    assert stage.drain(now=NOW) == {"projected": 0, "blocked": 1}
    assert not stage.river_path.exists()


def test_duplicate_and_changed_capture_id_denial(stage, env):
    provision(env)
    optin(stage, env)
    a = stage.admit(access_token=access(env), packet=packet(), now=NOW)
    b = stage.admit(access_token=access(env), packet=packet(), now=NOW)
    assert a["status"] == b["status"] == "pending" and b["duplicate"]
    changed = packet(message="MSG-2")
    with pytest.raises(AdmissionDenied, match="R05_CAPTURE_ID_CONFLICT"):
        stage.admit(access_token=access(env), packet=changed, now=NOW)


def test_invalid_signed_packet_not_queued(stage, env):
    provision(env)
    optin(stage, env)
    bad = packet()
    bad["signature"] = "f" * 64
    with pytest.raises(AdmissionDenied, match="R05_CAPTURE_INVALID"):
        stage.admit(access_token=access(env), packet=bad, now=NOW)
    with __import__("sqlite3").connect(stage.db_path) as db:
        assert db.execute("SELECT count(*) FROM capture_outbox").fetchone()[0] == 0


def test_historical_export_channel_rejected_in_live_intake(stage, env):
    provision(env)
    optin(stage, env)
    from genesis_control_plane.work_capture import sign_packet
    bad = packet()
    bad["payload"] = {**bad["payload"], "channel": "import_unknown", "provenance": "unknown"}
    bad = sign_packet({k: v for k,v in bad.items() if k != "signature"}, SOURCE_KEY)
    with pytest.raises(AdmissionDenied, match="WARDEN_SOURCE_CHANNEL_DENIED"):
        stage.admit(access_token=access(env), packet=bad, now=NOW)


def test_other_tenant_or_principal_cannot_read_receipts(stage, env):
    provision(env)
    optin(stage, env)
    stage.admit(access_token=access(env), packet=packet(), now=NOW)
    stage.drain(now=NOW)
    for token in [access(env, tenant="BNR-T2", jti="JTI-T2"),
                  access(env, sub="DM-002", jti="JTI-M2")]:
        stats = stage.private_progress(access_token=token, work_id="GW-001", now=NOW)
        assert stats["accepted"] == 0 and stats["projected"] == 0
    own = stage.private_progress(access_token=access(env), work_id="GW-001", now=NOW)
    assert own["accepted"] == 1


def test_read_and_capture_permissions_are_independent(stage, env):
    provision(env)
    optin(stage, env)
    with pytest.raises(ValueError, match="IDENTITY_SCOPE_DENIED"):
        stage.private_progress(access_token=access(env, scopes="work:capture"),
                               work_id="GW-001", now=NOW)
    with pytest.raises(ValueError, match="IDENTITY_SCOPE_DENIED"):
        stage.admit(access_token=access(env, scopes="work:read"), packet=packet(), now=NOW)
    with pytest.raises(ValueError, match="IDENTITY_SCOPE_DENIED"):
        stage.withdraw(access_token=access(env, scopes="work:capture"),
                       work_id="GW-001", now=NOW)


def test_river_crash_after_append_is_recovered_idempotently(stage, env):
    provision(env)
    optin(stage, env)
    p = packet()
    stage.admit(access_token=access(env), packet=p, now=NOW)
    # Simulate crash after append, before outbox acknowledgement.
    append_work_event(EvidenceJournal(stage.river_path), kind=p["kind"], payload=p["payload"],
                      station_id=p["station_id"], principal_id=p["principal_id"],
                      session_id=p["session_id"], correlation_id=p["correlation_id"],
                      source=p["source"], classification="private")
    assert not stage.reconcile()["consistent"]
    assert stage.drain(now=NOW) == {"projected": 1, "blocked": 0}
    assert len(EvidenceJournal(stage.river_path)._records()) == 1
    assert stage.reconcile()["consistent"]


def test_tampered_river_prevents_projection(stage, env):
    provision(env)
    optin(stage, env)
    stage.admit(access_token=access(env), packet=packet(), now=NOW)
    stage.drain(now=NOW)
    stage.admit(access_token=access(env), packet=packet(message="MSG-2", capture="CAP-2"), now=NOW)
    stage.river_path.write_text(stage.river_path.read_text().replace("voice_dictation", "typed"))
    with pytest.raises(AdmissionDenied, match="R05_RIVER_CHAIN_INVALID"):
        stage.drain(now=NOW)


def test_r05_purpose_and_consent_duration_denied(stage, env):
    with pytest.raises(AdmissionDenied, match="R05_PURPOSE_DENIED"):
        stage.opt_in(access_token=access(env), work_id="GW-001",
                     expires_at=NOW+timedelta(days=1), purpose="surveillance", now=NOW)
    with pytest.raises(AdmissionDenied, match="R05_CONSENT_DURATION_DENIED"):
        stage.opt_in(access_token=access(env), work_id="GW-001",
                     expires_at=NOW+timedelta(days=31), now=NOW)


def test_projected_private_counts_fail_closed_on_river_tamper(stage, env):
    provision(env)
    optin(stage, env)
    stage.admit(access_token=access(env), packet=packet(), now=NOW)
    assert stage.drain(now=NOW)["projected"] == 1
    stage.river_path.write_text(stage.river_path.read_text().replace("voice_dictation", "typed"))
    with pytest.raises(AdmissionDenied, match="R05_RIVER_CHAIN_INVALID"):
        stage.private_progress(access_token=access(env), work_id="GW-001", now=NOW)
