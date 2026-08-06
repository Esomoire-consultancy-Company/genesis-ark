from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from threading import RLock
from typing import Iterator, Protocol

from .errors import StateConflictError
from .models import (
    CommandStatus,
    ControlTowerEvent,
    FleetAsset,
    FleetCommand,
    Incident,
    IncidentStatus,
)


class ControlTowerRepository(Protocol):
    @contextmanager
    def transaction(self, aggregate_key: str) -> Iterator[None]: ...

    def get_asset(self, asset_id: str) -> FleetAsset | None: ...
    def get_signal(self, signal_id: str) -> tuple[str, str] | None: ...
    def save_signal(self, signal_id: str, payload_hash: str, incident_id: str) -> None: ...
    def save_asset(self, asset: FleetAsset) -> FleetAsset: ...
    def list_assets(self) -> list[FleetAsset]: ...

    def find_active_incident(self, fingerprint: str) -> Incident | None: ...
    def get_incident(self, incident_id: str) -> Incident | None: ...
    def save_incident(self, incident: Incident) -> Incident: ...
    def list_incidents(self) -> list[Incident]: ...

    def get_command(self, command_id: str) -> FleetCommand | None: ...
    def save_command(self, command: FleetCommand) -> FleetCommand: ...
    def list_commands(self) -> list[FleetCommand]: ...

    def append_event(self, event: ControlTowerEvent) -> ControlTowerEvent: ...
    def latest_event(self, aggregate_type: str, aggregate_id: str) -> ControlTowerEvent | None: ...
    def list_events_for_subject(self, subject_id: str) -> list[ControlTowerEvent]: ...


class InMemoryControlTowerRepository:
    def __init__(self) -> None:
        self.assets: dict[str, FleetAsset] = {}
        self.incidents: dict[str, Incident] = {}
        self.signals: dict[str, tuple[str, str]] = {}
        self.commands: dict[str, FleetCommand] = {}
        self.events: list[ControlTowerEvent] = []
        self._lock = RLock()

    @contextmanager
    def transaction(self, aggregate_key: str) -> Iterator[None]:
        del aggregate_key
        with self._lock:
            snapshot = deepcopy((self.assets, self.incidents, self.signals, self.commands, self.events))
            try:
                yield
            except Exception:
                self.assets, self.incidents, self.signals, self.commands, self.events = snapshot
                raise

    def get_asset(self, asset_id: str) -> FleetAsset | None:
        return self.assets.get(asset_id)

    def save_asset(self, asset: FleetAsset) -> FleetAsset:
        self.assets[asset.asset_id] = asset
        return asset

    def list_assets(self) -> list[FleetAsset]:
        return sorted(self.assets.values(), key=lambda item: (item.asset_type, item.asset_id))

    def get_signal(self, signal_id: str) -> tuple[str, str] | None:
        return self.signals.get(signal_id)

    def save_signal(self, signal_id: str, payload_hash: str, incident_id: str) -> None:
        self.signals[signal_id] = (payload_hash, incident_id)

    def find_active_incident(self, fingerprint: str) -> Incident | None:
        return next(
            (
                incident
                for incident in self.incidents.values()
                if incident.fingerprint == fingerprint
                and incident.status != IncidentStatus.RESOLVED
            ),
            None,
        )

    def get_incident(self, incident_id: str) -> Incident | None:
        return self.incidents.get(incident_id)

    def save_incident(self, incident: Incident) -> Incident:
        self.incidents[incident.incident_id] = incident
        return incident

    def list_incidents(self) -> list[Incident]:
        return sorted(self.incidents.values(), key=lambda item: (item.created_at, item.incident_id))

    def get_command(self, command_id: str) -> FleetCommand | None:
        return self.commands.get(command_id)

    def save_command(self, command: FleetCommand) -> FleetCommand:
        existing = self.commands.get(command.command_id)
        if existing is not None and existing.issued_at != command.issued_at:
            raise StateConflictError(
                "Fleet command ID conflicts with an existing command",
                reason_codes=["COMMAND_ID_CONFLICT"],
            )
        self.commands[command.command_id] = command
        return command

    def list_commands(self) -> list[FleetCommand]:
        return sorted(self.commands.values(), key=lambda item: (item.issued_at, item.command_id))

    def append_event(self, event: ControlTowerEvent) -> ControlTowerEvent:
        latest = self.latest_event(event.aggregate_type, event.aggregate_id)
        expected = latest.evidence_hash if latest is not None else None
        if event.previous_event_hash != expected:
            raise StateConflictError(
                "Control Tower event does not continue the aggregate chain",
                reason_codes=["EVIDENCE_CHAIN_CONFLICT"],
            )
        self.events.append(event)
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

    def list_events_for_subject(self, subject_id: str) -> list[ControlTowerEvent]:
        return [event for event in self.events if event.subject_id == subject_id]
