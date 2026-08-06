from __future__ import annotations

from datetime import timedelta
import hashlib
import json

from .capabilities import CapabilityVerifier
from .config import Settings
from .errors import ForbiddenError, NotFoundError, StateConflictError
from .evidence import build_event, new_id, utcnow
from .models import (
    ApproveFleetCommandRequest, CommandCompletionStatus, CommandStatus,
    CompleteFleetCommandRequest, CreateFleetCommandRequest, DashboardSnapshot,
    DispatchFleetCommandRequest, FleetAsset, FleetCommand, HIGH_IMPACT_COMMANDS,
    Incident, IncidentActionRequest, IncidentStatus, ReportSignalRequest,
    SEVERITY_RANK, UpsertFleetAssetRequest,
)
from .repository import ControlTowerRepository

class AssetIncidentOperations:
    def upsert_asset(self, request: UpsertFleetAssetRequest) -> FleetAsset:
        now = utcnow()
        with self.repository.transaction(f"asset:{request.asset_id}"):
            existing = self.repository.get_asset(request.asset_id)
            if existing is not None and request.observed_at < existing.observed_at:
                raise StateConflictError(
                    "Fleet observation is older than the current canonical state",
                    reason_codes=["STALE_FLEET_OBSERVATION"],
                )
            if existing is not None and request.model_dump() == existing.model_dump(
                exclude={"created_at", "updated_at"}
            ):
                return existing
            asset = FleetAsset(
                **request.model_dump(),
                created_at=existing.created_at if existing else now,
                updated_at=now,
            )
            self.repository.save_asset(asset)
            self._emit(
                aggregate_type="FLEET_ASSET",
                aggregate_id=asset.asset_id,
                subject_id=asset.asset_id,
                event_type="FLEET_ASSET_OBSERVED",
                actor_id=asset.owner_reference,
                payload=asset.model_dump(mode="json"),
            )
            return asset

    def get_asset(self, asset_id: str) -> FleetAsset:
        asset = self.repository.get_asset(asset_id)
        if asset is None:
            raise NotFoundError(
                "Fleet asset was not found",
                reason_codes=["FLEET_ASSET_NOT_FOUND"],
            )
        return asset

    def list_assets(self) -> list[FleetAsset]:
        return self.repository.list_assets()

    def report_signal(self, request: ReportSignalRequest) -> Incident:
        self.get_asset(request.subject_asset_id)
        now = utcnow()
        fingerprint = request.fingerprint or hashlib.sha256(
            f"{request.subject_asset_id}|{request.signal_type}".encode("utf-8")
        ).hexdigest()
        payload_hash = hashlib.sha256(
            json.dumps(
                request.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        with self.repository.transaction(f"signal:{request.signal_id}"):
            prior_signal = self.repository.get_signal(request.signal_id)
            if prior_signal is not None:
                prior_hash, prior_incident_id = prior_signal
                if prior_hash != payload_hash:
                    raise StateConflictError(
                        "Signal ID was reused with different content",
                        reason_codes=["SIGNAL_ID_CONFLICT"],
                    )
                return self._incident(prior_incident_id)
            with self.repository.transaction(f"incident-fingerprint:{fingerprint}"):
                existing = self.repository.find_active_incident(fingerprint)
                if existing is None:
                    incident = Incident(
                        incident_id=new_id("INCIDENT"),
                        fingerprint=fingerprint,
                        subject_asset_id=request.subject_asset_id,
                        signal_type=request.signal_type,
                        severity=request.severity,
                        status=IncidentStatus.OPEN,
                        summary=request.summary,
                        occurrence_count=1,
                        first_seen_at=request.observed_at,
                        last_seen_at=request.observed_at,
                        created_at=now,
                        updated_at=now,
                    )
                    event_type = "INCIDENT_OPENED"
                else:
                    severity = (
                        request.severity
                        if SEVERITY_RANK[request.severity] > SEVERITY_RANK[existing.severity]
                        else existing.severity
                    )
                    incident = existing.model_copy(
                        update={
                            "severity": severity,
                            "summary": request.summary,
                            "occurrence_count": existing.occurrence_count + 1,
                            "last_seen_at": max(existing.last_seen_at, request.observed_at),
                            "updated_at": now,
                        }
                    )
                    event_type = "INCIDENT_SIGNAL_CORRELATED"
                self.repository.save_incident(incident)
                self.repository.save_signal(
                    request.signal_id,
                    payload_hash,
                    incident.incident_id,
                )
                self._emit(
                    aggregate_type="INCIDENT",
                    aggregate_id=incident.incident_id,
                    subject_id=incident.subject_asset_id,
                    event_type=event_type,
                    actor_id=request.source_reference,
                    payload={
                        "incident": incident.model_dump(mode="json"),
                        "signal_id": request.signal_id,
                        "details": request.details,
                    },
                )
                return incident

    def acknowledge_incident(
        self,
        incident_id: str,
        request: IncidentActionRequest,
    ) -> Incident:
        now = utcnow()
        with self.repository.transaction(f"incident:{incident_id}"):
            incident = self._incident(incident_id)
            if incident.status == IncidentStatus.RESOLVED:
                raise StateConflictError(
                    "Resolved incidents cannot be acknowledged",
                    reason_codes=["INCIDENT_ALREADY_RESOLVED"],
                )
            self._require_capability(
                capability_id=request.capability_id,
                box_id=request.box_id,
                principal_id=request.actor_id,
                context_id=request.context_id,
                resource_id=incident_id,
                action="CONTROL_TOWER_INCIDENT_ACK",
                purpose=request.purpose,
                at=now,
            )
            if incident.status == IncidentStatus.ACKNOWLEDGED:
                return incident
            updated = incident.model_copy(
                update={
                    "status": IncidentStatus.ACKNOWLEDGED,
                    "acknowledged_by": request.actor_id,
                    "acknowledged_at": now,
                    "updated_at": now,
                }
            )
            self.repository.save_incident(updated)
            self._emit(
                aggregate_type="INCIDENT",
                aggregate_id=incident_id,
                subject_id=incident.subject_asset_id,
                event_type="INCIDENT_ACKNOWLEDGED",
                actor_id=request.actor_id,
                payload={"note": request.note},
            )
            return updated

    def resolve_incident(
        self,
        incident_id: str,
        request: IncidentActionRequest,
    ) -> Incident:
        now = utcnow()
        with self.repository.transaction(f"incident:{incident_id}"):
            incident = self._incident(incident_id)
            if incident.status == IncidentStatus.RESOLVED:
                return incident
            self._require_capability(
                capability_id=request.capability_id,
                box_id=request.box_id,
                principal_id=request.actor_id,
                context_id=request.context_id,
                resource_id=incident_id,
                action="CONTROL_TOWER_INCIDENT_RESOLVE",
                purpose=request.purpose,
                at=now,
            )
            updated = incident.model_copy(
                update={
                    "status": IncidentStatus.RESOLVED,
                    "resolved_by": request.actor_id,
                    "resolved_at": now,
                    "resolution": request.note,
                    "updated_at": now,
                }
            )
            self.repository.save_incident(updated)
            self._emit(
                aggregate_type="INCIDENT",
                aggregate_id=incident_id,
                subject_id=incident.subject_asset_id,
                event_type="INCIDENT_RESOLVED",
                actor_id=request.actor_id,
                payload={"resolution": request.note},
            )
            return updated

    def list_incidents(self) -> list[Incident]:
        return self.repository.list_incidents()
