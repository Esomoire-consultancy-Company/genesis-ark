"""Private, synthetic-first operator case routing contract R0.1.

Not an authentication provider, secret store, HTTP service, live Railway
collector, Synnergyze dispatcher, or canonical RiverOS ledger. Event sources
must already be trusted by the private adapter; authorization context must
come from a verified Warden/SSO system, never a request parameter.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from html import escape
from typing import Literal

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SECRET = re.compile(r"^[A-Z][A-Z0-9_]{1,127}$")

EventKind = Literal["public_intent_probe", "sensitive_path_probe", "intent_denied", "secret_state"]
Status = Literal["new", "acknowledged"]


class AccessDenied(PermissionError):
    pass


class InvalidEvent(ValueError):
    pass


@dataclass(frozen=True)
class VerifiedOperator:
    """Server-verified grants. Offline fixtures only until a signed-claims adapter exists."""

    actor_id: str
    roles: frozenset[str]
    node_ids: frozenset[str]
    # This flag is set only by the trusted auth adapter, NEVER from HTTP input.
    authority_verified: bool = False
    environments: frozenset[str] = frozenset()


@dataclass(frozen=True)
class SecurityEvent:
    event_id: str
    kind: EventKind
    environment: str
    node_id: str | None
    correlation_id: str | None
    source_receipt: str
    # For registry events, this is a *name/reference*, never secret material.
    secret_name: str | None = None
    secret_state: str | None = None


@dataclass(frozen=True)
class Case:
    case_id: str
    event: SecurityEvent
    queue_role: str
    severity: str
    status: Status
    evidence_hash: str
    assignee_id: str | None = None
    intended_recipient_id: str | None = None
    handoff_receipt: str | None = None
    ack_receipt: str | None = None


def _valid_id(value: str | None) -> bool:
    return isinstance(value, str) and bool(_ID.fullmatch(value))


def _canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: dict) -> str:
    return hashlib.sha256(_canonical(value).encode("ascii")).hexdigest()


def _validate(event: SecurityEvent) -> None:
    if not all(_valid_id(value) for value in (event.event_id, event.environment, event.source_receipt)):
        raise InvalidEvent("INVALID_EVENT_IDENTITY")
    if event.node_id is not None and not _valid_id(event.node_id):
        raise InvalidEvent("INVALID_NODE")
    if event.correlation_id is not None and not _valid_id(event.correlation_id):
        raise InvalidEvent("INVALID_CORRELATION")
    if event.kind not in {"public_intent_probe", "sensitive_path_probe", "intent_denied", "secret_state"}:
        raise InvalidEvent("INVALID_KIND")
    if event.kind == "secret_state":
        if not event.secret_name or not _SECRET.fullmatch(event.secret_name):
            raise InvalidEvent("INVALID_SECRET_REFERENCE")
        if event.secret_state not in {"missing", "rotation_due", "revoked"}:
            raise InvalidEvent("INVALID_SECRET_STATE")
    elif event.secret_name is not None or event.secret_state is not None:
        raise InvalidEvent("SECRET_METADATA_NOT_ALLOWED")
    if event.kind == "intent_denied" and (not event.node_id or not event.correlation_id):
        raise InvalidEvent("INTENT_REQUIRES_NODE_AND_CORRELATION")
    if event.kind in {"public_intent_probe", "sensitive_path_probe"} and event.node_id is not None:
        raise InvalidEvent("UNAUTHENTICATED_PROBE_CANNOT_CLAIM_NODE")


def classify_public_denial(*, event_id: str, path: str, status: int,
                           source_receipt: str, environment: str = "staging") -> SecurityEvent | None:
    """Trusted Railway-log adapter calls this on allowlisted metadata only.

    Never accept arbitrary path, query string, request headers, body, IP, or
    actor hints for a case. Query strings are not stored or reflected.
    """
    if status != 404:
        return None
    route = path.partition("?")[0]
    if route not in {"/v1/intents", "/secrets", "/.env"}:
        return None
    event = SecurityEvent(event_id, "public_intent_probe" if route == "/v1/intents" else "sensitive_path_probe",
                          environment, None, None, source_receipt)
    _validate(event)
    return event


def record_gateway_denial(*, event_id: str, trusted_node_id: str,
                          trusted_correlation_id: str, evidence_hash: str,
                          environment: str = "staging") -> SecurityEvent:
    """Pass only server-validated ledger receipt + authenticated registry mapping."""
    if not re.fullmatch(r"[0-9a-f]{64}", evidence_hash):
        raise InvalidEvent("INVALID_LEDGER_HASH")
    event = SecurityEvent(event_id, "intent_denied", environment, trusted_node_id,
                          trusted_correlation_id, evidence_hash)
    _validate(event)
    return event


def record_secret_status(*, event_id: str, secret_reference: str,
                         state: str, registry_receipt_id: str,
                         environment: str = "staging") -> SecurityEvent:
    """Accept registry metadata only, never read os.environ or secret values."""
    event = SecurityEvent(event_id, "secret_state", environment, None, None,
                          registry_receipt_id, secret_reference, state)
    _validate(event)
    return event


def _route(event: SecurityEvent) -> tuple[str, str]:
    return {
        "public_intent_probe": ("security_custodian", "info"),
        "sensitive_path_probe": ("security_custodian", "warning"),
        "intent_denied": ("node_operator", "review"),
        "secret_state": ("configuration_custodian", "warning"),
    }[event.kind]


def _authorized(operator: VerifiedOperator, case: Case) -> bool:
    if not operator.authority_verified or not _valid_id(operator.actor_id):
        return False
    if case.queue_role not in operator.roles or case.event.environment not in operator.environments:
        return False
    return case.event.node_id is None or case.event.node_id in operator.node_ids


class SyntheticCaseQueue:
    """In-memory demonstration only. Never back a live dashboard with this."""

    def __init__(self):
        self._cases: dict[str, Case] = {}

    def ingest(self, event: SecurityEvent) -> Case:
        _validate(event)
        queue_role, severity = _route(event)
        event_details = {field: getattr(event, field) for field in event.__dataclass_fields__}
        evidence = _digest({"event": event_details, "queue_role": queue_role, "severity": severity})
        case_id = "CASE-" + hashlib.sha256(f"{event.environment}:{event.event_id}".encode("ascii")).hexdigest()[:20]
        prior = self._cases.get(case_id)
        if prior:
            if prior.evidence_hash != evidence:
                raise InvalidEvent("EVENT_ID_CONFLICT")
            return prior
        case = Case(case_id, event, queue_role, severity, "new", evidence)
        self._cases[case_id] = case
        return case

    def visible_cases(self, operator: VerifiedOperator) -> tuple[Case, ...]:
        return tuple(c for c in self._cases.values() if _authorized(operator, c))

    def prepare_handoff(self, case_id: str, *, verified_on_duty: tuple[VerifiedOperator, ...]) -> Case:
        """Resolve one authorized recipient; record intent only, never send alerts.

        Production dispatch needs a signed duty roster, authenticated private
        delivery channel, durable outbox/retries and RiverOS witnessing.
        Ambiguous or unassigned roles stay within the restricted work queue.
        """
        case = self._cases.get(case_id)
        if case is None:
            raise AccessDenied("CASE_NOT_FOUND")
        if case.intended_recipient_id is not None:
            return case
        recipients = {actor.actor_id for actor in verified_on_duty
                      if _authorized(actor, case)}
        if len(recipients) != 1:
            return case  # No routing on ambiguity or missing authority.
        recipient_id = next(iter(recipients))
        receipt = _digest({"case_id": case.case_id, "action": "prepare_private_handoff",
                           "recipient_id": recipient_id, "prior_evidence": case.evidence_hash})
        updated = replace(case, intended_recipient_id=recipient_id, handoff_receipt=receipt)
        self._cases[case_id] = updated
        return updated

    def acknowledge(self, operator: VerifiedOperator, case_id: str) -> Case:
        case = self._cases.get(case_id)
        if case is None or not _authorized(operator, case):
            raise AccessDenied("WARDEN_ACCESS_DENIED")
        if case.intended_recipient_id is not None and case.intended_recipient_id != operator.actor_id:
            raise AccessDenied("NOT_ASSIGNED_RECIPIENT")
        if case.status == "acknowledged":
            if case.assignee_id != operator.actor_id:
                raise AccessDenied("ALREADY_ASSIGNED")
            return case
        receipt = _digest({"case_id": case.case_id, "action": "acknowledge",
                           "actor_id": operator.actor_id, "prior_evidence": case.evidence_hash})
        updated = replace(case, status="acknowledged", assignee_id=operator.actor_id,
                          ack_receipt=receipt)
        self._cases[case_id] = updated
        return updated


def render_private_preview(queue: SyntheticCaseQueue, operator: VerifiedOperator) -> str:
    """Offline HTML preview. NOT a live operator endpoint or authentication UI."""
    rows = []
    for case in queue.visible_cases(operator):
        event = case.event
        summary = {
            "public_intent_probe": "Public intent endpoint probe",
            "sensitive_path_probe": "Protected-path access probe",
            "intent_denied": "Authenticated intent denied",
            "secret_state": "Secret metadata needs custodian review",
        }[event.kind]
        reference = event.secret_name if event.kind == "secret_state" else (event.correlation_id or "-")
        values = (case.case_id, summary, event.environment, event.node_id or "Unassigned",
                  case.queue_role, reference, case.severity, case.status, case.evidence_hash[:16])
        rows.append("<tr>" + "".join("<td>" + escape(str(v)) + "</td>" for v in values) + "</tr>")
    head = ("Case", "Event", "Environment", "Node", "Queue", "Reference", "Severity", "Status", "Receipt")
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<meta name='robots' content='noindex,nofollow'><title>Genesis Operator Inbox - SYNTHETIC</title>"
            "<style>body{font:15px system-ui;background:#0c1520;color:#eef5f8;padding:25px}"
            "h1{font-size:25px}p{color:#c0d2de}table{border-collapse:collapse;min-width:850px}"
            "th,td{padding:12px;text-align:left;border-bottom:1px solid #426071}"
            "th{color:#a9dbc0}main{overflow-x:auto}strong{color:#ffdba8}</style></head><body>"
            "<h1>Genesis ARK | Private Operator Inbox</h1>"
            "<p><strong>SYNTHETIC-ONLY PREVIEW | NOT CONNECTED TO LIVE RAILWAY / WARDEN / RIVEROS</strong></p>"
            "<p>Authenticated roles would govern visibility. No secrets, request bodies, headers, or IP addresses are displayed.</p>"
            "<main><table aria-label='Operator work items'><thead><tr>" +
            "".join("<th>" + escape(h) + "</th>" for h in head) +
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></main></body></html>")
