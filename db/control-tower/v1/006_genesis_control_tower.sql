begin;

create schema if not exists genesis_control_tower;

revoke all on schema genesis_control_tower from public, anon, authenticated;
grant usage on schema genesis_control_tower to genesis_control_plane;

create table if not exists genesis_control_tower.fleet_assets (
  asset_id text primary key,
  asset_type text not null check (asset_type in (
    'RUNTIME_NODE','EDGE_NODE','RUNTIME_INSTANCE','ACTOR_BOX',
    'CLOUDBROWSER_SESSION','AGENT','DEVICE','VEHICLE','MERCHANT_TERMINAL'
  )),
  anchor_id text not null,
  authority_reference text not null,
  owner_reference text not null,
  region text not null,
  jurisdiction text not null,
  status text not null check (status in (
    'HEALTHY','DEGRADED','OFFLINE','DRAINING','QUARANTINED','RETIRED','UNKNOWN'
  )),
  health_score integer not null check (health_score between 0 and 100),
  attestation_reference text,
  policy_version text not null,
  observed_at timestamptz not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  check (jsonb_typeof(metadata) = 'object'),
  check (updated_at >= created_at)
);

create index if not exists fleet_assets_status_idx
  on genesis_control_tower.fleet_assets (status, asset_type, region);
create index if not exists fleet_assets_observed_idx
  on genesis_control_tower.fleet_assets (observed_at desc);

create table if not exists genesis_control_tower.incidents (
  incident_id text primary key,
  fingerprint text not null,
  subject_asset_id text not null references genesis_control_tower.fleet_assets(asset_id),
  signal_type text not null,
  severity text not null check (severity in ('LOW','MEDIUM','HIGH','CRITICAL')),
  status text not null check (status in ('OPEN','ACKNOWLEDGED','RESOLVED')),
  summary text not null,
  occurrence_count integer not null check (occurrence_count > 0),
  first_seen_at timestamptz not null,
  last_seen_at timestamptz not null,
  acknowledged_by text,
  acknowledged_at timestamptz,
  resolved_by text,
  resolved_at timestamptz,
  resolution text,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  check (last_seen_at >= first_seen_at),
  check (updated_at >= created_at),
  check ((status <> 'ACKNOWLEDGED') or (acknowledged_by is not null and acknowledged_at is not null)),
  check ((status <> 'RESOLVED') or (resolved_by is not null and resolved_at is not null and resolution is not null))
);

create unique index if not exists incidents_active_fingerprint_uidx
  on genesis_control_tower.incidents (fingerprint)
  where status <> 'RESOLVED';
create index if not exists incidents_subject_status_idx
  on genesis_control_tower.incidents (subject_asset_id, status, severity, last_seen_at desc);

create table if not exists genesis_control_tower.operational_signals (
  signal_id text primary key,
  payload_hash text not null check (payload_hash ~ '^[0-9a-f]{64}$'),
  incident_id text not null references genesis_control_tower.incidents(incident_id),
  ingested_at timestamptz not null
);

create index if not exists operational_signals_incident_idx
  on genesis_control_tower.operational_signals (incident_id, ingested_at);

create table if not exists genesis_control_tower.fleet_commands (
  command_id text primary key,
  target_asset_id text not null references genesis_control_tower.fleet_assets(asset_id),
  command_type text not null check (command_type in (
    'RUN_DIAGNOSTICS','COLLECT_LOGS','RESTART_RUNTIME','DRAIN_NODE',
    'PAUSE_RUNTIME','SUSPEND_NODE','ROTATE_CERTIFICATE','LOCK_ACTOR_BOX','UPGRADE_RUNTIME'
  )),
  issuer_id text not null,
  box_id text not null,
  context_id text not null,
  capability_id text not null,
  purpose text not null,
  parameters jsonb not null default '{}'::jsonb,
  status text not null check (status in (
    'AUTHORIZATION_REQUIRED','APPROVED','DISPATCHED','COMPLETED',
    'FAILED','CANCELLED','EXPIRED'
  )),
  high_impact boolean not null,
  issued_at timestamptz not null,
  expires_at timestamptz not null,
  approved_by text,
  approval_capability_id text,
  approval_reason text,
  approved_at timestamptz,
  dispatched_at timestamptz,
  completed_at timestamptz,
  result jsonb,
  updated_at timestamptz not null,
  check (jsonb_typeof(parameters) = 'object'),
  check (result is null or jsonb_typeof(result) = 'object'),
  check (expires_at > issued_at),
  check (updated_at >= issued_at),
  check ((not high_impact) or status = 'AUTHORIZATION_REQUIRED' or approved_at is not null)
);

create index if not exists fleet_commands_target_status_idx
  on genesis_control_tower.fleet_commands (target_asset_id, status, issued_at desc);
create index if not exists fleet_commands_pending_idx
  on genesis_control_tower.fleet_commands (status, expires_at)
  where status in ('AUTHORIZATION_REQUIRED','APPROVED','DISPATCHED');

create table if not exists genesis_control_tower.events (
  event_id text primary key,
  aggregate_type text not null,
  aggregate_id text not null,
  subject_id text not null,
  event_type text not null,
  actor_id text not null,
  payload jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null,
  previous_event_hash text,
  evidence_hash text not null unique,
  published_at timestamptz,
  check (jsonb_typeof(payload) = 'object'),
  check (previous_event_hash is null or previous_event_hash ~ '^[0-9a-f]{64}$'),
  check (evidence_hash ~ '^[0-9a-f]{64}$')
);

create index if not exists control_tower_events_aggregate_idx
  on genesis_control_tower.events (aggregate_type, aggregate_id, occurred_at desc, event_id desc);
create index if not exists control_tower_events_subject_idx
  on genesis_control_tower.events (subject_id, occurred_at, event_id);
create index if not exists control_tower_events_outbox_idx
  on genesis_control_tower.events (occurred_at, event_id)
  where published_at is null;

alter table genesis_control_tower.fleet_assets enable row level security;
alter table genesis_control_tower.incidents enable row level security;
alter table genesis_control_tower.operational_signals enable row level security;
alter table genesis_control_tower.fleet_commands enable row level security;
alter table genesis_control_tower.events enable row level security;

revoke all on all tables in schema genesis_control_tower from public, anon, authenticated;
grant select, insert, update, delete on all tables in schema genesis_control_tower to genesis_control_plane;

create policy fleet_assets_control_plane on genesis_control_tower.fleet_assets
  for all to genesis_control_plane using (true) with check (true);
create policy incidents_control_plane on genesis_control_tower.incidents
  for all to genesis_control_plane using (true) with check (true);
create policy operational_signals_control_plane on genesis_control_tower.operational_signals
  for all to genesis_control_plane using (true) with check (true);
create policy fleet_commands_control_plane on genesis_control_tower.fleet_commands
  for all to genesis_control_plane using (true) with check (true);
create policy events_control_plane on genesis_control_tower.events
  for all to genesis_control_plane using (true) with check (true);

drop view if exists genesis_control_tower.open_incidents;
create view genesis_control_tower.open_incidents with (security_invoker = true) as
select incident_id, subject_asset_id, signal_type, severity, status, summary,
       occurrence_count, first_seen_at, last_seen_at, updated_at
from genesis_control_tower.incidents
where status <> 'RESOLVED';

drop view if exists genesis_control_tower.fleet_status_summary;
create view genesis_control_tower.fleet_status_summary with (security_invoker = true) as
select asset_type, status, region, count(*)::bigint as asset_count,
       min(health_score) as minimum_health_score,
       max(observed_at) as latest_observation_at
from genesis_control_tower.fleet_assets
group by asset_type, status, region;

revoke all on genesis_control_tower.open_incidents from public, anon, authenticated;
revoke all on genesis_control_tower.fleet_status_summary from public, anon, authenticated;
grant select on genesis_control_tower.open_incidents to genesis_control_plane;
grant select on genesis_control_tower.fleet_status_summary to genesis_control_plane;

commit;
