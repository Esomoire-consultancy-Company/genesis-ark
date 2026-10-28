"""Secret changes must be requested, independently approved, and checked."""
import pytest
from genesis_gateway.operator_inbox import AccessDenied, InvalidEvent, VerifiedOperator
from genesis_gateway.operator_preview import demo
from genesis_gateway.secret_workflow import SyntheticSecretWorkflow


def actor(name, role, verified=True, environment="staging",
          services=("genesis-cloud-gateway-r01",), nodes=()):
    return VerifiedOperator(name, frozenset({role}), frozenset(nodes), verified,
                            frozenset({environment}), frozenset(services))


def setup():
    q = demo()
    custodian = actor("CUSTODIAN-01", "configuration_custodian")
    case = q.visible_cases(custodian)[0]
    return SyntheticSecretWorkflow(q), case, custodian


def test_three_distinct_actors_request_approve_check():
    workflow, case, custodian = setup()
    item = workflow.request(actor=custodian, case_id=case.case_id, work_id="WORK-01", action="rotate")
    assert item.status == "pending_approval"
    assert item.secret_name == "GENESIS_GATEWAY_API_KEY"
    approver = actor("APPROVER-01", "secret_change_approver")
    approved = workflow.approve(approver=approver, work_id="WORK-01")
    assert approved.status == "approved_for_vault_work"
    assert len(approved.approval_receipt) == 64
    checked = workflow.synthetic_check(checker=actor("CHECKER-01", "secret_state_verifier"),
                                       work_id="WORK-01", inventory_receipt="VAULT-METADATA-RECEIPT-01")
    assert checked.status == "checked_synthetic_only"
    assert len(checked.check_receipt) == 64
    assert not hasattr(checked, "secret_value")


def test_no_self_approval_or_self_check():
    w, case, custodian = setup()
    w.request(actor=custodian, case_id=case.case_id, work_id="WORK-02", action="rotate")
    self_approver = VerifiedOperator(custodian.actor_id, frozenset({"secret_change_approver"}),
                                     frozenset(), True, frozenset({"staging"}),
                                     frozenset({"genesis-cloud-gateway-r01"}))
    with pytest.raises(AccessDenied, match="DUAL_CONTROL_REQUIRED"):
        w.approve(approver=self_approver, work_id="WORK-02")
    with pytest.raises(AccessDenied):
        w.synthetic_check(checker=actor("CHECKER-01", "secret_state_verifier"),
                          work_id="WORK-02", inventory_receipt="R-01")


def test_wrong_environment_and_unverified_actor_blocked():
    w, case, custodian = setup()
    for caller in (actor("CUSTODIAN-02", "configuration_custodian", environment="production"),
                   actor("CUSTODIAN-03", "configuration_custodian", verified=False)):
        with pytest.raises(AccessDenied):
            w.request(actor=caller, case_id=case.case_id, work_id="WORK-03", action="rotate")
    w.request(actor=custodian, case_id=case.case_id, work_id="WORK-03", action="rotate")
    with pytest.raises(AccessDenied):
        w.approve(approver=actor("APPROVER-02", "secret_change_approver", environment="production"),
                  work_id="WORK-03")
    with pytest.raises(AccessDenied):
        w.approve(approver=actor("APPROVER-03", "secret_change_approver",
                                 services=("genesis-public-site-preview",)), work_id="WORK-03")


def test_reject_arbitrary_secret_payload_and_request_mismatch():
    w, case, custodian = setup()
    with pytest.raises(InvalidEvent):
        w.request(actor=custodian, case_id=case.case_id, work_id="DATABASE_PASSWORD=12345", action="add")
    with pytest.raises(InvalidEvent):
        w.request(actor=custodian, case_id=case.case_id, work_id="WORK-04", action="add")
    item = w.request(actor=custodian, case_id=case.case_id, work_id="WORK-04", action="rotate")
    assert w.request(actor=custodian, case_id=case.case_id, work_id="WORK-04", action="rotate") == item
    with pytest.raises(InvalidEvent):
        w.request(actor=custodian, case_id=case.case_id, work_id="WORK-04", action="add")


def test_node_mapped_vault_work_requires_node_scope_for_all_three_roles():
    from genesis_gateway.operator_inbox import record_secret_status, SyntheticCaseQueue
    q = SyntheticCaseQueue()
    event = record_secret_status(
        event_id="CONFIG-NODE-01", secret_reference="SERVICE_API_KEY",
        state="rotation_due", registry_receipt_id="VAULT-0001",
        trusted_node_id="NODE-SCOPED-01",
    )
    case = q.ingest(event)
    workflow = SyntheticSecretWorkflow(q)
    custodian = actor("CUSTODIAN-10", "configuration_custodian", nodes=("NODE-SCOPED-01",))
    assert workflow.request(actor=custodian, case_id=case.case_id,
                            work_id="WORK-NODE-01", action="rotate").node_id == "NODE-SCOPED-01"
    with pytest.raises(AccessDenied):
        workflow.approve(approver=actor("APPROVER-11", "secret_change_approver"),
                         work_id="WORK-NODE-01")
    workflow.approve(approver=actor("APPROVER-11", "secret_change_approver",
                                   nodes=("NODE-SCOPED-01",)), work_id="WORK-NODE-01")
    with pytest.raises(AccessDenied):
        workflow.synthetic_check(checker=actor("CHECKER-11", "secret_state_verifier"),
                                 work_id="WORK-NODE-01", inventory_receipt="INV-001")
    assert workflow.synthetic_check(
        checker=actor("CHECKER-11", "secret_state_verifier", nodes=("NODE-SCOPED-01",)),
        work_id="WORK-NODE-01", inventory_receipt="INV-001"
    ).status == "checked_synthetic_only"
