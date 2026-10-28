"""Offline, synthetic-only security and routing acceptance tests."""
import pytest
from genesis_gateway.operator_inbox import (
    AccessDenied, InvalidEvent, SecurityEvent, SyntheticCaseQueue,
    VerifiedOperator, classify_public_denial, record_gateway_denial,
    record_secret_status, render_private_preview,
)
from genesis_gateway.operator_preview import demo


def user(role, nodes=(), verified=True, name="ACTOR-TEST-1", environments=("staging",)):
    return VerifiedOperator(name, frozenset({role}), frozenset(nodes), authority_verified=verified, environments=frozenset(environments))


def test_only_protected_public_denials_are_classified():
    assert classify_public_denial(event_id="A1", path="/", status=404, source_receipt="R1") is None
    assert classify_public_denial(event_id="A1", path="/.env", status=200, source_receipt="R1") is None
    assert classify_public_denial(event_id="A1", path="/.env.local", status=404, source_receipt="R1") is None
    assert classify_public_denial(event_id="A1", path="/v1/intents", status=404, source_receipt="R1").kind == "public_intent_probe"
    assert classify_public_denial(event_id="A2", path="/.env?password=DO-NOT-STORE", status=404, source_receipt="R2").kind == "sensitive_path_probe"


def test_public_probe_cannot_claim_node_or_identity():
    q = SyntheticCaseQueue()
    event = classify_public_denial(event_id="A1", path="/.env?auth=secret", status=404,
                                   source_receipt="RAILWAY-001")
    case = q.ingest(event)
    assert case.event.node_id is None and case.queue_role == "security_custodian"
    assert "auth=secret" not in repr(case) and "?" not in repr(case)
    with pytest.raises(InvalidEvent):
        q.ingest(SecurityEvent("A2", "sensitive_path_probe", "staging", "CLAIMED-NODE", None, "R2"))


def test_strict_routing_and_node_scope():
    q = demo()
    assert len(q.visible_cases(user("security_custodian"))) == 2
    assert len(q.visible_cases(user("configuration_custodian"))) == 1
    assert len(q.visible_cases(user("node_operator", ("NODE-DEMO-01",)))) == 1
    assert len(q.visible_cases(user("node_operator", ("NODE-OTHER",)))) == 0
    assert q.visible_cases(user("security_custodian", verified=False)) == ()
    assert q.visible_cases(user("auditor")) == ()
    assert q.visible_cases(user("security_custodian", environments=("production",))) == ()


def test_untrusted_operator_cannot_acknowledge_or_read_case():
    q = demo()
    case = q.visible_cases(user("configuration_custodian"))[0]
    for actor in (user("security_custodian"), user("configuration_custodian", verified=False)):
        with pytest.raises(AccessDenied):
            q.acknowledge(actor, case.case_id)
    ok = q.acknowledge(user("configuration_custodian"), case.case_id)
    assert ok.status == "acknowledged" and len(ok.ack_receipt) == 64
    assert q.acknowledge(user("configuration_custodian"), case.case_id) == ok
    with pytest.raises(AccessDenied):
        q.acknowledge(user("configuration_custodian", name="ANOTHER-ACTOR"), case.case_id)


def test_handoff_only_one_registry_verified_recipient_and_no_delivery_claim():
    q = demo()
    case = q.visible_cases(user("node_operator", ("NODE-DEMO-01",)))[0]
    target = user("node_operator", ("NODE-DEMO-01",), name="NODE-OPERATOR-01")
    wrong = user("node_operator", ("OTHER-NODE",), name="OTHER-OPERATOR")
    unverified = user("node_operator", ("NODE-DEMO-01",), verified=False)
    assert q.prepare_handoff(case.case_id, verified_on_duty=(wrong, unverified)).intended_recipient_id is None
    also_target = user("node_operator", ("NODE-DEMO-01",), name="NODE-OPERATOR-02")
    assert q.prepare_handoff(case.case_id, verified_on_duty=(target, also_target)).intended_recipient_id is None
    planned = q.prepare_handoff(case.case_id, verified_on_duty=(target, wrong))
    assert planned.intended_recipient_id == "NODE-OPERATOR-01"
    assert len(planned.handoff_receipt) == 64 and planned.status == "new"
    with pytest.raises(AccessDenied):
        q.acknowledge(user("node_operator", ("NODE-DEMO-01",), name="NODE-OPERATOR-02"), case.case_id)
    assert q.acknowledge(target, case.case_id).assignee_id == "NODE-OPERATOR-01"


def test_idempotent_and_conflicting_events():
    q = SyntheticCaseQueue()
    first = record_secret_status(event_id="EV-01", secret_reference="SERVICE_PASSWORD",
                                 state="missing", registry_receipt_id="REG-001")
    assert q.ingest(first) == q.ingest(first)
    with pytest.raises(InvalidEvent, match="EVENT_ID_CONFLICT"):
        q.ingest(record_secret_status(event_id="EV-01", secret_reference="SERVICE_PASSWORD",
                                      state="revoked", registry_receipt_id="REG-001"))


def test_secret_reference_only_and_strict_input():
    with pytest.raises(InvalidEvent):
        record_secret_status(event_id="E1", secret_reference="DATABASE_URL=postgres://user:pass@host",
                             state="missing", registry_receipt_id="R1")
    with pytest.raises(InvalidEvent):
        record_secret_status(event_id="E1", secret_reference="SOME_KEY",
                             state="raw-secret-text", registry_receipt_id="R1")
    with pytest.raises(InvalidEvent):
        record_gateway_denial(event_id="E1", trusted_node_id="NODE-1", trusted_correlation_id="COR-1",
                              evidence_hash="not-a-valid-evidence-hash")


def test_preview_is_role_filtered_and_synthetic_marked():
    q = demo()
    html = render_private_preview(q, user("node_operator", ("NODE-DEMO-01",)))
    assert "SYNTHETIC-ONLY" in html
    assert "Authenticated intent denied" in html
    assert "Secret metadata needs custodian review" not in html
    assert "Protected-path access probe" not in html
    html2 = render_private_preview(q, user("configuration_custodian"))
    assert "GENESIS_GATEWAY_API_KEY" in html2
    assert "a" * 64 not in html2


def test_all_outputs_are_ascii_encoding_safe():
    output = render_private_preview(demo(), user("security_custodian"))
    output.encode("ascii")
