-- Genesis Control Tower v1
-- Apply after 001 Actor Box, 002 CloudBrowser, 003 authoritative hardening,
-- 004 Runtime Platform and 005 Edge Node.

begin;

create schema if not exists genesis_control_tower;
revoke all on schema genesis_control_tower from public, anon, authenticated;

create type genesis_control_tower.fleet_status as enum (
  'ONLINE', 'DEGRADED', 'OFFLINE', 'QUARANTINED',
  'DRAINING', 'RETIRED', 'UNKNOWN'
);
create type genesis_control_tower.command_request_status as enum (
  'AUTHORIZATION_REQUIRED', 'AUTHORIZED', 'DISPATCHED',
  'REJECTED', 'EXPIRED', 'CANCELLED'
);
create type genesis_control_tower.incident_severity as enum ('INFO', 'WARNING', 'CRITICAL');
create type genesis_control_tower.incident_status as enum (
  'OPEN', 'ACKNOWLEDGED', 'MITIGATING', 'RESOLVED', 'CLOSED'
);
create type genesis_control_tower.incident_source as enum ('SYSTEM', 'MANUAL');
create type genesis_control_tower.publication_stream as enum ('RUNTIME', 'EDGE', 'CONTROL_TOWER');
create type genesis_control_tower.publication_lease_status as enum (
  'LEASED', 'ACKNOWLEDGED', 'EXPIRED', 'FAILED'
);

create table genesis_control_tower.fleet_node_snapshots (
  node_id text primary key references genesis_runtime.runtime_nodes(node_id),
  node_class text not null,
  region text not null,
  jurisdiction text not null,
  runtime_status text not null,
  edge_status text,
  effective_status genesis_control_tower.fleet_status not null,
  last_seen_at timestamptz,
  heartbeat_age_seconds integer check (heartbeat_age_seconds is null or heartbeat_age_seconds >= 0),
  active_instances integer not null check (active_instances >= 0),
  active_sessions integer not null check (active_sessions >= 0),
  pending_commands integer not null check (pending_commands >= 0),
  open_incidents integer not null check (open_incidents >= 0),
  capacity jsonb not null default '{}'::jsonb,
  latest_metrics jsonb not null default '{}'::jsonb,
  source_fingerprint text not null check (source_fingerprint ~ '^[0-9a-f]{64}$'),
  observed_at timestamptz not null,
  check (jsonb_typeof(capacity) = 'object'),
  check (jsonb_typeof(latest_metrics) = 'object')
);
create index control_fleet_status_lookup
  on genesis_control_tower.fleet_node_snapshots(effective_status, region, node_id);

create table genesis_control_tower.command_requests (
  request_id text primary key,
  node_id text not null references genesis_runtime.runtime_nodes(node_id),
  command_type genesis_edge.edge_command_type not null,
  required_capability_action text not null,
  requested_by text not null,
  target_reference text not null,
  payload jsonb not null default '{}'::jsonb,
  purpose text not null,
  status genesis_control_tower.command_request_status not null,
  expires_at timestamptz not null,
  authorization_capability_id text references public.capability_grants(capability_id),
  authorized_by text,
  authorized_at timestamptz,
  authorization_reason text,
  dispatched_command_id text references genesis_edge.edge_commands(command_id),
  dispatched_at timestamptz,
  rejection_reason text,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  check (jsonb_typeof(payload) = 'object'),
  check (expires_at > created_at),
  check (updated_at >= created_at),
  check (authorized_at is null or authorized_at >= created_at),
  check (dispatched_at is null or authorized_at is not null)
);
create index control_command_authorization_queue
  on genesis_control_tower.command_requests(status, expires_at, created_at, request_id)
  where status in ('AUTHORIZATION_REQUIRED', 'AUTHORIZED');

create table genesis_control_tower.incidents (
  incident_id text primary key,
  node_id text not null references genesis_runtime.runtime_nodes(node_id),
  severity genesis_control_tower.incident_severity not null,
  incident_type text not null,
  summary text not null,
  source genesis_control_tower.incident_source not null,
  status genesis_control_tower.incident_status not null,
  opened_by text not null,
  assigned_to text,
  evidence_references jsonb not null default '[]'::jsonb,
  resolution_note text,
  opened_at timestamptz not null,
  acknowledged_at timestamptz,
  mitigating_at timestamptz,
  resolved_at timestamptz,
  closed_at timestamptz,
  updated_at timestamptz not null,
  check (jsonb_typeof(evidence_references) = 'array'),
  check (updated_at >= opened_at)
);
create index control_incident_queue
  on genesis_control_tower.incidents(status, severity, opened_at, incident_id);
create unique index control_system_incident_dedupe
  on genesis_control_tower.incidents(node_id, incident_type)
  where source = 'SYSTEM' and status in ('OPEN', 'ACKNOWLEDGED', 'MITIGATING');

create table genesis_control_tower.control_tower_events (
  event_id text primary key,
  aggregate_type text not null,
  aggregate_id text not null,
  event_type text not null,
  actor_id text not null,
  payload jsonb not null,
  occurred_at timestamptz not null,
  previous_event_hash text check (previous_event_hash is null or previous_event_hash ~ '^[0-9a-f]{64}$'),
  evidence_hash text not null unique check (evidence_hash ~ '^[0-9a-f]{64}$'),
  published_at timestamptz,
  publication_attempts integer not null default 0 check (publication_attempts >= 0),
  created_at timestamptz not null default now(),
  check (jsonb_typeof(payload) = 'object')
);
create index control_event_chain_lookup
  on genesis_control_tower.control_tower_events(aggregate_type, aggregate_id, occurred_at desc, event_id desc);
create index control_event_outbox_lookup
  on genesis_control_tower.control_tower_events(published_at, occurred_at, event_id)
  where published_at is null;

create table genesis_control_tower.publication_leases (
  lease_id text primary key,
  publisher_id text not null,
  lease_token_hash text not null check (lease_token_hash ~ '^[0-9a-f]{64}$'),
  status genesis_control_tower.publication_lease_status not null,
  leased_at timestamptz not null,
  expires_at timestamptz not null,
  acknowledged_at timestamptz,
  check (expires_at > leased_at),
  check (acknowledged_at is null or acknowledged_at >= leased_at)
);

create table genesis_control_tower.publication_claims (
  stream genesis_control_tower.publication_stream not null,
  source_event_id text not null,
  lease_id text not null references genesis_control_tower.publication_leases(lease_id),
  evidence_hash text not null check (evidence_hash ~ '^[0-9a-f]{64}$'),
  leased_until timestamptz not null,
  attempts integer not null default 1 check (attempts > 0),
  published_at timestamptz,
  destination_reference text,
  last_error text,
  updated_at timestamptz not null,
  primary key (stream, source_event_id)
);
create index control_publication_active_claims
  on genesis_control_tower.publication_claims(leased_until, stream, source_event_id)
  where published_at is null;

revoke all on all tables in schema genesis_control_tower from public, anon, authenticated;

alter table genesis_control_tower.fleet_node_snapshots enable row level security;
alter table genesis_control_tower.command_requests enable row level security;
alter table genesis_control_tower.incidents enable row level security;
alter table genesis_control_tower.control_tower_events enable row level security;
alter table genesis_control_tower.publication_leases enable row level security;
alter table genesis_control_tower.publication_claims enable row level security;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'genesis_control_plane') then
    create role genesis_control_plane nologin;
  end if;
end
$$;

grant usage on schema genesis_control_tower to genesis_control_plane;
grant usage on all types in schema genesis_control_tower to genesis_control_plane;
grant select, insert, update on all tables in schema genesis_control_tower to genesis_control_plane;

create policy genesis_control_plane_fleet_snapshots
  on genesis_control_tower.fleet_node_snapshots for all to genesis_control_plane
  using (true) with check (true);
create policy genesis_control_plane_command_requests
  on genesis_control_tower.command_requests for all to genesis_control_plane
  using (true) with check (true);
create policy genesis_control_plane_incidents
  on genesis_control_tower.incidents for all to genesis_control_plane
  using (true) with check (true);
create policy genesis_control_plane_control_events
  on genesis_control_tower.control_tower_events for all to genesis_control_plane
  using (true) with check (true);
create policy genesis_control_plane_publication_leases
  on genesis_control_tower.publication_leases for all to genesis_control_plane
  using (true) with check (true);
create policy genesis_control_plane_publication_claims
  on genesis_control_tower.publication_claims for all to genesis_control_plane
  using (true) with check (true);

create view genesis_control_tower.fleet_dashboard
with (security_invoker = true) as
select
  count(*) as total_nodes,
  count(*) filter (where effective_status = 'ONLINE') as online_nodes,
  count(*) filter (where effective_status = 'DEGRADED') as degraded_nodes,
  count(*) filter (where effective_status = 'OFFLINE') as offline_nodes,
  count(*) filter (where effective_status = 'QUARANTINED') as quarantined_nodes,
  sum(open_incidents) as open_incidents,
  sum(pending_commands) as pending_edge_commands,
  max(observed_at) as observed_at
from genesis_control_tower.fleet_node_snapshots;
revoke all on genesis_control_tower.fleet_dashboard from public, anon, authenticated;
grant select on genesis_control_tower.fleet_dashboard to genesis_control_plane;

commit;
