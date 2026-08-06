from __future__ import annotations

from datetime import datetime
from threading import RLock
from typing import Protocol

from .errors import StateConflictError
from .models import (
    AllocationStatus,
    RecoveryJob,
    ResourceAllocation,
    ResourceVector,
    RuntimeEvent,
    RuntimeHealthReport,
    RuntimeInstance,
    RuntimeNode,
    RuntimeSession,
    SessionStatus,
)


class RuntimeRepository(Protocol):
    def get_node(self, node_id: str) -> RuntimeNode | None: ...
    def save_node(self, node: RuntimeNode) -> RuntimeNode: ...
    def get_instance(self, instance_id: str) -> RuntimeInstance | None: ...
    def save_instance(self, instance: RuntimeInstance) -> RuntimeInstance: ...
    def get_session(self, session_id: str) -> RuntimeSession | None: ...
    def save_session(self, session: RuntimeSession) -> RuntimeSession: ...
    def save_allocation(self, allocation: ResourceAllocation) -> ResourceAllocation: ...
    def active_allocations_for_instance(self, instance_id: str, at: datetime) -> list[ResourceAllocation]: ...
    def node_reserved_resources(self, node_id: str) -> ResourceVector: ...
    def release_allocations_for_session(self, session_id: str, at: datetime) -> None: ...
    def save_health_report(self, report: RuntimeHealthReport) -> RuntimeHealthReport: ...
    def save_recovery_job(self, job: RecoveryJob) -> RecoveryJob: ...
    def append_event(self, event: RuntimeEvent) -> RuntimeEvent: ...
    def latest_event(self, aggregate_type: str, aggregate_id: str) -> RuntimeEvent | None: ...
    def list_events(self, aggregate_type: str, aggregate_id: str) -> list[RuntimeEvent]: ...


class InMemoryRuntimeRepository:
    def __init__(self) -> None:
        self.nodes: dict[str, RuntimeNode] = {}
        self.instances: dict[str, RuntimeInstance] = {}
        self.sessions: dict[str, RuntimeSession] = {}
        self.allocations: dict[str, ResourceAllocation] = {}
        self.health_reports: dict[str, RuntimeHealthReport] = {}
        self.recovery_jobs: dict[str, RecoveryJob] = {}
        self.events: list[RuntimeEvent] = []
        self._lock = RLock()

    def get_node(self, node_id: str) -> RuntimeNode | None:
        return self.nodes.get(node_id)

    def save_node(self, node: RuntimeNode) -> RuntimeNode:
        with self._lock:
            if node.node_id in self.nodes:
                raise StateConflictError("Runtime node already exists")
            self.nodes[node.node_id] = node
            return node

    def get_instance(self, instance_id: str) -> RuntimeInstance | None:
        return self.instances.get(instance_id)

    def save_instance(self, instance: RuntimeInstance) -> RuntimeInstance:
        with self._lock:
            self.instances[instance.instance_id] = instance
            return instance

    def get_session(self, session_id: str) -> RuntimeSession | None:
        return self.sessions.get(session_id)

    def save_session(self, session: RuntimeSession) -> RuntimeSession:
        with self._lock:
            existing = self.sessions.get(session.session_id)
            if existing is not None and existing.status != SessionStatus.ACTIVE:
                raise StateConflictError("Runtime session is not active")
            self.sessions[session.session_id] = session
            return session

    def save_allocation(self, allocation: ResourceAllocation) -> ResourceAllocation:
        with self._lock:
            if allocation.allocation_id in self.allocations:
                raise StateConflictError("Resource allocation already exists")
            self.allocations[allocation.allocation_id] = allocation
            return allocation

    def active_allocations_for_instance(
        self,
        instance_id: str,
        at: datetime,
    ) -> list[ResourceAllocation]:
        session_ids = {
            session.session_id
            for session in self.sessions.values()
            if session.instance_id == instance_id
            and session.status == SessionStatus.ACTIVE
            and session.started_at <= at < session.expires_at
        }
        return [
            item
            for item in self.allocations.values()
            if item.session_id in session_ids and item.status == AllocationStatus.ACTIVE
        ]

    def release_allocations_for_session(self, session_id: str, at: datetime) -> None:
        with self._lock:
            for allocation_id, allocation in list(self.allocations.items()):
                if allocation.session_id == session_id and allocation.status == AllocationStatus.ACTIVE:
                    self.allocations[allocation_id] = allocation.model_copy(
                        update={"status": AllocationStatus.RELEASED, "released_at": at}
                    )

    def save_health_report(self, report: RuntimeHealthReport) -> RuntimeHealthReport:
        self.health_reports[report.health_report_id] = report
        return report

    def save_recovery_job(self, job: RecoveryJob) -> RecoveryJob:
        self.recovery_jobs[job.recovery_job_id] = job
        return job

    def append_event(self, event: RuntimeEvent) -> RuntimeEvent:
        with self._lock:
            latest = self.latest_event(event.aggregate_type, event.aggregate_id)
            expected = latest.evidence_hash if latest else None
            if event.previous_event_hash != expected:
                raise StateConflictError("Runtime event does not continue the evidence chain")
            self.events.append(event)
            return event

    def latest_event(self, aggregate_type: str, aggregate_id: str) -> RuntimeEvent | None:
        return next(
            (
                event
                for event in reversed(self.events)
                if event.aggregate_type == aggregate_type
                and event.aggregate_id == aggregate_id
            ),
            None,
        )

    def list_events(self, aggregate_type: str, aggregate_id: str) -> list[RuntimeEvent]:
        return [
            event
            for event in self.events
            if event.aggregate_type == aggregate_type
            and event.aggregate_id == aggregate_id
        ]

    def node_reserved_resources(self, node_id: str) -> ResourceVector:
        total = ResourceVector()
        for instance in self.instances.values():
            if instance.node_id == node_id and instance.status not in {"RETIRED", "STOPPED"}:
                total = total.plus(instance.resource_limits)
        return total
