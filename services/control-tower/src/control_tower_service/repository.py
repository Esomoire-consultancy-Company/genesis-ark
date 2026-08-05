from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import secrets
from threading import RLock
from typing import ContextManager, Iterator, Protocol

from .errors import NotFoundError, StateConflictError
from .models import (
    ControlCommandRequest,
    ControlIncident,
    ControlTowerEvent,
    DispatchedEdgeCommand,
    FleetNodeSnapshot,
    IncidentStatus,
    PublicationAckItem,
    PublicationLeaseStatus,
    PublicationSourceEvent,
    SourceFleetObservation,
)


@dataclass(slots=True)
class PublicationLeaseRecord:
    lease_id: str
    publisher_id: str
    token_hash: str
    status: PublicationLeaseStatus
    event_keys: list[tuple[str, str]]
    leased_at: datetime
    expires_at: datetime


class ControlTowerRepository(Protocol):
    def transaction(self, key: str) -> ContextManager[None]: ...
    def load_fleet_observations(self, at: datetime) -> list[SourceFleetObservation]: ...
    def get_snapshot(self, node_id: str) -> FleetNodeSnapshot | None: ...
    def save_snapshot(self, snapshot: FleetNodeSnapshot) -> FleetNodeSnapshot: ...
    def list_snapshots(self) -> list[FleetNodeSnapshot]: ...
    def get_command_request(self, request_id: str) -> ControlCommandRequest | None: ...
    def save_command_request(self, request: ControlCommandRequest) -> ControlCommandRequest: ...
    def list_command_requests(self) -> list[ControlCommandRequest]: ...
    def dispatch_command(self, request: ControlCommandRequest, command: DispatchedEdgeCommand) -> None: ...
    def get_incident(self, incident_id: str) -> ControlIncident | None: ...
    def save_incident(self, incident: ControlIncident) -> ControlIncident: ...
    def list_incidents(self) -> list[ControlIncident]: ...
    def find_open_incident(self, node_id: str, incident_type: str) -> ControlIncident | None: ...
    def append_event(self, event: ControlTowerEvent) -> ControlTowerEvent: ...
    def latest_event(self, aggregate_type: str, aggregate_id: str) -> ControlTowerEvent | None: ...
    def lease_outbox(
        self,
        *,
        lease_id: str,
        publisher_id: str,
        token_hash: str,
        max_events: int,
        leased_at: datetime,
        expires_at: datetime,
    ) -> tuple[PublicationLeaseRecord, list[PublicationSourceEvent]]: ...
    def acknowledge_lease(
        self,
        *,
        lease_id: str,
        publisher_id: str,
        token_hash: str,
        items: list[PublicationAckItem],
        at: datetime,
    ) -> list[str]: ...
    def unpublished_count(self, at: datetime) -> int: ...


class InMemoryControlTowerRepository:
    def __init__(self) -> None:
        self.source_observations: dict[str, SourceFleetObservation] = {}
        self.snapshots: dict[str, FleetNodeSnapshot] = {}
        self.command_requests: dict[str, ControlCommandRequest] = {}
        self.dispatched_commands: dict[str, DispatchedEdgeCommand] = {}
        self.incidents: dict[str, ControlIncident] = {}
        self.events: list[ControlTowerEvent] = []
        self.source_events: dict[tuple[str, str], PublicationSourceEvent] = {}
        self.published: dict[tuple[str, str], tuple[datetime, str]] = {}
        self.leases: dict[str, PublicationLeaseRecord] = {}
        self.claims: dict[tuple[str, str], str] = {}
        self._lock = RLock()

    def seed_observation(self, observation: SourceFleetObservation) -> None:
        self.source_observations[observation.node_id] = observation

    def seed_outbox_event(self, event: PublicationSourceEvent) -> None:
        self.source_events[(event.stream.value, event.event_id)] = event

    @contextmanager
    def transaction(self, key: str) -> Iterator[None]:
        del key
        with self._lock:
            snapshot = deepcopy(
                (
                    self.snapshots,
                    self.command_requests,
                    self.dispatched_commands,
                    self.incidents,
                    self.events,
                    self.published,
                    self.leases,
                    self.claims,
                )
            )
            try:
                yield
            except Exception:
                (
                    self.snapshots,
                    self.command_requests,
                    self.dispatched_commands,
                    self.incidents,
                    self.events,
                    self.published,
                    self.leases,
                    self.claims,
                ) = snapshot
                raise

    def load_fleet_observations(self, at: datetime) -> list[SourceFleetObservation]:
        del at
        return sorted(self.source_observations.values(), key=lambda item: item.node_id)

    def get_snapshot(self, node_id: str) -> FleetNodeSnapshot | None:
        return self.snapshots.get(node_id)

    def save_snapshot(self, snapshot: FleetNodeSnapshot) -> FleetNodeSnapshot:
        self.snapshots[snapshot.node_id] = snapshot
        return snapshot

    def list_snapshots(self) -> list[FleetNodeSnapshot]:
        return sorted(self.snapshots.values(), key=lambda item: item.node_id)

    def get_command_request(self, request_id: str) -> ControlCommandRequest | None:
        return self.command_requests.get(request_id)

    def save_command_request(self, request: ControlCommandRequest) -> ControlCommandRequest:
        current = self.command_requests.get(request.request_id)
        if current is not None and current.created_at != request.created_at:
            raise StateConflictError(
                "Command request ID conflicts with an existing request",
                reason_codes=["COMMAND_REQUEST_ID_CONFLICT"],
            )
        self.command_requests[request.request_id] = request
        return request

    def list_command_requests(self) -> list[ControlCommandRequest]:
        return sorted(self.command_requests.values(), key=lambda item: (item.created_at, item.request_id))

    def dispatch_command(self, request: ControlCommandRequest, command: DispatchedEdgeCommand) -> None:
        if command.command_id in self.dispatched_commands:
            raise StateConflictError(
                "The Edge command has already been dispatched",
                reason_codes=["EDGE_COMMAND_ID_CONFLICT"],
            )
        current = self.command_requests.get(request.request_id)
        if current is None:
            raise NotFoundError(
                "Control Tower command request was not found",
                reason_codes=["COMMAND_REQUEST_NOT_FOUND"],
            )
        self.dispatched_commands[command.command_id] = command
        self.command_requests[request.request_id] = request

    def get_incident(self, incident_id: str) -> ControlIncident | None:
        return self.incidents.get(incident_id)

    def save_incident(self, incident: ControlIncident) -> ControlIncident:
        self.incidents[incident.incident_id] = incident
        return incident

    def list_incidents(self) -> list[ControlIncident]:
        return sorted(self.incidents.values(), key=lambda item: (item.opened_at, item.incident_id))

    def find_open_incident(self, node_id: str, incident_type: str) -> ControlIncident | None:
        active = {
            IncidentStatus.OPEN,
            IncidentStatus.ACKNOWLEDGED,
            IncidentStatus.MITIGATING,
        }
        return next(
            (
                item
                for item in self.incidents.values()
                if item.node_id == node_id
                and item.incident_type == incident_type
                and item.status in active
            ),
            None,
        )

    def append_event(self, event: ControlTowerEvent) -> ControlTowerEvent:
        latest = self.latest_event(event.aggregate_type, event.aggregate_id)
        expected = latest.evidence_hash if latest is not None else None
        if event.previous_event_hash != expected:
            raise StateConflictError(
                "Control Tower evidence does not continue the aggregate chain",
                reason_codes=["EVIDENCE_CHAIN_CONFLICT"],
            )
        self.events.append(event)
        publication = PublicationSourceEvent(
            stream="CONTROL_TOWER",
            event_id=event.event_id,
            aggregate_id=event.aggregate_id,
            event_type=event.event_type,
            evidence_hash=event.evidence_hash,
            payload={"actor_id": event.actor_id, **event.payload},
            occurred_at=event.occurred_at,
        )
        self.source_events[(publication.stream.value, publication.event_id)] = publication
        return event

    def latest_event(self, aggregate_type: str, aggregate_id: str) -> ControlTowerEvent | None:
        return next(
            (
                event
                for event in reversed(self.events)
                if event.aggregate_type == aggregate_type and event.aggregate_id == aggregate_id
            ),
            None,
        )

    def _expire_leases(self, at: datetime) -> None:
        for lease in self.leases.values():
            if lease.status == PublicationLeaseStatus.LEASED and lease.expires_at <= at:
                lease.status = PublicationLeaseStatus.EXPIRED
                for key in lease.event_keys:
                    if self.claims.get(key) == lease.lease_id:
                        del self.claims[key]

    def lease_outbox(
        self,
        *,
        lease_id: str,
        publisher_id: str,
        token_hash: str,
        max_events: int,
        leased_at: datetime,
        expires_at: datetime,
    ) -> tuple[PublicationLeaseRecord, list[PublicationSourceEvent]]:
        self._expire_leases(leased_at)
        available = [
            event
            for key, event in self.source_events.items()
            if key not in self.published and key not in self.claims
        ]
        available.sort(key=lambda item: (item.occurred_at, item.stream.value, item.event_id))
        selected = available[:max_events]
        keys = [(item.stream.value, item.event_id) for item in selected]
        record = PublicationLeaseRecord(
            lease_id=lease_id,
            publisher_id=publisher_id,
            token_hash=token_hash,
            status=PublicationLeaseStatus.LEASED,
            event_keys=keys,
            leased_at=leased_at,
            expires_at=expires_at,
        )
        self.leases[lease_id] = record
        for key in keys:
            self.claims[key] = lease_id
        return record, selected

    def acknowledge_lease(
        self,
        *,
        lease_id: str,
        publisher_id: str,
        token_hash: str,
        items: list[PublicationAckItem],
        at: datetime,
    ) -> list[str]:
        self._expire_leases(at)
        lease = self.leases.get(lease_id)
        if lease is None:
            raise NotFoundError("Publication lease was not found", reason_codes=["PUBLICATION_LEASE_NOT_FOUND"])
        if lease.status != PublicationLeaseStatus.LEASED or lease.expires_at <= at:
            raise StateConflictError("Publication lease is no longer active", reason_codes=["PUBLICATION_LEASE_INACTIVE"])
        if lease.publisher_id != publisher_id or not secrets.compare_digest(lease.token_hash, token_hash):
            raise StateConflictError("Publication lease credentials are invalid", reason_codes=["PUBLICATION_LEASE_INVALID"])
        expected = set(lease.event_keys)
        supplied = {(item.stream.value, item.event_id) for item in items}
        if supplied != expected:
            raise StateConflictError(
                "Acknowledgement must cover exactly the events in the lease",
                reason_codes=["PUBLICATION_ACK_SET_MISMATCH"],
            )
        for item in items:
            key = (item.stream.value, item.event_id)
            self.published[key] = (at, item.destination_reference)
            self.claims.pop(key, None)
        lease.status = PublicationLeaseStatus.ACKNOWLEDGED
        return [item.event_id for item in items]

    def unpublished_count(self, at: datetime) -> int:
        self._expire_leases(at)
        return sum(1 for key in self.source_events if key not in self.published)
