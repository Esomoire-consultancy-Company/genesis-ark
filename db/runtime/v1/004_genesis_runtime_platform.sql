-- Genesis Runtime Platform foundation v1
-- Apply after 001_actor_box_foundation.sql, 002_cloud_browser_foundation.sql,
-- and 003_authoritative_runtime_hardening.sql.

begin;

create schema if not exists genesis_runtime;
revoke all on schema genesis_runtime from public, anon, authenticated;

create type genesis_runtime.runtime_node_status as enum (
  'REGISTERED', 'ACTIVE', 'DRAINING', 'OFFLINE', 'QUARANTINED', 'RETIRED'
);
create type genesis_runtime.runtime_instance_status as enum (
  'PROVISIONING', 'ACTIVE', 'DEGRADED', 'SUSPENDED',
  'RECOVERY_PENDING', 'STOPPED', 'RETIRED'
);
create type genesis_runtime.runtime_session_status as enum (
  'ACTIVE', 'PAUSED', 'TERMINATED', 'EXPIRED'
);
create type genesis_runtime.runtime_session_type as enum (
  'ACTOR', 'CLOUDBROWSER', 'AGENT', 'WORKSPACE', 'MERCHANT', 'VEHICLE'
);
create type genesis_runtime.runtime_health_state as enum (
  'HEALTHY', 'DEGRADED', 'CRITICAL', 'UNKNOWN'
);
create type genesis_runtime.runtime_allocation_status as enum (
  'ACTIVE', 'RELEASED'
);
create type genesis_runtime.runtime_recovery_status as enum (
  'AUTHORIZATION_REQUIRED', 'AUTHORIZED', 'RUNNING',
  'COMPLETED', 'FAILED', 'CANCELLED'
);

create table genesis_runtime.runtime_nodes (
  node_id text primary key,
  node_class text not null,
  region text not null,
  jurisdiction text not null,
  authority_reference text not null,
  attestation_reference text not null,
  status genesis_runtime.runtime_node_status not null default 'REGISTERED',
  capacity jsonb not null,
  registered_at timestamptz not null,
  updated_at timestamptz not null,
  check (jsonb_typeof(capacity) = 'object'),
  check ((capacity->>'cpu_millis')::bigint >= 0),
  check ((capacity->>'memory_mb')::bigint >= 0),
  check ((capacity->>'gpu_millis')::bigint >= 0),
  check ((capacity->>'storage_mb')::bigint >= 0),
  check ((capacity->>'network_egress_mb')::bigint >= 0),
  check ((capacity->>'browser_slots')::bigint >= 0)
);

create table genesis_runtime.runtime_instances (
  instance_id text primary key,
  node_id text not null references genesis_runtime.runtime_nodes(node_id),
  box_id text not null references public.actor_boxes(box_id),
  runtime_class text not null,
  runtime_version text not null,
  status genesis_runtime.runtime_instance_status not null default 'PROVISIONING',
  integrity_status public.runtime_integrity_status not null default 'UNKNOWN',
  resource_limits jsonb not null,
  attestation_reference text,
  provisioned_at timestamptz not null,
  activated_at timestamptz,
  last_attested_at timestamptz,
  updated_at timestamptz not null,
  check (jsonb_typeof(resource_limits) = 'object'),
  check (activated_at is null or activated_at >= provisioned_at),
  check (last_attested_at is null or last_attested_at >= provisioned_at)
);

create index runtime_instances_node_status_lookup
  on genesis_runtime.runtime_instances (node_id, status, instance_id);
create index runtime_instances_box_lookup
  on genesis_runtime.runtime_instances (box_id, status, instance_id);

create table genesis_runtime.runtime_sessions (
  session_id text primary key,
  instance_id text not null references genesis_runtime.runtime_instances(instance_id),
  box_id text not null references public.actor_boxes(box_id),
  principal_id text not null,
  context_id text not null references public.box_contexts(context_id),
  capability_id text not null references public.capability_grants(capability_id),
  session_type genesis_runtime.runtime_session_type not null,
  purpose text not null,
  status genesis_runtime.runtime_session_status not null default 'ACTIVE',
  started_at timestamptz not null,
  expires_at timestamptz not null,
  terminated_at timestamptz,
  termination_reason text,
  updated_at timestamptz not null,
  check (expires_at > started_at),
  check (terminated_at is null or terminated_at >= started_at)
);

create index runtime_sessions_instance_lookup
  on genesis_runtime.runtime_sessions (instance_id, status, expires_at);
create index runtime_sessions_box_principal_lookup
  on genesis_runtime.runtime_sessions (box_id, principal_id, status, expires_at);

create table genesis_runtime.runtime_resource_allocations (
  allocation_id text primary key,
  session_id text not null references genesis_runtime.runtime_sessions(session_id),
  capability_id text not null references public.capability_grants(capability_id),
  resources jsonb not null,
  status genesis_runtime.runtime_allocation_status not null default 'ACTIVE',
  allocated_at timestamptz not null,
  released_at timestamptz,
  check (jsonb_typeof(resources) = 'object'),
  check (released_at is null or released_at >= allocated_at)
);

create index runtime_allocations_session_lookup
  on genesis_runtime.runtime_resource_allocations (session_id, status, allocated_at);

create table genesis_runtime.runtime_health_reports (
  health_report_id text primary key,
  instance_id text not null references genesis_runtime.runtime_instances(instance_id),
  state genesis_runtime.runtime_health_state not null,
  reported_by text not null,
  checks jsonb not null default '{}'::jsonb,
  metrics jsonb not null default '{}'::jsonb,
  reported_at timestamptz not null,
  check (jsonb_typeof(checks) = 'object'),
  check (jsonb_typeof(metrics) = 'object')
);

create index runtime_health_instance_lookup
  on genesis_runtime.runtime_health_reports (instance_id, reported_at desc, health_report_id desc);

create table genesis_runtime.runtime_recovery_jobs (
  recovery_job_id text primary key,
  instance_id text not null references genesis_runtime.runtime_instances(instance_id),
  status genesis_runtime.runtime_recovery_status not null,
  trigger_health_report_id text not null references genesis_runtime.runtime_health_reports(health_report_id),
  required_capability_action text not null default 'RUNTIME_RECOVERY_EXECUTE',
  authorization_capability_id text references public.capability_grants(capability_id),
  created_at timestamptz not null,
  authorized_at timestamptz,
  started_at timestamptz,
  completed_at timestamptz,
  check (authorized_at is null or authorized_at >= created_at),
  check (started_at is null or authorized_at is not null),
  check (completed_at is null or started_at is not null)
);

create index runtime_recovery_pending_lookup
  on genesis_runtime.runtime_recovery_jobs (status, created_at, recovery_job_id);

create table genesis_runtime.runtime_events (
  event_id text primary key,
  aggregate_type text not null,
  aggregate_id text not null,
  box_id text references public.actor_boxes(box_id),
  event_type text not null,
  payload jsonb not null,
  occurred_at timestamptz not null,
  previous_event_hash text,
  evidence_hash text not null unique,
  published_at timestamptz,
  publication_attempts integer not null default 0 check (publication_attempts >= 0),
  created_at timestamptz not null default now(),
  check (jsonb_typeof(payload) = 'object')
);

create index runtime_events_chain_lookup
  on genesis_runtime.runtime_events (
    aggregate_type, aggregate_id, occurred_at desc, event_id desc
  );
create index runtime_events_outbox_lookup
  on genesis_runtime.runtime_events (published_at, occurred_at, event_id)
  where published_at is null;

revoke all on all tables in schema genesis_runtime from public, anon, authenticated;

alter table genesis_runtime.runtime_nodes enable row level security;
alter table genesis_runtime.runtime_instances enable row level security;
alter table genesis_runtime.runtime_sessions enable row level security;
alter table genesis_runtime.runtime_resource_allocations enable row level security;
alter table genesis_runtime.runtime_health_reports enable row level security;
alter table genesis_runtime.runtime_recovery_jobs enable row level security;
alter table genesis_runtime.runtime_events enable row level security;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'genesis_control_plane') then
    create role genesis_control_plane nologin;
  end if;
end
$$;

grant usage on schema genesis_runtime to genesis_control_plane;
grant usage on all types in schema genesis_runtime to genesis_control_plane;
grant select, insert, update on all tables in schema genesis_runtime to genesis_control_plane;

create policy genesis_control_plane_runtime_nodes
  on genesis_runtime.runtime_nodes for all to genesis_control_plane
  using (true) with check (true);
create policy genesis_control_plane_runtime_instances
  on genesis_runtime.runtime_instances for all to genesis_control_plane
  using (true) with check (true);
create policy genesis_control_plane_runtime_sessions
  on genesis_runtime.runtime_sessions for all to genesis_control_plane
  using (true) with check (true);
create policy genesis_control_plane_runtime_allocations
  on genesis_runtime.runtime_resource_allocations for all to genesis_control_plane
  using (true) with check (true);
create policy genesis_control_plane_runtime_health
  on genesis_runtime.runtime_health_reports for all to genesis_control_plane
  using (true) with check (true);
create policy genesis_control_plane_runtime_recovery
  on genesis_runtime.runtime_recovery_jobs for all to genesis_control_plane
  using (true) with check (true);
create policy genesis_control_plane_runtime_events
  on genesis_runtime.runtime_events for all to genesis_control_plane
  using (true) with check (true);

create view genesis_runtime.active_runtime_sessions
with (security_invoker = true) as
select s.*
from genesis_runtime.runtime_sessions s
join genesis_runtime.runtime_instances i on i.instance_id = s.instance_id
join public.actor_boxes b on b.box_id = s.box_id
join public.box_contexts x on x.context_id = s.context_id and x.box_id = s.box_id
join public.active_capability_grants c on c.capability_id = s.capability_id
where s.status = 'ACTIVE'
  and s.started_at <= now()
  and s.expires_at > now()
  and i.status = 'ACTIVE'
  and i.integrity_status = 'ATTESTED'
  and b.current_status in ('ACTIVE', 'RESTRICTED')
  and not b.is_locked
  and x.context_status = 'ACTIVE';

revoke all on genesis_runtime.active_runtime_sessions from public, anon, authenticated;
grant select on genesis_runtime.active_runtime_sessions to genesis_control_plane;

commit;
