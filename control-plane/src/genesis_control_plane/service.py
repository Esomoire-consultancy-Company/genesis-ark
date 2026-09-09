from __future__ import annotations

import secrets
from dataclasses import asdict, dataclass
from datetime import datetime

from genesis_control_plane.contracts import (
    Command,
    Decision,
    DecisionResult,
    EvidenceEvent,
    ExecutionResult,
    ExecutionState,
    VerificationResult,
)
from genesis_control_plane.docker_adapter import DockerAdapter
from genesis_control_plane.evidence import EvidenceJournal, EvidenceReceipt
from genesis_control_plane.registry import AlphaRegistry
from genesis_control_plane.tokens import TokenIssuer
from genesis_control_plane.verifier import DockerVerifier
from genesis_control_plane.warden import Warden
from genesis_control_plane.weg import WardenExecutionGateway


@dataclass(frozen=True)
class GovernedExecutionOutcome:
    decision: Decision
    token_id: str | None
    execution: ExecutionResult | None
    verification: VerificationResult | None
    evidence_receipts: tuple[EvidenceReceipt, ...]


class GovernedExecutionService:
    def __init__(
        self,
        registry: AlphaRegistry,
        warden: Warden,
        token_issuer: TokenIssuer,
        weg: WardenExecutionGateway,
        adapter: DockerAdapter,
        verifier: DockerVerifier,
        evidence: EvidenceJournal,
    ):
        self._registry = registry
        self._warden = warden
        self._token_issuer = token_issuer
        self._weg = weg
        self._adapter = adapter
        self._verifier = verifier
        self._evidence = evidence

    def _event(
        self,
        command: Command,
        event_type: str,
        source: str,
        subject: str,
        payload: dict,
        now: datetime,
        causation_id: str | None,
    ) -> EvidenceEvent:
        return EvidenceEvent(
            event_id=f"EVT-{secrets.token_hex(8)}",
            event_type=event_type,
            schema_version="1.0",
            occurred_at=now.isoformat(),
            station_id=command.station_id,
            principal_id=command.principal_id,
            session_id=command.session_id,
            source=source,
            subject=subject,
            payload=payload,
            correlation_id=command.correlation_id,
            causation_id=causation_id,
            classification="internal",
        )

    def execute(self, command: Command, now: datetime) -> GovernedExecutionOutcome:
        receipts: list[EvidenceReceipt] = []
        previous_event_id: str | None = None

        def record(event_type: str, source: str, subject: str, payload: dict) -> EvidenceReceipt:
            nonlocal previous_event_id
            event = self._event(
                command,
                event_type,
                source,
                subject,
                payload,
                now,
                previous_event_id,
            )
            receipt = self._evidence.append(event)
            previous_event_id = event.event_id
            receipts.append(receipt)
            return receipt

        record("command.requested", "operator", command.target_resource_id, asdict(command))
        decision = self._warden.evaluate(command, now)
        record("warden.decision.created", "warden", command.command_id, asdict(decision))

        if decision.result is DecisionResult.DENY:
            return GovernedExecutionOutcome(
                decision=decision,
                token_id=None,
                execution=None,
                verification=None,
                evidence_receipts=tuple(receipts),
            )

        token = self._token_issuer.issue(command, decision, now)
        claims = self._token_issuer.decode_and_verify(token, now)
        record("warden.token.issued", "warden", command.command_id, asdict(claims))

        consumed_claims = self._weg.validate_and_consume(token, command, now)
        record(
            "weg.token.consumed",
            "weg",
            command.target_resource_id,
            {"token_id": consumed_claims.token_id, "command_id": command.command_id},
        )

        resource = self._registry.resource(command.target_resource_id)
        try:
            execution = self._adapter.restart(resource, command, now)
        except Exception as exc:
            execution = ExecutionResult(
                execution_id=f"EXEC-{secrets.token_hex(8)}",
                command_id=command.command_id,
                target_resource_id=resource.resource_id,
                state=ExecutionState.FAILED,
                exit_code=-1,
                stdout="",
                stderr=type(exc).__name__,
                started_at=now.isoformat(),
                completed_at=now.isoformat(),
            )
        record(
            "execution.completed" if execution.state is ExecutionState.COMPLETED else "execution.failed",
            "docker-adapter",
            resource.resource_id,
            asdict(execution),
        )

        verification = self._verifier.verify_restart(resource, execution, now)
        record(
            "verification.completed",
            "docker-verifier",
            resource.resource_id,
            asdict(verification),
        )
        record(
            "river.receipt.completed",
            "river",
            command.command_id,
            {
                "execution_id": execution.execution_id,
                "verification_id": verification.verification_id,
                "prior_record_hash": receipts[-1].record_hash,
            },
        )
        return GovernedExecutionOutcome(
            decision=decision,
            token_id=claims.token_id,
            execution=execution,
            verification=verification,
            evidence_receipts=tuple(receipts),
        )
