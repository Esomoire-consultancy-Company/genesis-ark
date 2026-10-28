"""Secret changes must be requested, independently approved, and checked."""
import pytest
from genesis_gateway.operator_inbox import AccessDenied, InvalidEvent, VerifiedOperator
from genesis_gateway.operator_preview import demo
from genesis_gateway.secret_workflow import SyntheticSecretWorkflow


def actor(name, role, verified=True, environment="staging"):
    return VerifiedOperator(name, frozenset({role}), frozenset(), verified,
                            frozenset({environment}))


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
                                     frozenset(), True, frozenset({"staging"}))
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
