-- Genesis authoritative Warden + CloudBrowser runtime hardening
-- Apply after 001_actor_box_foundation.sql and 002_cloud_browser_foundation.sql.

begin;

alter table actor_boxes
  add column if not exists is_locked boolean not null default false,
  add column if not exists locked_at timestamptz,
  add column if not exists lock_reason text;

alter table warden_policy_profiles
  add column if not exists profile_status control_object_status not null default 'ACTIVE',
  add column if not exists max_capability_ttl_seconds integer not null default 1200
    check (max_capability_ttl_seconds between 1 and 3600);

alter table delegated_agents
  add column if not exists write_requires_human_approval boolean not null default true;

alter table box_evidence_events
  alter column policy_decision type text using policy_decision::text;

alter table cloud_browser_actions
  alter column request_payload set default '{}'::jsonb;

create table if not exists warden_unbound_evidence_events (
  event_id text primary key,
  box_id text not null,
  actor_id text not null,
  agent_id text,
  context_id text,
  event_type text not null,
  action_reference text not null,
  policy_decision text not null,
  event_timestamp timestamptz not null,
  evidence_hash text not null unique,
  previous_event_hash text,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  check (jsonb_typeof(payload) = 'object')
);

create table if not exists warden_unbound_decisions (
  policy_decision_id text primary key,
  request_id text not null unique,
  box_id text not null,
  outcome warden_decision_outcome not null,
  reason_codes jsonb not null,
  policy_bundle_version text not null,
  requested_at timestamptz not null,
  decided_at timestamptz not null,
  evidence_event_id text not null references warden_unbound_evidence_events(event_id),
  request_payload jsonb not null,
  decision_payload jsonb not null,
  created_at timestamptz not null default now(),
  check (jsonb_typeof(reason_codes) = 'array'),
  check (decided_at >= requested_at)
);

create index if not exists warden_unbound_evidence_latest_lookup
  on warden_unbound_evidence_events (box_id, event_timestamp desc, event_id desc);
create index if not exists box_evidence_latest_lookup
  on box_evidence_events (box_id, event_timestamp desc, event_id desc);
create index if not exists cloud_browser_evidence_latest_lookup
  on cloud_browser_evidence_events (browser_session_id, occurred_at desc, event_id desc);

revoke all on table
  actor_boxes,
  actor_box_bindings,
  box_runtimes,
  box_contexts,
  warden_policy_profiles,
  consent_receipts,
  delegated_agents,
  warden_policy_decisions,
  capability_grants,
  data_boundary_rules,
  box_evidence_events,
  box_revocations,
  box_recovery_authorities,
  warden_unbound_evidence_events,
  warden_unbound_decisions,
  cloud_browser_policies,
  cloud_browser_sessions,
  cloud_browser_actions,
  cloud_browser_approvals,
  cloud_browser_usage,
  cloud_browser_evidence_events
from anon, authenticated;

alter table actor_boxes enable row level security;
alter table actor_box_bindings enable row level security;
alter table box_runtimes enable row level security;
alter table box_contexts enable row level security;
alter table warden_policy_profiles enable row level security;
alter table consent_receipts enable row level security;
alter table delegated_agents enable row level security;
alter table warden_policy_decisions enable row level security;
alter table capability_grants enable row level security;
alter table data_boundary_rules enable row level security;
alter table box_evidence_events enable row level security;
alter table box_revocations enable row level security;
alter table box_recovery_authorities enable row level security;
alter table warden_unbound_evidence_events enable row level security;
alter table warden_unbound_decisions enable row level security;
alter table cloud_browser_policies enable row level security;
alter table cloud_browser_sessions enable row level security;
alter table cloud_browser_actions enable row level security;
alter table cloud_browser_approvals enable row level security;
alter table cloud_browser_usage enable row level security;
alter table cloud_browser_evidence_events enable row level security;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'genesis_control_plane') then
    create role genesis_control_plane nologin;
  end if;
end
$$;

grant usage on schema public to genesis_control_plane;
grant usage on type
  actor_box_status,
  actor_box_type,
  actor_box_context_type,
  warden_decision_outcome,
  control_object_status,
  capability_status,
  runtime_integrity_status,
  cloud_browser_session_status,
  cloud_browser_action_decision
to genesis_control_plane;

grant select on table
  actor_boxes, actor_box_bindings, box_runtimes, box_contexts, warden_policy_profiles, consent_receipts, delegated_agents, warden_policy_decisions, capability_grants, data_boundary_rules, box_evidence_events, box_revocations, box_recovery_authorities, warden_unbound_evidence_events, warden_unbound_decisions, cloud_browser_policies, cloud_browser_sessions, cloud_browser_actions, cloud_browser_approvals, cloud_browser_usage, cloud_browser_evidence_events
to genesis_control_plane;

grant insert on table
  warden_policy_decisions,
  capability_grants,
  box_evidence_events,
  box_revocations,
  warden_unbound_evidence_events,
  warden_unbound_decisions,
  cloud_browser_sessions,
  cloud_browser_actions,
  cloud_browser_approvals,
  cloud_browser_usage,
  cloud_browser_evidence_events
to genesis_control_plane;

grant update on table
  actor_boxes,
  capability_grants,
  cloud_browser_sessions,
  cloud_browser_actions,
  cloud_browser_usage
to genesis_control_plane;

drop policy if exists genesis_control_plane_internal_access on actor_boxes;
create policy genesis_control_plane_internal_access on actor_boxes for all to genesis_control_plane using (true) with check (true);
drop policy if exists genesis_control_plane_internal_access on actor_box_bindings;
create policy genesis_control_plane_internal_access on actor_box_bindings for all to genesis_control_plane using (true) with check (true);
drop policy if exists genesis_control_plane_internal_access on box_runtimes;
create policy genesis_control_plane_internal_access on box_runtimes for all to genesis_control_plane using (true) with check (true);
drop policy if exists genesis_control_plane_internal_access on box_contexts;
create policy genesis_control_plane_internal_access on box_contexts for all to genesis_control_plane using (true) with check (true);
drop policy if exists genesis_control_plane_internal_access on warden_policy_profiles;
create policy genesis_control_plane_internal_access on warden_policy_profiles for all to genesis_control_plane using (true) with check (true);
drop policy if exists genesis_control_plane_internal_access on consent_receipts;
create policy genesis_control_plane_internal_access on consent_receipts for all to genesis_control_plane using (true) with check (true);
drop policy if exists genesis_control_plane_internal_access on delegated_agents;
create policy genesis_control_plane_internal_access on delegated_agents for all to genesis_control_plane using (true) with check (true);
drop policy if exists genesis_control_plane_internal_access on warden_policy_decisions;
create policy genesis_control_plane_internal_access on warden_policy_decisions for all to genesis_control_plane using (true) with check (true);
drop policy if exists genesis_control_plane_internal_access on capability_grants;
create policy genesis_control_plane_internal_access on capability_grants for all to genesis_control_plane using (true) with check (true);
drop policy if exists genesis_control_plane_internal_access on data_boundary_rules;
create policy genesis_control_plane_internal_access on data_boundary_rules for all to genesis_control_plane using (true) with check (true);
drop policy if exists genesis_control_plane_internal_access on box_evidence_events;
create policy genesis_control_plane_internal_access on box_evidence_events for all to genesis_control_plane using (true) with check (true);
drop policy if exists genesis_control_plane_internal_access on box_revocations;
create policy genesis_control_plane_internal_access on box_revocations for all to genesis_control_plane using (true) with check (true);
drop policy if exists genesis_control_plane_internal_access on box_recovery_authorities;
create policy genesis_control_plane_internal_access on box_recovery_authorities for all to genesis_control_plane using (true) with check (true);
drop policy if exists genesis_control_plane_internal_access on warden_unbound_evidence_events;
create policy genesis_control_plane_internal_access on warden_unbound_evidence_events for all to genesis_control_plane using (true) with check (true);
drop policy if exists genesis_control_plane_internal_access on warden_unbound_decisions;
create policy genesis_control_plane_internal_access on warden_unbound_decisions for all to genesis_control_plane using (true) with check (true);
drop policy if exists genesis_control_plane_internal_access on cloud_browser_policies;
create policy genesis_control_plane_internal_access on cloud_browser_policies for all to genesis_control_plane using (true) with check (true);
drop policy if exists genesis_control_plane_internal_access on cloud_browser_sessions;
create policy genesis_control_plane_internal_access on cloud_browser_sessions for all to genesis_control_plane using (true) with check (true);
drop policy if exists genesis_control_plane_internal_access on cloud_browser_actions;
create policy genesis_control_plane_internal_access on cloud_browser_actions for all to genesis_control_plane using (true) with check (true);
drop policy if exists genesis_control_plane_internal_access on cloud_browser_approvals;
create policy genesis_control_plane_internal_access on cloud_browser_approvals for all to genesis_control_plane using (true) with check (true);
drop policy if exists genesis_control_plane_internal_access on cloud_browser_usage;
create policy genesis_control_plane_internal_access on cloud_browser_usage for all to genesis_control_plane using (true) with check (true);
drop policy if exists genesis_control_plane_internal_access on cloud_browser_evidence_events;
create policy genesis_control_plane_internal_access on cloud_browser_evidence_events for all to genesis_control_plane using (true) with check (true);

drop view if exists active_cloud_browser_sessions;
create view active_cloud_browser_sessions with (security_invoker = true) as
select s.*
from cloud_browser_sessions s
join actor_boxes b on b.box_id = s.box_id
join capability_grants c on c.capability_id = s.capability_id
where s.session_status = 'ACTIVE'
  and s.started_at <= now()
  and s.expires_at > now()
  and b.current_status in ('ACTIVE', 'RESTRICTED')
  and not b.is_locked
  and c.capability_status = 'ISSUED'
  and c.expires_at > now()
  and not exists (
    select 1 from box_revocations r
    where r.target_id in (s.browser_session_id, s.capability_id, s.box_id)
      and r.effective_at <= now()
  );
revoke all on active_cloud_browser_sessions from anon, authenticated;
grant select on active_cloud_browser_sessions to genesis_control_plane;

drop view if exists active_capability_grants;
create view active_capability_grants with (security_invoker = true) as
select c.*
from capability_grants c
join actor_boxes b on b.box_id = c.box_id
join box_contexts x on x.context_id = c.context_id and x.box_id = c.box_id
join warden_policy_decisions d on d.policy_decision_id = c.policy_decision_id
where c.capability_status = 'ISSUED'
  and c.expires_at > now()
  and b.current_status in ('ACTIVE', 'RESTRICTED')
  and not b.is_locked
  and x.context_status = 'ACTIVE'
  and d.outcome in ('ALLOW', 'RESTRICT')
  and not exists (
    select 1 from box_revocations r
    where r.effective_at <= now()
      and (
        (r.target_type = 'BOX' and r.target_id = c.box_id)
        or (r.target_type = 'CAPABILITY' and r.target_id = c.capability_id)
        or (r.target_type = 'CONTEXT' and r.target_id = c.context_id)
      )
  );
revoke all on active_capability_grants from anon, authenticated;
grant select on active_capability_grants to genesis_control_plane;

commit;
