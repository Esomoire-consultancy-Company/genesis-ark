from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Callable

from .capabilities import CapabilityVerifier
from .config import Settings
from .errors import AuthorizationError, NotFoundError, SignatureError, StateConflictError
from .evidence import build_evidence_event, utc_now
from .models import (
    CommandLease,
    CommandStatus,
    CommandType,
    CompleteCommandRequest,
    EdgeCommand,
    EdgeEvidenceEvent,
    EdgeNodeIdentity,
    EdgeNodeStatus,
    EnrollNodeRequest,
    HeartbeatReceipt,
    HeartbeatRequest,
    IssueCommandRequest,
    LeaseCommandRequest,
    SpoolFlushReceipt,
    SpoolFlushRequest,
)
from .repository import EdgeNodeRepository
from .signatures import SecretResolver, spool_event_hash, verify_heartbeat, verify_spool_batch

COMMAND_ACTIONS: dict[CommandType, str] = {
    CommandType.START_INSTANCE: "EDGE_START_INSTANCE",
    CommandType.STOP_INSTANCE: "EDGE_STOP_INSTANCE",
    CommandType.PAUSE_SESSION: "EDGE_PAUSE_SESSION",
    CommandType.TERMINATE_SESSION: "EDGE_TERMINATE_SESSION",
    CommandType.EXECUTE_RECOVERY: "RUNTIME_RECOVERY_EXECUTE",
    CommandType.ROTATE_AGENT: "EDGE_ROTATE_AGENT",
    CommandType.DRAIN_NODE: "EDGE_DRAIN_NODE",
}


class EdgeNodeEngine:
    def __init__(
        self,
        repository: EdgeNodeRepository,
        capability_verifier: CapabilityVerifier,
        secret_resolver: SecretResolver,
        settings: Settings,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.repository = repository
        self.capability_verifier = capability_verifier
        self.secret_resolver = secret_resolver
        self.settings = settings
        self.clock = clock

    def _identity(self, node_id: str) -> EdgeNodeIdentity:
        identity = self.repository.get_identity(node_id)
        if identity is None:
            raise NotFoundError(
                "Edge Node is not enrolled",
                reason_codes=["EDGE_NODE_NOT_ENROLLED"],
            )
        return identity

    def _append_event(
        self,
        *,
        node_id: str,
        event_type: str,
        actor_id: str,
        payload: dict[str, object],
        at: datetime,
    ) -> EdgeEvidenceEvent:
        latest = self.repository.latest_event(node_id)
        event = build_evidence_event(
            node_id=node_id,
            event_type=event_type,
            actor_id=actor_id,
            payload=payload,
            occurred_at=at,
            previous_event_hash=latest.evidence_hash if latest else None,
        )
        return self.repository.append_event(event)

    def enroll(self, request: EnrollNodeRequest) -> EdgeNodeIdentity:
        at = self.clock()
        token_hash = hashlib.sha256(request.bootstrap_token.encode("utf-8")).hexdigest()
        with self.repository.transaction(request.node_id):
            if self.repository.get_identity(request.node_id) is not None:
                raise StateConflictError(
                    "Edge Node is already enrolled",
                    reason_codes=["EDGE_NODE_ALREADY_ENROLLED"],
                )
            self.repository.consume_bootstrap_token(request.node_id, token_hash, at)
            identity = EdgeNodeIdentity(
                node_id=request.node_id,
                device_id=request.device_id,
                agent_id=request.agent_id,
                hardware_fingerprint=request.hardware_fingerprint,
                agent_version=request.agent_version,
                credential_reference=request.credential_reference,
                attestation_reference=request.attestation_reference,
                status=EdgeNodeStatus.ENROLLED,
                last_heartbeat_sequence=0,
                last_spool_sequence=0,
                last_spool_hash=None,
                last_seen_at=None,
                enrolled_at=at,
                updated_at=at,
            )
            self.repository.save_identity(identity)
            self._append_event(
                node_id=request.node_id,
                event_type="EDGE_NODE_ENROLLED",
                actor_id=request.agent_id,
                payload={
                    "device_id": request.device_id,
                    "hardware_fingerprint": request.hardware_fingerprint,
                    "agent_version": request.agent_version,
                    "credential_reference": request.credential_reference,
                    "attestation_reference": request.attestation_reference,
                },
                at=at,
            )
            return identity

    def heartbeat(self, node_id: str, request: HeartbeatRequest) -> HeartbeatReceipt:
        at = self.clock()
        with self.repository.transaction(node_id):
            identity = self._identity(node_id)
            if identity.status == EdgeNodeStatus.RETIRED:
                raise StateConflictError(
                    "Retired Edge Nodes cannot send heartbeats",
                    reason_codes=["EDGE_NODE_RETIRED"],
                )
            if request.sequence <= identity.last_heartbeat_sequence:
                raise StateConflictError(
                    "Heartbeat sequence was replayed or is out of order",
                    reason_codes=["HEARTBEAT_REPLAYED"],
                )
            skew = abs((at - request.sent_at.astimezone(timezone.utc)).total_seconds())
            if skew > self.settings.heartbeat_max_clock_skew_seconds:
                raise StateConflictError(
                    "Heartbeat timestamp is outside the accepted clock-skew window",
                    reason_codes=["HEARTBEAT_STALE"],
                )
            if request.attestation_reference != identity.attestation_reference:
                raise SignatureError(
                    "Heartbeat attestation reference does not match enrollment",
                    reason_codes=["ATTESTATION_REFERENCE_MISMATCH"],
                )
            try:
                secret = self.secret_resolver.resolve(identity.credential_reference)
            except KeyError as exc:
                raise SignatureError(
                    "Node credential reference could not be resolved",
                    reason_codes=["NODE_CREDENTIAL_UNAVAILABLE"],
                ) from exc
            if not verify_heartbeat(secret, node_id, request):
                raise SignatureError(
                    "Heartbeat signature is invalid",
                    reason_codes=["HEARTBEAT_SIGNATURE_INVALID"],
                )
            if identity.status in {
                EdgeNodeStatus.QUARANTINED,
                EdgeNodeStatus.DRAINING,
            }:
                next_status = identity.status
            elif request.node_state in {EdgeNodeStatus.ACTIVE, EdgeNodeStatus.DEGRADED}:
                next_status = request.node_state
            else:
                next_status = EdgeNodeStatus.DEGRADED
            updated = identity.model_copy(
                update={
                    "agent_version": request.agent_version,
                    "status": next_status,
                    "last_heartbeat_sequence": request.sequence,
                    "last_seen_at": at,
                    "updated_at": at,
                }
            )
            self.repository.save_heartbeat(node_id, request, at)
            self.repository.save_identity(updated)
            event = self._append_event(
                node_id=node_id,
                event_type="EDGE_NODE_HEARTBEAT_ACCEPTED",
                actor_id=identity.agent_id,
                payload={
                    "sequence": request.sequence,
                    "runtime_digest": request.runtime_digest,
                    "node_state": next_status.value,
                    "metrics": request.metrics,
                },
                at=at,
            )
            return HeartbeatReceipt(
                node_id=node_id,
                sequence=request.sequence,
                accepted_at=at,
                node_status=next_status,
                evidence_event_id=event.event_id,
            )

    def issue_command(self, node_id: str, request: IssueCommandRequest) -> EdgeCommand:
        at = self.clock()
        if request.expires_at <= at:
            raise StateConflictError(
                "Command expiry must be in the future",
                reason_codes=["COMMAND_ALREADY_EXPIRED"],
            )
        if request.expires_at > at + timedelta(hours=24):
            raise StateConflictError(
                "Command expiry cannot exceed 24 hours",
                reason_codes=["COMMAND_EXPIRY_TOO_LONG"],
            )
        required_action = COMMAND_ACTIONS[request.command_type]
        with self.repository.transaction(node_id):
            identity = self._identity(node_id)
            if identity.status == EdgeNodeStatus.RETIRED:
                raise StateConflictError(
                    "Commands cannot be issued to a retired Edge Node",
                    reason_codes=["EDGE_NODE_RETIRED"],
                )
            self.capability_verifier.verify(
                capability_id=request.capability_id,
                subject_id=request.issued_by,
                resource_id=node_id,
                allowed_action=required_action,
                at=at,
            )
            command = EdgeCommand(
                command_id=request.command_id,
                node_id=node_id,
                command_type=request.command_type,
                capability_id=request.capability_id,
                required_capability_action=required_action,
                issued_by=request.issued_by,
                target_reference=request.target_reference,
                payload=request.payload,
                status=CommandStatus.PENDING,
                attempts=0,
                issued_at=at,
                expires_at=request.expires_at,
                updated_at=at,
            )
            self.repository.save_command(command)
            self._append_event(
                node_id=node_id,
                event_type="EDGE_COMMAND_ISSUED",
                actor_id=request.issued_by,
                payload={
                    "command_id": command.command_id,
                    "command_type": command.command_type.value,
                    "target_reference": command.target_reference,
                    "capability_id": command.capability_id,
                    "required_capability_action": required_action,
                    "expires_at": command.expires_at.isoformat(),
                },
                at=at,
            )
            return command

    def lease_command(self, node_id: str, request: LeaseCommandRequest) -> CommandLease | None:
        at = self.clock()
        lease_seconds = request.lease_seconds or self.settings.default_command_lease_seconds
        if lease_seconds > self.settings.max_command_lease_seconds:
            raise StateConflictError(
                "Requested command lease exceeds service maximum",
                reason_codes=["COMMAND_LEASE_TOO_LONG"],
            )
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        with self.repository.transaction(node_id):
            identity = self._identity(node_id)
            if request.agent_id != identity.agent_id:
                raise AuthorizationError(
                    "Only the enrolled Edge Agent may lease node commands",
                    reason_codes=["EDGE_AGENT_ID_MISMATCH"],
                )
            if identity.status in {EdgeNodeStatus.QUARANTINED, EdgeNodeStatus.RETIRED}:
                raise StateConflictError(
                    "This Edge Node cannot lease commands in its current state",
                    reason_codes=["EDGE_NODE_COMMANDS_BLOCKED"],
                )
            command = self.repository.lease_next_command(
                node_id=node_id,
                agent_id=request.agent_id,
                at=at,
                lease_seconds=lease_seconds,
                lease_token_hash=token_hash,
                max_attempts=self.settings.max_command_attempts,
            )
            if command is None:
                return None
            self._append_event(
                node_id=node_id,
                event_type="EDGE_COMMAND_LEASED",
                actor_id=request.agent_id,
                payload={
                    "command_id": command.command_id,
                    "attempt": command.attempts,
                    "lease_expires_at": command.lease_expires_at.isoformat()
                    if command.lease_expires_at
                    else None,
                },
                at=at,
            )
            return CommandLease(command=command, lease_token=raw_token)

    def complete_command(
        self,
        node_id: str,
        command_id: str,
        request: CompleteCommandRequest,
    ) -> EdgeCommand:
        at = self.clock()
        token_hash = hashlib.sha256(request.lease_token.encode("utf-8")).hexdigest()
        with self.repository.transaction(node_id):
            identity = self._identity(node_id)
            if request.agent_id != identity.agent_id:
                raise AuthorizationError(
                    "Only the enrolled Edge Agent may complete node commands",
                    reason_codes=["EDGE_AGENT_ID_MISMATCH"],
                )
            command = self.repository.complete_command(
                node_id=node_id,
                command_id=command_id,
                agent_id=request.agent_id,
                lease_token_hash=token_hash,
                status=request.status,
                result=request.result,
                at=at,
            )
            self._append_event(
                node_id=node_id,
                event_type=f"EDGE_COMMAND_{command.status.value}",
                actor_id=request.agent_id,
                payload={
                    "command_id": command.command_id,
                    "command_type": command.command_type.value,
                    "target_reference": command.target_reference,
                    "result": command.result or {},
                },
                at=at,
            )
            return command

    def ingest_spool(self, node_id: str, request: SpoolFlushRequest) -> SpoolFlushReceipt:
        at = self.clock()
        with self.repository.transaction(node_id):
            identity = self._identity(node_id)
            try:
                secret = self.secret_resolver.resolve(identity.credential_reference)
            except KeyError as exc:
                raise SignatureError(
                    "Node credential reference could not be resolved",
                    reason_codes=["NODE_CREDENTIAL_UNAVAILABLE"],
                ) from exc
            if not verify_spool_batch(
                secret,
                node_id,
                request.events,
                request.batch_signature,
            ):
                raise SignatureError(
                    "Spool batch signature is invalid",
                    reason_codes=["SPOOL_BATCH_SIGNATURE_INVALID"],
                )
            current = identity
            accepted: list[str] = []
            for item in request.events:
                if spool_event_hash(item) != item.local_hash:
                    raise SignatureError(
                        "Spool event hash is invalid",
                        reason_codes=["SPOOL_EVENT_HASH_INVALID"],
                    )
                is_new = self.repository.ingest_spool_event(node_id, item, at)
                if is_new:
                    expected_sequence = current.last_spool_sequence + 1
                    if item.sequence != expected_sequence:
                        raise StateConflictError(
                            "Spool event sequence does not continue the accepted stream",
                            reason_codes=["SPOOL_SEQUENCE_GAP"],
                        )
                    if item.previous_local_hash != current.last_spool_hash:
                        raise StateConflictError(
                            "Spool event hash does not continue the accepted stream",
                            reason_codes=["SPOOL_HASH_CHAIN_CONFLICT"],
                        )
                    current = current.model_copy(
                        update={
                            "last_spool_sequence": item.sequence,
                            "last_spool_hash": item.local_hash,
                            "updated_at": at,
                        }
                    )
                    self._append_event(
                        node_id=node_id,
                        event_type="EDGE_NODE_SPOOL_EVENT_INGESTED",
                        actor_id=item.actor_id,
                        payload={
                            "spool_event_id": item.event_id,
                            "spool_sequence": item.sequence,
                            "spool_event_type": item.event_type,
                            "local_hash": item.local_hash,
                            "payload": item.payload,
                        },
                        at=at,
                    )
                accepted.append(item.event_id)
            self.repository.save_identity(current)
            return SpoolFlushReceipt(
                node_id=node_id,
                accepted_event_ids=accepted,
                last_sequence=current.last_spool_sequence,
                accepted_at=at,
            )

    def get_identity(self, node_id: str) -> EdgeNodeIdentity:
        return self._identity(node_id)

    def list_events(self, node_id: str) -> list[EdgeEvidenceEvent]:
        self._identity(node_id)
        return self.repository.list_events(node_id)
