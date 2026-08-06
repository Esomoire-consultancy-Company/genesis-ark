from __future__ import annotations

from datetime import timedelta

from .capabilities import CapabilityVerifier
from .config import Settings
from .errors import ForbiddenError, NotFoundError, StateConflictError
from .evidence import build_runtime_event, new_id, utcnow
from .models import (
    AllocateResourcesRequest,
    AllocationStatus,
    AttestInstanceRequest,
    CreateSessionRequest,
    HealthReportRequest,
    HealthState,
    InstanceStatus,
    IntegrityStatus,
    NodeStatus,
    ProvisionInstanceRequest,
    RecoveryJob,
    RecoveryStatus,
    RegisterNodeRequest,
    ResourceAllocation,
    ResourceVector,
    RuntimeHealthReport,
    RuntimeInstance,
    RuntimeNode,
    RuntimeSession,
    SessionStatus,
    TerminateSessionRequest,
)
from .repository import RuntimeRepository


class RuntimeManager:
    def __init__(
        self,
        repository: RuntimeRepository,
        capability_verifier: CapabilityVerifier,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.capability_verifier = capability_verifier
        self.settings = settings

    def register_node(self, request: RegisterNodeRequest) -> RuntimeNode:
        now = utcnow()
        if self.repository.get_node(request.node_id) is not None:
            raise StateConflictError("Runtime node already exists")
        node = RuntimeNode(
            **request.model_dump(),
            status=NodeStatus.ACTIVE,
            registered_at=now,
            updated_at=now,
        )
        self.repository.save_node(node)
        self._emit(
            aggregate_type="NODE",
            aggregate_id=node.node_id,
            event_type="RUNTIME_NODE_REGISTERED",
            payload=node.model_dump(mode="json"),
        )
        return node

    def provision_instance(
        self,
        request: ProvisionInstanceRequest,
    ) -> RuntimeInstance:
        now = utcnow()
        if self.repository.get_instance(request.instance_id) is not None:
            raise StateConflictError("Runtime instance already exists")
        node = self.repository.get_node(request.node_id)
        if node is None:
            raise NotFoundError(f"Runtime node {request.node_id} does not exist")
        if node.status != NodeStatus.ACTIVE:
            raise StateConflictError(
                "Runtime node is not accepting new instances",
                reason_codes=[f"NODE_{node.status}"],
            )
        reserved = self.repository.node_reserved_resources(node.node_id)
        if not reserved.plus(request.resource_limits).fits_within(node.capacity):
            raise StateConflictError(
                "Runtime node capacity would be exceeded",
                reason_codes=["NODE_CAPACITY_EXCEEDED"],
            )
        instance = RuntimeInstance(
            instance_id=request.instance_id,
            node_id=request.node_id,
            box_id=request.box_id,
            runtime_class=request.runtime_class,
            runtime_version=request.runtime_version,
            status=InstanceStatus.PROVISIONING,
            integrity_status=IntegrityStatus.UNKNOWN,
            resource_limits=request.resource_limits,
            provisioned_at=now,
            updated_at=now,
        )
        self.repository.save_instance(instance)
        self._emit(
            aggregate_type="INSTANCE",
            aggregate_id=instance.instance_id,
            box_id=instance.box_id,
            event_type="RUNTIME_INSTANCE_PROVISIONED",
            payload={
                **instance.model_dump(mode="json"),
                "requested_by": request.requested_by,
                "authority_reference": request.authority_reference,
            },
        )
        return instance

    def attest_instance(
        self,
        instance_id: str,
        request: AttestInstanceRequest,
    ) -> RuntimeInstance:
        now = utcnow()
        instance = self._instance(instance_id)
        if instance.status in {InstanceStatus.RETIRED, InstanceStatus.STOPPED}:
            raise StateConflictError("Runtime instance cannot be attested in its current state")
        if request.integrity_status == IntegrityStatus.ATTESTED:
            status = InstanceStatus.ACTIVE
            activated_at = instance.activated_at or now
        elif request.integrity_status == IntegrityStatus.DEGRADED:
            status = InstanceStatus.DEGRADED
            activated_at = instance.activated_at
        else:
            status = InstanceStatus.SUSPENDED
            activated_at = instance.activated_at
        updated = instance.model_copy(
            update={
                "status": status,
                "integrity_status": request.integrity_status,
                "attestation_reference": request.attestation_reference,
                "last_attested_at": now,
                "activated_at": activated_at,
                "updated_at": now,
            }
        )
        self.repository.save_instance(updated)
        self._emit(
            aggregate_type="INSTANCE",
            aggregate_id=instance_id,
            box_id=updated.box_id,
            event_type="RUNTIME_INSTANCE_ATTESTED",
            payload={
                "integrity_status": request.integrity_status,
                "attestation_reference": request.attestation_reference,
                "attested_by": request.attested_by,
                "instance_status": status,
            },
        )
        return updated

    def create_session(self, request: CreateSessionRequest) -> RuntimeSession:
        now = utcnow()
        if self.repository.get_session(request.session_id) is not None:
            raise StateConflictError("Runtime session already exists")
        instance = self._instance(request.instance_id)
        if instance.box_id != request.box_id:
            raise ForbiddenError(
                "Runtime instance is not bound to the requested Actor Box",
                reason_codes=["INSTANCE_BOX_MISMATCH"],
            )
        if (
            instance.status != InstanceStatus.ACTIVE
            or instance.integrity_status != IntegrityStatus.ATTESTED
        ):
            raise StateConflictError(
                "Runtime instance is not attested and active",
                reason_codes=[
                    f"INSTANCE_{instance.status}",
                    f"INTEGRITY_{instance.integrity_status}",
                ],
            )
        authorization = self.capability_verifier.verify(
            capability_id=request.capability_id,
            box_id=request.box_id,
            principal_id=request.principal_id,
            context_id=request.context_id,
            resource_id=request.instance_id,
            required_actions={"RUNTIME_SESSION_START"},
            purpose=request.purpose,
            at=now,
        )
        if authorization is None:
            raise ForbiddenError(
                "No active Warden capability authorizes this runtime session",
                reason_codes=["CAPABILITY_NOT_ACTIVE"],
            )
        ttl = min(
            request.requested_duration_seconds,
            self.settings.max_session_ttl_seconds,
            max(0, int((authorization.expires_at - now).total_seconds())),
        )
        if ttl < 1:
            raise ForbiddenError(
                "The Warden capability expires before the session can start",
                reason_codes=["CAPABILITY_EXPIRED"],
            )
        session = RuntimeSession(
            session_id=request.session_id,
            instance_id=request.instance_id,
            box_id=request.box_id,
            principal_id=request.principal_id,
            context_id=request.context_id,
            capability_id=request.capability_id,
            session_type=request.session_type,
            purpose=request.purpose,
            status=SessionStatus.ACTIVE,
            started_at=now,
            expires_at=now + timedelta(seconds=ttl),
            updated_at=now,
        )
        self.repository.save_session(session)
        self._emit(
            aggregate_type="SESSION",
            aggregate_id=session.session_id,
            box_id=session.box_id,
            event_type="RUNTIME_SESSION_STARTED",
            payload=session.model_dump(mode="json"),
        )
        return session

    def allocate_resources(
        self,
        session_id: str,
        request: AllocateResourcesRequest,
    ) -> ResourceAllocation:
        now = utcnow()
        session = self._active_session(session_id, now)
        instance = self._instance(session.instance_id)
        authorization = self.capability_verifier.verify(
            capability_id=request.capability_id,
            box_id=session.box_id,
            principal_id=session.principal_id,
            context_id=session.context_id,
            resource_id=session.session_id,
            required_actions={"RUNTIME_RESOURCE_ALLOCATE"},
            purpose=session.purpose,
            at=now,
        )
        if authorization is None:
            raise ForbiddenError(
                "No active Warden capability authorizes this resource allocation",
                reason_codes=["RESOURCE_CAPABILITY_NOT_ACTIVE"],
            )
        allocated = ResourceVector()
        for allocation in self.repository.active_allocations_for_instance(
            instance.instance_id,
            now,
        ):
            allocated = allocated.plus(allocation.resources)
        if not allocated.plus(request.resources).fits_within(instance.resource_limits):
            raise StateConflictError(
                "Runtime instance resource limits would be exceeded",
                reason_codes=["INSTANCE_RESOURCE_LIMIT_EXCEEDED"],
            )
        allocation = ResourceAllocation(
            allocation_id=request.allocation_id,
            session_id=session_id,
            capability_id=request.capability_id,
            resources=request.resources,
            status=AllocationStatus.ACTIVE,
            allocated_at=now,
        )
        self.repository.save_allocation(allocation)
        self._emit(
            aggregate_type="SESSION",
            aggregate_id=session_id,
            box_id=session.box_id,
            event_type="RUNTIME_RESOURCES_ALLOCATED",
            payload=allocation.model_dump(mode="json"),
        )
        return allocation

    def report_health(
        self,
        instance_id: str,
        request: HealthReportRequest,
    ) -> RuntimeHealthReport:
        now = utcnow()
        instance = self._instance(instance_id)
        report = RuntimeHealthReport(
            health_report_id=new_id("RUNTIME-HEALTH"),
            instance_id=instance_id,
            state=request.state,
            reported_by=request.reported_by,
            checks=request.checks,
            metrics=request.metrics,
            reported_at=now,
        )
        self.repository.save_health_report(report)
        updates: dict[str, object] = {"updated_at": now}
        if request.state == HealthState.CRITICAL:
            updates["status"] = InstanceStatus.RECOVERY_PENDING
            job = RecoveryJob(
                recovery_job_id=new_id("RECOVERY-JOB"),
                instance_id=instance_id,
                status=RecoveryStatus.AUTHORIZATION_REQUIRED,
                trigger_health_report_id=report.health_report_id,
                required_capability_action="RUNTIME_RECOVERY_EXECUTE",
                created_at=now,
            )
            self.repository.save_recovery_job(job)
        elif request.state == HealthState.DEGRADED:
            updates["status"] = InstanceStatus.DEGRADED
        elif (
            request.state == HealthState.HEALTHY
            and instance.integrity_status == IntegrityStatus.ATTESTED
        ):
            updates["status"] = InstanceStatus.ACTIVE
        self.repository.save_instance(instance.model_copy(update=updates))
        self._emit(
            aggregate_type="INSTANCE",
            aggregate_id=instance_id,
            box_id=instance.box_id,
            event_type="RUNTIME_HEALTH_REPORTED",
            payload=report.model_dump(mode="json"),
        )
        return report

    def terminate_session(
        self,
        session_id: str,
        request: TerminateSessionRequest,
    ) -> RuntimeSession:
        now = utcnow()
        session = self.repository.get_session(session_id)
        if session is None:
            raise NotFoundError(f"Runtime session {session_id} does not exist")
        if session.status == SessionStatus.TERMINATED:
            return session
        updated = session.model_copy(
            update={
                "status": SessionStatus.TERMINATED,
                "terminated_at": now,
                "termination_reason": request.reason,
                "updated_at": now,
            }
        )
        self.repository.save_session(updated)
        self.repository.release_allocations_for_session(session_id, now)
        self._emit(
            aggregate_type="SESSION",
            aggregate_id=session_id,
            box_id=session.box_id,
            event_type="RUNTIME_SESSION_TERMINATED",
            payload={
                "reason": request.reason,
                "initiated_by": request.initiated_by,
            },
        )
        return updated

    def get_instance(self, instance_id: str) -> RuntimeInstance:
        return self._instance(instance_id)

    def _instance(self, instance_id: str) -> RuntimeInstance:
        instance = self.repository.get_instance(instance_id)
        if instance is None:
            raise NotFoundError(f"Runtime instance {instance_id} does not exist")
        return instance

    def _active_session(self, session_id: str, now) -> RuntimeSession:
        session = self.repository.get_session(session_id)
        if session is None:
            raise NotFoundError(f"Runtime session {session_id} does not exist")
        if session.status != SessionStatus.ACTIVE or not (
            session.started_at <= now < session.expires_at
        ):
            raise StateConflictError(
                "Runtime session is not active",
                reason_codes=[f"SESSION_{session.status}"],
            )
        return session

    def _emit(
        self,
        *,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict,
        box_id: str | None = None,
    ):
        latest = self.repository.latest_event(aggregate_type, aggregate_id)
        event = build_runtime_event(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            box_id=box_id,
            event_type=event_type,
            payload=payload,
            previous_event_hash=latest.evidence_hash if latest else None,
        )
        return self.repository.append_event(event)
