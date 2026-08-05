from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Protocol

from .capabilities import CapabilityVerifier
from .errors import EdgeNodeError
from .models import (
    CommandLease,
    CompleteCommandRequest,
    CompletionStatus,
    EdgeCommand,
    EdgeNodeStatus,
    HeartbeatReceipt,
    HeartbeatRequest,
    LeaseCommandRequest,
    SpoolFlushReceipt,
    SpoolFlushRequest,
)
from .signatures import SecretResolver, sign_heartbeat, sign_spool_batch
from .spool import SQLiteEventSpool
from .supervisor import SupervisorAdapter


class EdgeControllerClient(Protocol):
    def heartbeat(self, node_id: str, request: HeartbeatRequest) -> HeartbeatReceipt: ...
    def lease_command(self, node_id: str, request: LeaseCommandRequest) -> CommandLease | None: ...
    def complete_command(
        self,
        node_id: str,
        command_id: str,
        request: CompleteCommandRequest,
    ) -> EdgeCommand: ...
    def ingest_spool(self, node_id: str, request: SpoolFlushRequest) -> SpoolFlushReceipt: ...


class GenesisEdgeAgent:
    def __init__(
        self,
        *,
        node_id: str,
        agent_id: str,
        credential_reference: str,
        attestation_reference: str,
        agent_version: str,
        controller: EdgeControllerClient,
        capability_verifier: CapabilityVerifier,
        secret_resolver: SecretResolver,
        supervisor: SupervisorAdapter,
        spool: SQLiteEventSpool,
    ) -> None:
        self.node_id = node_id
        self.agent_id = agent_id
        self.credential_reference = credential_reference
        self.attestation_reference = attestation_reference
        self.agent_version = agent_version
        self.controller = controller
        self.capability_verifier = capability_verifier
        self.secret_resolver = secret_resolver
        self.supervisor = supervisor
        self.spool = spool

    def send_heartbeat(
        self,
        *,
        node_state: EdgeNodeStatus = EdgeNodeStatus.ACTIVE,
        metrics: dict[str, float] | None = None,
        sent_at: datetime | None = None,
    ) -> HeartbeatReceipt:
        at = sent_at or datetime.now(timezone.utc)
        snapshot = self.supervisor.snapshot()
        digest = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        provisional = HeartbeatRequest(
            sequence=self.spool.next_heartbeat_sequence(),
            sent_at=at,
            agent_version=self.agent_version,
            attestation_reference=self.attestation_reference,
            runtime_digest=digest,
            node_state=node_state,
            metrics=metrics or {},
            signature="0" * 64,
        )
        secret = self.secret_resolver.resolve(self.credential_reference)
        request = provisional.model_copy(
            update={"signature": sign_heartbeat(secret, self.node_id, provisional)}
        )
        receipt = self.controller.heartbeat(self.node_id, request)
        self.spool.append(
            event_type="EDGE_AGENT_HEARTBEAT_CONFIRMED",
            actor_id=self.agent_id,
            payload={"sequence": request.sequence, "evidence_event_id": receipt.evidence_event_id},
            occurred_at=at,
        )
        return receipt

    def run_once(self, *, lease_seconds: int = 60) -> EdgeCommand | None:
        lease = self.controller.lease_command(
            self.node_id,
            LeaseCommandRequest(agent_id=self.agent_id, lease_seconds=lease_seconds),
        )
        if lease is None:
            return None
        command = lease.command
        self.spool.append(
            event_type="EDGE_AGENT_COMMAND_LEASED",
            actor_id=self.agent_id,
            payload={
                "command_id": command.command_id,
                "command_type": command.command_type.value,
                "attempt": command.attempts,
            },
        )
        try:
            self.capability_verifier.verify(
                capability_id=command.capability_id,
                subject_id=command.issued_by,
                resource_id=self.node_id,
                allowed_action=command.required_capability_action,
                at=datetime.now(timezone.utc),
            )
            result = self.supervisor.execute(command)
            completion = CompleteCommandRequest(
                agent_id=self.agent_id,
                lease_token=lease.lease_token,
                status=CompletionStatus.SUCCEEDED,
                result=result,
            )
        except Exception as exc:
            reason_codes = exc.reason_codes if isinstance(exc, EdgeNodeError) else ["SUPERVISOR_EXECUTION_FAILED"]
            completion = CompleteCommandRequest(
                agent_id=self.agent_id,
                lease_token=lease.lease_token,
                status=CompletionStatus.FAILED,
                result={"error": str(exc), "reason_codes": reason_codes},
            )
        completed = self.controller.complete_command(
            self.node_id,
            command.command_id,
            completion,
        )
        self.spool.append(
            event_type=f"EDGE_AGENT_COMMAND_{completed.status.value}",
            actor_id=self.agent_id,
            payload={
                "command_id": completed.command_id,
                "command_type": completed.command_type.value,
                "result": completed.result or {},
            },
        )
        return completed

    def flush_spool(self, *, limit: int = 100) -> SpoolFlushReceipt | None:
        events = self.spool.pending(limit)
        if not events:
            return None
        secret = self.secret_resolver.resolve(self.credential_reference)
        request = SpoolFlushRequest(
            events=events,
            batch_signature=sign_spool_batch(secret, self.node_id, events),
        )
        receipt = self.controller.ingest_spool(self.node_id, request)
        self.spool.acknowledge(receipt.accepted_event_ids)
        return receipt
