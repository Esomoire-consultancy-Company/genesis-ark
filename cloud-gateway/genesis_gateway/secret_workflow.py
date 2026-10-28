"""Synthetic request/approval/check of secret inventory work - never secret values.

There are NO real vault connectors, no write credentials, no real Warden
verification, and no production path in this implementation. Work requests
are generated from authenticated case context, not from arbitrary clients.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from genesis_gateway.operator_inbox import (
    AccessDenied, InvalidEvent, SyntheticCaseQueue, VerifiedOperator,
    _authorized, _digest, _valid_id,
)


@dataclass(frozen=True)
class SecretWork:
    work_id: str
    case_id: str
    secret_name: str
    environment: str
    requester_id: str
    action: str
    status: str
    request_receipt: str
    approver_id: str | None = None
    approval_receipt: str | None = None
    checker_id: str | None = None
    check_receipt: str | None = None


class SyntheticSecretWorkflow:
    """Offline state machine: request -> approved -> synthetic checked.

    Approval is NOT an API permit or vault execution. A human must configure
    real secrets in a separately authenticated secret manager UI.
    """

    def __init__(self, cases: SyntheticCaseQueue):
        self.cases = cases
        self._work: dict[str, SecretWork] = {}

    def request(self, *, actor: VerifiedOperator, case_id: str, work_id: str, action: str) -> SecretWork:
        if not _valid_id(work_id) or action not in ("add", "rotate"):
            raise InvalidEvent("INVALID_WORK_REQUEST")
        case = self.cases._cases.get(case_id)
        if case is None or case.event.kind != "secret_state" or not _authorized(actor, case):
            raise AccessDenied("CUSTODIAN_NOT_AUTHORIZED")
        if action == "add" and case.event.secret_state != "missing":
            raise InvalidEvent("SECRET_NOT_MISSING")
        if action == "rotate" and case.event.secret_state not in ("rotation_due", "revoked"):
            raise InvalidEvent("ROTATION_NOT_REQUIRED")
        existing = self._work.get(work_id)
        if existing:
            if (existing.case_id, existing.action, existing.requester_id) != (case_id, action, actor.actor_id):
                raise InvalidEvent("WORK_ID_CONFLICT")
            return existing
        receipt = _digest({"event": "secret.work.requested", "case": case.evidence_hash,
                           "work_id": work_id, "actor": actor.actor_id, "action": action})
        value = SecretWork(work_id, case_id, case.event.secret_name, case.event.environment,
                           actor.actor_id, action, "pending_approval", receipt)
        self._work[work_id] = value
        return value

    def approve(self, *, approver: VerifiedOperator, work_id: str) -> SecretWork:
        work = self._work.get(work_id)
        if work is None or not approver.authority_verified or not _valid_id(approver.actor_id):
            raise AccessDenied("APPROVAL_DENIED")
        if "secret_change_approver" not in approver.roles or work.environment not in approver.environments:
            raise AccessDenied("APPROVAL_DENIED")
        if approver.actor_id == work.requester_id:
            raise AccessDenied("DUAL_CONTROL_REQUIRED")
        if work.approver_id is not None:
            if work.approver_id != approver.actor_id:
                raise AccessDenied("ALREADY_APPROVED")
            return work
        receipt = _digest({"event": "secret.work.approved", "work": work.request_receipt,
                           "actor": approver.actor_id})
        updated = replace(work, status="approved_for_vault_work", approver_id=approver.actor_id,
                          approval_receipt=receipt)
        self._work[work_id] = updated
        return updated

    def synthetic_check(self, *, checker: VerifiedOperator, work_id: str,
                        inventory_receipt: str) -> SecretWork:
        work = self._work.get(work_id)
        if work is None or work.approval_receipt is None or not _valid_id(inventory_receipt):
            raise AccessDenied("UNVERIFIED_CHANGE")
        if (not checker.authority_verified or "secret_state_verifier" not in checker.roles
                or work.environment not in checker.environments or not _valid_id(checker.actor_id)
                or checker.actor_id in (work.requester_id, work.approver_id)):
            raise AccessDenied("INDEPENDENT_VERIFIER_REQUIRED")
        if work.checker_id is not None:
            if work.checker_id != checker.actor_id:
                raise AccessDenied("ALREADY_CHECKED")
            return work
        receipt = _digest({"event": "secret.work.synthetic_checked", "approved": work.approval_receipt,
                           "inventory_receipt": inventory_receipt, "actor": checker.actor_id})
        updated = replace(work, status="checked_synthetic_only", checker_id=checker.actor_id,
                          check_receipt=receipt)
        self._work[work_id] = updated
        return updated
