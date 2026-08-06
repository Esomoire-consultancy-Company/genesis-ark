from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from .errors import StateConflictError
from .models import CapabilityAuthorization, ControlTowerEvent, FleetAsset, FleetCommand, Incident
from .postgres_base import _decode_fields, _decode_json

class PostgresFleetOperations:
    def get_asset(self, asset_id: str) -> FleetAsset | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select asset_id, asset_type, anchor_id, authority_reference,
                       owner_reference, region, jurisdiction, status, health_score,
                       attestation_reference, policy_version, observed_at, metadata,
                       created_at, updated_at
                from genesis_control_tower.fleet_assets where asset_id = %s
                """,
                (asset_id,),
            )
        decoded = _decode_fields(row, "metadata")
        return FleetAsset.model_validate(decoded) if decoded else None

    def save_asset(self, asset: FleetAsset) -> FleetAsset:
        with self._connection() as connection:
            self._execute(
                connection,
                """
                insert into genesis_control_tower.fleet_assets (
                  asset_id, asset_type, anchor_id, authority_reference,
                  owner_reference, region, jurisdiction, status, health_score,
                  attestation_reference, policy_version, observed_at, metadata,
                  created_at, updated_at
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
                on conflict (asset_id) do update set
                  asset_type = excluded.asset_type,
                  anchor_id = excluded.anchor_id,
                  authority_reference = excluded.authority_reference,
                  owner_reference = excluded.owner_reference,
                  region = excluded.region,
                  jurisdiction = excluded.jurisdiction,
                  status = excluded.status,
                  health_score = excluded.health_score,
                  attestation_reference = excluded.attestation_reference,
                  policy_version = excluded.policy_version,
                  observed_at = excluded.observed_at,
                  metadata = excluded.metadata,
                  updated_at = excluded.updated_at
                """,
                (
                    asset.asset_id,
                    asset.asset_type,
                    asset.anchor_id,
                    asset.authority_reference,
                    asset.owner_reference,
                    asset.region,
                    asset.jurisdiction,
                    asset.status,
                    asset.health_score,
                    asset.attestation_reference,
                    asset.policy_version,
                    asset.observed_at,
                    json.dumps(asset.metadata),
                    asset.created_at,
                    asset.updated_at,
                ),
            )
        return asset

    def get_signal(self, signal_id: str) -> tuple[str, str] | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select payload_hash, incident_id
                from genesis_control_tower.operational_signals
                where signal_id = %s
                """,
                (signal_id,),
            )
        if row is None:
            return None
        result = dict(row)
        return result["payload_hash"], result["incident_id"]

    def save_signal(self, signal_id: str, payload_hash: str, incident_id: str) -> None:
        with self._connection() as connection:
            self._execute(
                connection,
                """
                insert into genesis_control_tower.operational_signals (
                  signal_id, payload_hash, incident_id, ingested_at
                ) values (%s,%s,%s,now())
                on conflict (signal_id) do nothing
                """,
                (signal_id, payload_hash, incident_id),
            )

    def list_assets(self) -> list[FleetAsset]:
        with self._connection() as connection:
            rows = self._fetchall(
                connection,
                """
                select asset_id, asset_type, anchor_id, authority_reference,
                       owner_reference, region, jurisdiction, status, health_score,
                       attestation_reference, policy_version, observed_at, metadata,
                       created_at, updated_at
                from genesis_control_tower.fleet_assets
                order by asset_type, asset_id
                """,
            )
        return [FleetAsset.model_validate(_decode_fields(row, "metadata")) for row in rows]

    def find_active_incident(self, fingerprint: str) -> Incident | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select incident_id, fingerprint, subject_asset_id, signal_type,
                       severity, status, summary, occurrence_count, first_seen_at,
                       last_seen_at, acknowledged_by, acknowledged_at,
                       resolved_by, resolved_at, resolution, created_at, updated_at
                from genesis_control_tower.incidents
                where fingerprint = %s and status <> 'RESOLVED'
                order by created_at desc limit 1
                """,
                (fingerprint,),
            )
        return Incident.model_validate(row) if row else None

    def get_incident(self, incident_id: str) -> Incident | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                """
                select incident_id, fingerprint, subject_asset_id, signal_type,
                       severity, status, summary, occurrence_count, first_seen_at,
                       last_seen_at, acknowledged_by, acknowledged_at,
                       resolved_by, resolved_at, resolution, created_at, updated_at
                from genesis_control_tower.incidents where incident_id = %s
                """,
                (incident_id,),
            )
        return Incident.model_validate(row) if row else None

    def save_incident(self, incident: Incident) -> Incident:
        with self._connection() as connection:
            self._execute(
                connection,
                """
                insert into genesis_control_tower.incidents (
                  incident_id, fingerprint, subject_asset_id, signal_type,
                  severity, status, summary, occurrence_count, first_seen_at,
                  last_seen_at, acknowledged_by, acknowledged_at, resolved_by,
                  resolved_at, resolution, created_at, updated_at
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (incident_id) do update set
                  severity = excluded.severity,
                  status = excluded.status,
                  summary = excluded.summary,
                  occurrence_count = excluded.occurrence_count,
                  last_seen_at = excluded.last_seen_at,
                  acknowledged_by = excluded.acknowledged_by,
                  acknowledged_at = excluded.acknowledged_at,
                  resolved_by = excluded.resolved_by,
                  resolved_at = excluded.resolved_at,
                  resolution = excluded.resolution,
                  updated_at = excluded.updated_at
                """,
                (
                    incident.incident_id,
                    incident.fingerprint,
                    incident.subject_asset_id,
                    incident.signal_type,
                    incident.severity,
                    incident.status,
                    incident.summary,
                    incident.occurrence_count,
                    incident.first_seen_at,
                    incident.last_seen_at,
                    incident.acknowledged_by,
                    incident.acknowledged_at,
                    incident.resolved_by,
                    incident.resolved_at,
                    incident.resolution,
                    incident.created_at,
                    incident.updated_at,
                ),
            )
        return incident

    def list_incidents(self) -> list[Incident]:
        with self._connection() as connection:
            rows = self._fetchall(
                connection,
                """
                select incident_id, fingerprint, subject_asset_id, signal_type,
                       severity, status, summary, occurrence_count, first_seen_at,
                       last_seen_at, acknowledged_by, acknowledged_at,
                       resolved_by, resolved_at, resolution, created_at, updated_at
                from genesis_control_tower.incidents order by created_at, incident_id
                """,
            )
        return [Incident.model_validate(row) for row in rows]
