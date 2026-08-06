begin;

create schema if not exists genesis_edge;
revoke all on schema genesis_edge from public, anon, authenticated;

create type genesis_edge.edge_node_status as enum (
  'ENROLLED', 'ACTIVE', 'DEGRADED', 'OFFLINE',
  'DRAINING', 'QUARANTINED', 'RETIRED'
);
create type genesis_edge.edge_command_type as enum (
  'START_INSTANCE', 'STOP_INSTANCE', 'PAUSE_SESSION',
  'TERMINATE_SESSION', 'EXECUTE_RECOVERY', 'ROTATE_AGENT', 'DRAIN_NODE'
);
create type genesis_edge.edge_command_status as enum (
  'PENDING', 'LEASED', 'SUCCEEDED', 'FAILED',
  'CANCELLED', 'EXPIRED'
);

create table genesis_edge.edge_enrollment_tokens (
  token_id text primary key,
  node_id text not null references genesis_runtime.runtime_nodes(node_id),
  token_hash text not null unique check (token_hash ~ '^[0-9a-f]{64}$'),
  authority_reference text not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  consumed_at timestamptz,
  check (expires_at > created_at),
  check (consumed_at is null or consumed_at >= created_at)
);
create unique index edge_active_enrollment_token_per_node
  on genesis_edge.edge_enrollment_tokens(node_id)
  where consumed_at is null;

create table genesis_edge.edge_node_identities (
  node_id text primary key references genesis_runtime.runtime_nodes(node_id),
  device_id text not null unique,
  agent_id text not null unique,
  hardware_fingerprint text not null check (hardware_fingerprint ~ '^[0-9a-f]{64}$'),
  agent_version text not null,
  credential_reference text not null,
  attestation_reference text not null,
  status genesis_edge.edge_node_status not null default 'ENROLLED',
  last_heartbeat_sequence bigint not null default 0 check (last_heartbeat_sequence >= 0),
  last_spool_sequence bigint not null default 0 check (last_spool_sequence >= 0),
  last_spool_hash text check (last_spool_hash is null or last_spool_hash ~ '^[0-9a-f]{64}$'),
  last_seen_at timestamptz,
  enrolled_at timestamptz not null,
  updated_at timestamptz not null,
  check (last_seen_at is null or last_seen_at >= enrolled_at),
  check (updated_at >= enrolled_at)
);

create table genesis_edge.edge_heartbeats (
  node_id text not null references genesis_edge.edge_node_identities(node_id),
  sequence bigint not null check (sequence > 0),
  sent_at timestamptz not null,
  accepted_at timestamptz not null,
  agent_version text not null,
  attestation_reference text not null,
  runtime_digest text not null check (runtime_digest ~ '^[0-9a-f]{64}$'),
  node_state genesis_edge.edge_node_status not null,
  metrics jsonb not null default '{}'::jsonb,
  signature text not null check (signature ~ '^[0-9a-f]{64}$'),
  primary key (node_id, sequence),
  check (jsonb_typeof(metrics) = 'object')
);
create index edge_heartbeats_latest
  on genesis_edge.edge_heartbeats(node_id, accepted_at desc, sequence desc);

create table genesis_edge.edge_commands (
  command_id text primary key,
  node_id text not null references genesis_edge.edge_node_identities(node_id),
  command_type genesis_edge.edge_command_type not null,
  capability_id text not null references public.capability_grants(capability_id),
  required_capability_action text not null,
  issued_by text not null,
  target_reference text not null,
  payload jsonb not null default '{}'::jsonb,
  status genesis_edge.edge_command_status not null default 'PENDING',
  attempts integer not null default 0 check (attempts >= 0),
  issued_at timestamptz not null,
  expires_at timestamptz not null,
  lease_owner text,
  lease_token_hash text check (lease_token_hash is null or lease_token_hash ~ '^[0-9a-f]{64}$'),
  lease_expires_at timestamptz,
  completed_at timestamptz,
  result jsonb,
  updated_at timestamptz not null,
  check (jsonb_typeof(payload) = 'object'),
  check (result is null or jsonb_typeof(result) = 'object'),
  check (expires_at > issued_at),
  check (
    status <> 'LEASED'
    or (lease_owner is not null and lease_token_hash is not null and lease_expires_at is not null)
  ),
  check (completed_at is null or completed_at >= issued_at)
);
create index edge_commands_lease_queue
  on genesis_edge.edge_commands(node_id, status, issued_at, command_id)
  where status in ('PENDING', 'LEASED');
create index edge_commands_capability_lookup
  on genesis_edge.edge_commands(capability_id, status, expires_at);

create table genesis_edge.edge_spool_events (
  event_id text primary key,
  node_id text not null references genesis_edge.edge_node_identities(node_id),
  sequence bigint not null check (sequence > 0),
  event_type text not null,
  actor_id text not null,
  occurred_at timestamptz not null,
  payload jsonb not null,
  previous_local_hash text check (previous_local_hash is null or previous_local_hash ~ '^[0-9a-f]{64}$'),
  local_hash text not null check (local_hash ~ '^[0-9a-f]{64}$'),
  ingested_at timestamptz not null,
  unique (node_id, sequence),
  check (jsonb_typeof(payload) = 'object')
);

create table genesis_edge.edge_evidence_events (
  event_id text primary key,
  node_id text not null references genesis_edge.edge_node_identities(node_id),
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
create index edge_evidence_chain_lookup
  on genesis_edge.edge_evidence_events(node_id, occurred_at desc, event_id desc);
create index edge_evidence_outbox_lookup
  on genesis_edge.edge_evidence_events(published_at, occurred_at, event_id)
  where published_at is null;

revoke all on all tables in schema genesis_edge from public, anon, authenticated;

alter table genesis_edge.edge_enrollment_tokens enable row level security;
alter table genesis_edge.edge_node_identities enable row level security;
alter table genesis_edge.edge_heartbeats enable row level security;
alter table genesis_edge.edge_commands enable row level security;
alter table genesis_edge.edge_spool_events enable row level security;
alter table genesis_edge.edge_evidence_events enable row level security;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'genesis_control_plane') then
    create role genesis_control_plane nologin;
  end if;
end
$$;

grant usage on schema genesis_edge to genesis_control_plane;
grant usage on all types in schema genesis_edge to genesis_control_plane;
grant select, insert, update on all tables in schema genesis_edge to genesis_control_plane;

create policy genesis_control_plane_edge_enrollment_tokens
  on genesis_edge.edge_enrollment_tokens for all to genesis_control_plane
  using (true) with check (true);
create policy genesis_control_plane_edge_node_identities
  on genesis_edge.edge_node_identities for all to genesis_control_plane
  using (true) with check (true);
create policy genesis_control_plane_edge_heartbeats
  on genesis_edge.edge_heartbeats for all to genesis_control_plane
  using (true) with check (true);
create policy genesis_control_plane_edge_commands
  on genesis_edge.edge_commands for all to genesis_control_plane
  using (true) with check (true);
create policy genesis_control_plane_edge_spool_events
  on genesis_edge.edge_spool_events for all to genesis_control_plane
  using (true) with check (true);
create policy genesis_control_plane_edge_evidence_events
  on genesis_edge.edge_evidence_events for all to genesis_control_plane
  using (true) with check (true);

create view genesis_edge.active_edge_nodes
with (security_invoker = true) as
select e.*, r.region, r.jurisdiction, r.node_class
from genesis_edge.edge_node_identities e
join genesis_runtime.runtime_nodes r on r.node_id = e.node_id
where e.status in ('ENROLLED', 'ACTIVE', 'DEGRADED', 'DRAINING')
  and r.status in ('REGISTERED', 'ACTIVE', 'DRAINING');

revoke all on genesis_edge.active_edge_nodes from public, anon, authenticated;
grant select on genesis_edge.active_edge_nodes to genesis_control_plane;

commit;
