from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
import hashlib
import secrets
from typing import Callable

from .capabilities import CapabilityVerifier
from .config import Settings
from .errors import AuthorizationError, NotFoundError, StateConflictError
from .evidence import build_event, new_id, source_fingerprint, utc_now
from .models import (
    AuthorizationDecision,
    AuthorizeCommandRequest,
    CommandRequestStatus,
    CommandType,
    ControlCommandRequest,
    ControlIncident,
    DashboardSummary,
    DispatchedEdgeCommand,
    DispatchCommandRequest,
    FleetNodeSnapshot,
    FleetRefreshReceipt,
    FleetStatus,
    IncidentSeverity,
    IncidentSource,
    IncidentStatus,
    IncidentTransitionRequest,
    CreateCommandRequest,
    CreateIncidentRequest,
    PublicationLease,
    PublicationLeaseRequest,
    PublicationLeaseStatus,
    PublicationAckRequest,
    PublicationReceipt,
)
from .repository import ControlTowerRepository

COMMAND_ACTIONS: dict[CommandType, str] = {
    CommandType.START_INSTANCE: "EDGE_START_INSTANCE",
    CommandType.STOP_INSTANCE: "EDGE_STOP_INSTANCE",
    CommandType.PAUSE_SESSION: "EDGE_PAUSE_SESSION",
    CommandType.TERMINATE_SESSION: "EDGE_TERMINATE_SESSION",
    CommandType.EXECUTE_RECOVERY: "RUNTIME_RECOVERY_EXECUTE",
    CommandType.ROTATE_AGENT: "EDGE_ROTATE_AGENT",
    CommandType.DRAIN_NODE: "EDGE_DRAIN_NODE",
}

INCIDENT_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.OPEN: {IncidentStatus.ACKNOWLEDGED, IncidentStatus.MITIGATING, IncidentStatus.RESOLVED},
    IncidentStatus.ACKNOWLEDGED: {IncidentStatus.MITIGATING, IncidentStatus.RESOLVED},
    IncidentStatus.MITIGATING: {IncidentStatus.RESOLVED},
    IncidentStatus.RESOLVED: {IncidentStatus.CLOSED},
    IncidentStatus.CLOSED: set(),
}


class ControlTowerEngine:
    def __init__(
        self,
        repository: ControlTowerRepository,
        capability_verifier: CapabilityVerifier,
        settings: Settings,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.repository = repository
        self.capability_verifier = capability_verifier
        self.settings = settings
        self.clock = clock

    def _append_event(
        self,
        *,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        actor_id: str,
        payload: dict[str, object],
        at: datetime,
    ):
        latest = self.repository.latest_event(aggregate_type, aggregate_id)
        event = build_event(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            actor_id=actor_id,
            payload=payload,
            previous_event_hash=latest.evidence_hash if latest else None,
            occurred_at=at,
        )
        return self.repository.append_event(event)

    def _effective_status(self, observation, at: datetime) -> tuple[FleetStatus, int | None]:
        runtime = observation.runtime_status.upper()
        edge = (observation.edge_status or "").upper()
        if "RETIRED" in {runtime, edge}:
            return FleetStatus.RETIRED, None
        if "QUARANTINED" in {runtime, edge}:
            return FleetStatus.QUARANTINED, None
        if "DRAINING" in {runtime, edge}:
            return FleetStatus.DRAINING, None
        if observation.last_seen_at is None:
            return FleetStatus.UNKNOWN, None
        if observation.last_seen_at.tzinfo is None or observation.last_seen_at.utcoffset() is None:
            raise StateConflictError(
                "Fleet source returned a timezone-naive last_seen_at value",
                reason_codes=["SOURCE_TIMESTAMP_INVALID"],
            )
        age = max(0, int((at - observation.last_seen_at).total_seconds()))
        if age >= self.settings.offline_after_seconds or "OFFLINE" in {runtime, edge}:
            return FleetStatus.OFFLINE, age
        if age >= self.settings.degraded_after_seconds or "DEGRADED" in {runtime, edge}:
            return FleetStatus.DEGRADED, age
        return FleetStatus.ONLINE, age

    @staticmethod
    def _incident_for_status(status: FleetStatus) -> tuple[str, IncidentSeverity, str] | None:
        if status == FleetStatus.OFFLINE:
            return "NODE_OFFLINE", IncidentSeverity.CRITICAL, "Edge Node heartbeat exceeded the offline threshold"
        if status == FleetStatus.QUARANTINED:
            return "NODE_QUARANTINED", IncidentSeverity.CRITICAL, "Runtime or Edge Node is quarantined"
        if status == FleetStatus.DEGRADED:
            return "NODE_DEGRADED", IncidentSeverity.WARNING, "Node is reporting degraded health"
        return None

    def refresh_fleet(self, actor_id: str) -> FleetRefreshReceipt:
        at = self.clock()
        opened: list[str] = []
        resolved: list[str] = []
        refreshed: list[str] = []
        with self.repository.transaction("fleet-refresh"):
            observations = self.repository.load_fleet_observations(at)
            for observation in observations:
                effective, age = self._effective_status(observation, at)
                incident_rule = self._incident_for_status(effective)
                active_types = {"NODE_OFFLINE", "NODE_QUARANTINED", "NODE_DEGRADED"}
                if incident_rule is not None:
                    incident_type, severity, summary = incident_rule
                    current = self.repository.find_open_incident(observation.node_id, incident_type)
                    if current is None:
                        incident = ControlIncident(
                            incident_id=new_id("INCIDENT"),
                            node_id=observation.node_id,
                            severity=severity,
                            incident_type=incident_type,
                            summary=summary,
                            source=IncidentSource.SYSTEM,
                            status=IncidentStatus.OPEN,
                            opened_by=actor_id,
                            evidence_references=[],
                            opened_at=at,
                            updated_at=at,
                        )
                        self.repository.save_incident(incident)
                        opened.append(incident.incident_id)
                        self._append_event(
                            aggregate_type="INCIDENT",
                            aggregate_id=incident.incident_id,
                            event_type="CONTROL_INCIDENT_OPENED",
                            actor_id=actor_id,
                            payload={"node_id": observation.node_id, "incident_type": incident_type, "source": "SYSTEM"},
                            at=at,
                        )
                else:
                    for incident_type in active_types:
                        current = self.repository.find_open_incident(observation.node_id, incident_type)
                        if current is not None and current.source == IncidentSource.SYSTEM:
                            current = current.model_copy(
                                update={
                                    "status": IncidentStatus.RESOLVED,
                                    "resolution_note": "Fleet status returned to a non-incident state",
                                    "resolved_at": at,
                                    "updated_at": at,
                                }
                            )
                            self.repository.save_incident(current)
                            resolved.append(current.incident_id)
                            self._append_event(
                                aggregate_type="INCIDENT",
                                aggregate_id=current.incident_id,
                                event_type="CONTROL_INCIDENT_AUTO_RESOLVED",
                                actor_id=actor_id,
                                payload={"node_id": observation.node_id, "effective_status": effective.value},
                                at=at,
                            )
                open_incidents = sum(
                    1
                    for incident in self.repository.list_incidents()
                    if incident.node_id == observation.node_id
                    and incident.status in {IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED, IncidentStatus.MITIGATING}
                )
                fingerprint_payload = observation.model_dump(mode="json")
                fingerprint_payload["effective_status"] = effective.value
                snapshot = FleetNodeSnapshot(
                    node_id=observation.node_id,
                    node_class=observation.node_class,
                    region=observation.region,
                    jurisdiction=observation.jurisdiction,
                    runtime_status=observation.runtime_status,
                    edge_status=observation.edge_status,
                    effective_status=effective,
                    last_seen_at=observation.last_seen_at,
                    heartbeat_age_seconds=age,
                    active_instances=observation.active_instances,
                    active_sessions=observation.active_sessions,
                    pending_commands=observation.pending_commands,
                    open_incidents=open_incidents,
                    capacity=observation.capacity,
                    latest_metrics=observation.latest_metrics,
                    source_fingerprint=source_fingerprint(fingerprint_payload),
                    observed_at=at,
                )
                self.repository.save_snapshot(snapshot)
                refreshed.append(observation.node_id)
            event = self._append_event(
                aggregate_type="FLEET",
                aggregate_id="GENESIS-FLEET",
                event_type="CONTROL_FLEET_REFRESHED",
                actor_id=actor_id,
                payload={
                    "node_count": len(refreshed),
                    "opened_incidents": opened,
                    "resolved_incidents": resolved,
                },
                at=at,
            )
        return FleetRefreshReceipt(
            observed_at=at,
            refreshed_node_ids=refreshed,
            opened_incident_ids=opened,
            resolved_incident_ids=resolved,
            evidence_event_id=event.event_id,
        )

    def get_node(self, node_id: str) -> FleetNodeSnapshot:
        snapshot = self.repository.get_snapshot(node_id)
        if snapshot is None:
            raise NotFoundError("Fleet node snapshot was not found", reason_codes=["FLEET_NODE_NOT_FOUND"])
        return snapshot

    def list_fleet(self, status: FleetStatus | None = None) -> list[FleetNodeSnapshot]:
        snapshots = self.repository.list_snapshots()
        return [item for item in snapshots if status is None or item.effective_status == status]

    def create_command_request(self, request: CreateCommandRequest) -> ControlCommandRequest:
        at = self.clock()
        if request.expires_at <= at:
            raise StateConflictError("Command request is already expired", reason_codes=["COMMAND_REQUEST_EXPIRED"])
        if request.expires_at > at + timedelta(hours=24):
            raise StateConflictError("Command request expiry cannot exceed 24 hours", reason_codes=["COMMAND_REQUEST_EXPIRY_TOO_LONG"])
        snapshot = self.get_node(request.node_id)
        if snapshot.effective_status == FleetStatus.RETIRED:
            raise StateConflictError("Commands cannot target a retired node", reason_codes=["NODE_RETIRED"])
        if snapshot.effective_status == FleetStatus.QUARANTINED and request.command_type not in {
            CommandType.EXECUTE_RECOVERY,
            CommandType.ROTATE_AGENT,
            CommandType.DRAIN_NODE,
        }:
            raise StateConflictError(
                "Only recovery, rotation or drain commands may target a quarantined node",
                reason_codes=["QUARANTINED_COMMAND_BLOCKED"],
            )
        with self.repository.transaction(f"command-request:{request.request_id}"):
            if self.repository.get_command_request(request.request_id) is not None:
                raise StateConflictError("Command request ID already exists", reason_codes=["COMMAND_REQUEST_ID_CONFLICT"])
            record = ControlCommandRequest(
                request_id=request.request_id,
                node_id=request.node_id,
                command_type=request.command_type,
                required_capability_action=COMMAND_ACTIONS[request.command_type],
                requested_by=request.requested_by,
                target_reference=request.target_reference,
                payload=request.payload,
                purpose=request.purpose,
                status=CommandRequestStatus.AUTHORIZATION_REQUIRED,
                expires_at=request.expires_at,
                created_at=at,
                updated_at=at,
            )
            self.repository.save_command_request(record)
            self._append_event(
                aggregate_type="COMMAND_REQUEST",
                aggregate_id=record.request_id,
                event_type="CONTROL_COMMAND_AUTHORIZATION_REQUESTED",
                actor_id=request.requested_by,
                payload={"node_id": record.node_id, "command_type": record.command_type.value},
                at=at,
            )
            return record

    def _command_request(self, request_id: str) -> ControlCommandRequest:
        record = self.repository.get_command_request(request_id)
        if record is None:
            raise NotFoundError("Command request was not found", reason_codes=["COMMAND_REQUEST_NOT_FOUND"])
        return record

    def authorize_command(self, request_id: str, request: AuthorizeCommandRequest) -> ControlCommandRequest:
        at = self.clock()
        with self.repository.transaction(f"command-request:{request_id}"):
            record = self._command_request(request_id)
            if record.status != CommandRequestStatus.AUTHORIZATION_REQUIRED:
                raise StateConflictError("Command request is not awaiting authorization", reason_codes=["COMMAND_NOT_AWAITING_AUTHORIZATION"])
            if record.expires_at <= at:
                record = record.model_copy(update={"status": CommandRequestStatus.EXPIRED, "updated_at": at})
                self.repository.save_command_request(record)
                raise StateConflictError("Command request has expired", reason_codes=["COMMAND_REQUEST_EXPIRED"])
            if request.decision == AuthorizationDecision.REJECT:
                record = record.model_copy(
                    update={
                        "status": CommandRequestStatus.REJECTED,
                        "rejection_reason": request.reason,
                        "updated_at": at,
                    }
                )
                event_type = "CONTROL_COMMAND_REJECTED"
            else:
                assert request.capability_id is not None
                self.capability_verifier.verify(
                    capability_id=request.capability_id,
                    subject_id=request.actor_id,
                    resource_id=record.node_id,
                    allowed_action=record.required_capability_action,
                    at=at,
                )
                record = record.model_copy(
                    update={
                        "status": CommandRequestStatus.AUTHORIZED,
                        "authorization_capability_id": request.capability_id,
                        "authorized_by": request.actor_id,
                        "authorized_at": at,
                        "authorization_reason": request.reason,
                        "updated_at": at,
                    }
                )
                event_type = "CONTROL_COMMAND_AUTHORIZED"
            self.repository.save_command_request(record)
            self._append_event(
                aggregate_type="COMMAND_REQUEST",
                aggregate_id=record.request_id,
                event_type=event_type,
                actor_id=request.actor_id,
                payload={"node_id": record.node_id, "reason": request.reason},
                at=at,
            )
            return record

    def dispatch_command(self, request_id: str, request: DispatchCommandRequest) -> ControlCommandRequest:
        at = self.clock()
        with self.repository.transaction(f"command-request:{request_id}"):
            record = self._command_request(request_id)
            if record.status != CommandRequestStatus.AUTHORIZED:
                raise StateConflictError("Command request is not authorized", reason_codes=["COMMAND_NOT_AUTHORIZED"])
            if record.expires_at <= at:
                expired = record.model_copy(update={"status": CommandRequestStatus.EXPIRED, "updated_at": at})
                self.repository.save_command_request(expired)
                raise StateConflictError("Command request has expired", reason_codes=["COMMAND_REQUEST_EXPIRED"])
            if request.actor_id != record.authorized_by:
                raise AuthorizationError(
                    "The authorizing actor must dispatch the command in this version",
                    reason_codes=["DISPATCH_ACTOR_MISMATCH"],
                )
            if record.authorization_capability_id is None or record.authorized_by is None:
                raise StateConflictError("Authorized command is missing authority binding", reason_codes=["COMMAND_AUTHORITY_BINDING_MISSING"])
            self.capability_verifier.verify(
                capability_id=record.authorization_capability_id,
                subject_id=record.authorized_by,
                resource_id=record.node_id,
                allowed_action=record.required_capability_action,
                at=at,
            )
            command = DispatchedEdgeCommand(
                command_id=new_id("EDGE-COMMAND"),
                node_id=record.node_id,
                command_type=record.command_type,
                capability_id=record.authorization_capability_id,
                required_capability_action=record.required_capability_action,
                issued_by=record.authorized_by,
                target_reference=record.target_reference,
                payload=record.payload,
                issued_at=at,
                expires_at=record.expires_at,
            )
            dispatched = record.model_copy(
                update={
                    "status": CommandRequestStatus.DISPATCHED,
                    "dispatched_command_id": command.command_id,
                    "dispatched_at": at,
                    "updated_at": at,
                }
            )
            self.repository.dispatch_command(dispatched, command)
            self._append_event(
                aggregate_type="COMMAND_REQUEST",
                aggregate_id=record.request_id,
                event_type="CONTROL_COMMAND_DISPATCHED",
                actor_id=request.actor_id,
                payload={"node_id": record.node_id, "edge_command_id": command.command_id},
                at=at,
            )
            return dispatched

    def create_incident(self, request: CreateIncidentRequest) -> ControlIncident:
        at = self.clock()
        self.get_node(request.node_id)
        with self.repository.transaction(f"incident:{request.incident_id}"):
            if self.repository.get_incident(request.incident_id) is not None:
                raise StateConflictError("Incident ID already exists", reason_codes=["INCIDENT_ID_CONFLICT"])
            incident = ControlIncident(
                incident_id=request.incident_id,
                node_id=request.node_id,
                severity=request.severity,
                incident_type=request.incident_type,
                summary=request.summary,
                source=IncidentSource.MANUAL,
                status=IncidentStatus.OPEN,
                opened_by=request.opened_by,
                evidence_references=request.evidence_references,
                opened_at=at,
                updated_at=at,
            )
            self.repository.save_incident(incident)
            self._append_event(
                aggregate_type="INCIDENT",
                aggregate_id=incident.incident_id,
                event_type="CONTROL_INCIDENT_OPENED",
                actor_id=request.opened_by,
                payload={"node_id": incident.node_id, "severity": incident.severity.value, "source": "MANUAL"},
                at=at,
            )
            return incident

    def transition_incident(self, incident_id: str, request: IncidentTransitionRequest) -> ControlIncident:
        at = self.clock()
        with self.repository.transaction(f"incident:{incident_id}"):
            incident = self.repository.get_incident(incident_id)
            if incident is None:
                raise NotFoundError("Incident was not found", reason_codes=["INCIDENT_NOT_FOUND"])
            if request.status not in INCIDENT_TRANSITIONS[incident.status]:
                raise StateConflictError(
                    f"Incident cannot transition from {incident.status.value} to {request.status.value}",
                    reason_codes=["INCIDENT_TRANSITION_INVALID"],
                )
            updates: dict[str, object] = {"status": request.status, "updated_at": at}
            if request.status == IncidentStatus.ACKNOWLEDGED:
                updates.update({"acknowledged_at": at, "assigned_to": request.actor_id})
            elif request.status == IncidentStatus.MITIGATING:
                updates.update({"mitigating_at": at, "assigned_to": request.actor_id})
            elif request.status == IncidentStatus.RESOLVED:
                updates.update({"resolved_at": at, "resolution_note": request.note})
            elif request.status == IncidentStatus.CLOSED:
                updates.update({"closed_at": at})
            incident = incident.model_copy(update=updates)
            self.repository.save_incident(incident)
            self._append_event(
                aggregate_type="INCIDENT",
                aggregate_id=incident.incident_id,
                event_type=f"CONTROL_INCIDENT_{request.status.value}",
                actor_id=request.actor_id,
                payload={"node_id": incident.node_id, "note": request.note},
                at=at,
            )
            return incident

    def list_incidents(self, status: IncidentStatus | None = None) -> list[ControlIncident]:
        incidents = self.repository.list_incidents()
        return [item for item in incidents if status is None or item.status == status]

    def lease_publications(self, request: PublicationLeaseRequest) -> PublicationLease:
        at = self.clock()
        seconds = request.lease_seconds or self.settings.publication_default_lease_seconds
        if seconds > self.settings.publication_max_lease_seconds:
            raise StateConflictError("Publication lease exceeds service maximum", reason_codes=["PUBLICATION_LEASE_TOO_LONG"])
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        lease_id = new_id("PUBLICATION-LEASE")
        expires_at = at + timedelta(seconds=seconds)
        with self.repository.transaction("publication-queue"):
            record, events = self.repository.lease_outbox(
                lease_id=lease_id,
                publisher_id=request.publisher_id,
                token_hash=token_hash,
                max_events=request.max_events,
                leased_at=at,
                expires_at=expires_at,
            )
            self._append_event(
                aggregate_type="PUBLICATION_LEASE",
                aggregate_id=lease_id,
                event_type="CONTROL_PUBLICATION_LEASED",
                actor_id=request.publisher_id,
                payload={"event_count": len(events), "expires_at": expires_at.isoformat()},
                at=at,
            )
        return PublicationLease(
            lease_id=record.lease_id,
            publisher_id=record.publisher_id,
            lease_token=raw_token,
            status=record.status,
            events=events,
            leased_at=record.leased_at,
            expires_at=record.expires_at,
        )

    def acknowledge_publications(self, lease_id: str, request: PublicationAckRequest) -> PublicationReceipt:
        at = self.clock()
        token_hash = hashlib.sha256(request.lease_token.encode("utf-8")).hexdigest()
        with self.repository.transaction("publication-queue"):
            acknowledged = self.repository.acknowledge_lease(
                lease_id=lease_id,
                publisher_id=request.publisher_id,
                token_hash=token_hash,
                items=request.items,
                at=at,
            )
            self._append_event(
                aggregate_type="PUBLICATION_LEASE",
                aggregate_id=lease_id,
                event_type="CONTROL_PUBLICATION_ACKNOWLEDGED",
                actor_id=request.publisher_id,
                payload={"acknowledged_event_ids": acknowledged},
                at=at,
            )
        return PublicationReceipt(lease_id=lease_id, acknowledged_event_ids=acknowledged, acknowledged_at=at)

    def dashboard(self) -> DashboardSummary:
        at = self.clock()
        snapshots = self.repository.list_snapshots()
        incidents = self.repository.list_incidents()
        commands = self.repository.list_command_requests()
        counts = Counter(item.effective_status for item in snapshots)
        return DashboardSummary(
            generated_at=at,
            total_nodes=len(snapshots),
            nodes_by_status={status: counts.get(status, 0) for status in FleetStatus},
            open_incidents=sum(1 for item in incidents if item.status in {IncidentStatus.OPEN, IncidentStatus.ACKNOWLEDGED, IncidentStatus.MITIGATING}),
            critical_incidents=sum(1 for item in incidents if item.severity == IncidentSeverity.CRITICAL and item.status not in {IncidentStatus.RESOLVED, IncidentStatus.CLOSED}),
            authorization_queue=sum(1 for item in commands if item.status == CommandRequestStatus.AUTHORIZATION_REQUIRED),
            authorized_commands=sum(1 for item in commands if item.status == CommandRequestStatus.AUTHORIZED),
            unpublished_evidence=self.repository.unpublished_count(at),
        )
