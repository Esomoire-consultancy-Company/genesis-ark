from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from .models import FleetNodeSnapshot, SourceFleetObservation


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


class PostgresFleetMixin:
    def load_fleet_observations(self, at: datetime) -> list[SourceFleetObservation]:
        del at
        with self._connection() as connection:
            rows = self._all(
                connection,
                """
                select
                  r.node_id, r.node_class, r.region, r.jurisdiction,
                  r.status::text as runtime_status,
                  e.status::text as edge_status,
                  e.last_seen_at,
                  r.capacity,
                  coalesce(i.active_instances, 0) as active_instances,
                  coalesce(s.active_sessions, 0) as active_sessions,
                  coalesce(c.pending_commands, 0) as pending_commands,
                  coalesce(h.metrics, '{}'::jsonb) as latest_metrics
                from genesis_runtime.runtime_nodes r
                left join genesis_edge.edge_node_identities e on e.node_id = r.node_id
                left join lateral (
                  select metrics from genesis_edge.edge_heartbeats h
                  where h.node_id = r.node_id
                  order by accepted_at desc, sequence desc limit 1
                ) h on true
                left join lateral (
                  select count(*)::integer as active_instances
                  from genesis_runtime.runtime_instances i
                  where i.node_id = r.node_id and i.status in ('ACTIVE', 'DEGRADED', 'RECOVERY_PENDING')
                ) i on true
                left join lateral (
                  select count(*)::integer as active_sessions
                  from genesis_runtime.runtime_sessions s
                  join genesis_runtime.runtime_instances ri on ri.instance_id = s.instance_id
                  where ri.node_id = r.node_id and s.status = 'ACTIVE' and s.expires_at > now()
                ) s on true
                left join lateral (
                  select count(*)::integer as pending_commands
                  from genesis_edge.edge_commands c
                  where c.node_id = r.node_id and c.status in ('PENDING', 'LEASED') and c.expires_at > now()
                ) c on true
                order by r.node_id
                """,
            )
        observations: list[SourceFleetObservation] = []
        for row in rows:
            data = dict(row)
            data["capacity"] = _json(data["capacity"])
            data["latest_metrics"] = _json(data["latest_metrics"])
            observations.append(SourceFleetObservation.model_validate(data))
        return observations

    def get_snapshot(self, node_id: str) -> FleetNodeSnapshot | None:
        with self._connection() as connection:
            row = self._one(
                connection,
                "select * from genesis_control_tower.fleet_node_snapshots where node_id = %s",
                (node_id,),
            )
        if row is None:
            return None
        data = dict(row)
        data["capacity"] = _json(data["capacity"])
        data["latest_metrics"] = _json(data["latest_metrics"])
        return FleetNodeSnapshot.model_validate(data)

    def save_snapshot(self, snapshot: FleetNodeSnapshot) -> FleetNodeSnapshot:
        with self._connection() as connection:
            self._run(
                connection,
                """
                insert into genesis_control_tower.fleet_node_snapshots (
                  node_id, node_class, region, jurisdiction, runtime_status,
                  edge_status, effective_status, last_seen_at, heartbeat_age_seconds,
                  active_instances, active_sessions, pending_commands, open_incidents,
                  capacity, latest_metrics, source_fingerprint, observed_at
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s)
                on conflict (node_id) do update set
                  node_class = excluded.node_class,
                  region = excluded.region,
                  jurisdiction = excluded.jurisdiction,
                  runtime_status = excluded.runtime_status,
                  edge_status = excluded.edge_status,
                  effective_status = excluded.effective_status,
                  last_seen_at = excluded.last_seen_at,
                  heartbeat_age_seconds = excluded.heartbeat_age_seconds,
                  active_instances = excluded.active_instances,
                  active_sessions = excluded.active_sessions,
                  pending_commands = excluded.pending_commands,
                  open_incidents = excluded.open_incidents,
                  capacity = excluded.capacity,
                  latest_metrics = excluded.latest_metrics,
                  source_fingerprint = excluded.source_fingerprint,
                  observed_at = excluded.observed_at
                """,
                (
                    snapshot.node_id,
                    snapshot.node_class,
                    snapshot.region,
                    snapshot.jurisdiction,
                    snapshot.runtime_status,
                    snapshot.edge_status,
                    snapshot.effective_status.value,
                    snapshot.last_seen_at,
                    snapshot.heartbeat_age_seconds,
                    snapshot.active_instances,
                    snapshot.active_sessions,
                    snapshot.pending_commands,
                    snapshot.open_incidents,
                    json.dumps(snapshot.capacity),
                    json.dumps(snapshot.latest_metrics),
                    snapshot.source_fingerprint,
                    snapshot.observed_at,
                ),
            )
        return snapshot

    def list_snapshots(self) -> list[FleetNodeSnapshot]:
        with self._connection() as connection:
            rows = self._all(connection, "select * from genesis_control_tower.fleet_node_snapshots order by node_id")
        result: list[FleetNodeSnapshot] = []
        for row in rows:
            data = dict(row)
            data["capacity"] = _json(data["capacity"])
            data["latest_metrics"] = _json(data["latest_metrics"])
            result.append(FleetNodeSnapshot.model_validate(data))
        return result
