-- Genesis Governed CloudBrowser
-- Registry foundation v1; depends on Actor Box foundation migration 001.

begin;

create type cloud_browser_session_status as enum (
  'REQUESTED', 'ACTIVE', 'PAUSED', 'TERMINATED', 'EXPIRED', 'LOCKED'
);

create type cloud_browser_action_decision as enum (
  'ALLOW', 'DENY', 'APPROVAL_REQUIRED', 'APPROVED', 'EXECUTED'
);

create table cloud_browser_policies (
  policy_id text primary key,
  allowed_domains jsonb not null,
  allowed_actions jsonb not null,
  high_impact_actions jsonb not null default '[]'::jsonb,
  allow_uploads boolean not null default false,
  allow_downloads boolean not null default false,
  allow_clipboard boolean not null default false,
  allow_credentials boolean not null default false,
  allow_screen_capture boolean not null default false,
  allow_sensors boolean not null default false,
  max_file_bytes bigint not null default 10000000 check (max_file_bytes >= 0),
  effective_from timestamptz not null default now(),
  effective_until timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  check (jsonb_typeof(allowed_domains) = 'array'),
  check (jsonb_array_length(allowed_domains) > 0),
  check (jsonb_typeof(allowed_actions) = 'array'),
  check (jsonb_array_length(allowed_actions) > 0),
  check (jsonb_typeof(high_impact_actions) = 'array'),
  check (effective_until is null or effective_until > effective_from)
);

create table cloud_browser_sessions (
  browser_session_id text primary key,
  box_id text not null references actor_boxes(box_id),
  digitalme_id text not null,
  agent_id text,
  context_id text not null references box_contexts(context_id),
  workspace_id text not null,
  licence_id text,
  runtime_id text not null references box_runtimes(runtime_id),
  policy_id text not null references cloud_browser_policies(policy_id),
  policy_decision_id text not null references warden_policy_decisions(policy_decision_id),
  capability_id text not null references capability_grants(capability_id),
  session_status cloud_browser_session_status not null default 'REQUESTED',
  isolation_profile text not null,
  started_at timestamptz not null,
  expires_at timestamptz not null,
  terminated_at timestamptz,
  evidence_stream_id text not null unique,
  compute_meter_id text not null unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (expires_at > started_at),
  check (terminated_at is null or terminated_at >= started_at)
);

create index cloud_browser_session_actor_lookup
  on cloud_browser_sessions (box_id, digitalme_id, session_status, expires_at);

create table cloud_browser_actions (
  action_id text primary key,
  browser_session_id text not null references cloud_browser_sessions(browser_session_id),
  action_type text not null,
  decision cloud_browser_action_decision not null,
  reason_codes jsonb not null,
  target_url text,
  warden_policy_decision_id text references warden_policy_decisions(policy_decision_id),
  capability_id text references capability_grants(capability_id),
  approval_id text,
  request_payload jsonb not null,
  result_payload jsonb,
  requested_at timestamptz not null,
  decided_at timestamptz not null,
  executed_at timestamptz,
  evidence_event_id text not null,
  created_at timestamptz not null default now(),
  check (jsonb_typeof(reason_codes) = 'array'),
  check (decided_at >= requested_at),
  check (executed_at is null or executed_at >= decided_at)
);

create index cloud_browser_action_session_lookup
  on cloud_browser_actions (browser_session_id, requested_at desc);

create table cloud_browser_approvals (
  approval_id text primary key,
  browser_session_id text not null references cloud_browser_sessions(browser_session_id),
  action_id text not null unique references cloud_browser_actions(action_id),
  approved_by text not null,
  approval_reason text not null,
  approved_at timestamptz not null,
  expires_at timestamptz not null,
  evidence_event_id text not null,
  created_at timestamptz not null default now(),
  check (expires_at > approved_at)
);

alter table cloud_browser_actions
  add constraint cloud_browser_action_approval_fk
  foreign key (approval_id)
  references cloud_browser_approvals(approval_id)
  deferrable initially deferred;

create table cloud_browser_usage (
  compute_meter_id text primary key,
  browser_session_id text not null unique references cloud_browser_sessions(browser_session_id),
  runtime_seconds bigint not null default 0 check (runtime_seconds >= 0),
  action_count bigint not null default 0 check (action_count >= 0),
  approval_count bigint not null default 0 check (approval_count >= 0),
  connector_calls bigint not null default 0 check (connector_calls >= 0),
  uploaded_bytes bigint not null default 0 check (uploaded_bytes >= 0),
  downloaded_bytes bigint not null default 0 check (downloaded_bytes >= 0),
  network_bytes bigint not null default 0 check (network_bytes >= 0),
  compute_units numeric(20, 6) not null default 0 check (compute_units >= 0),
  updated_at timestamptz not null default now()
);

create table cloud_browser_evidence_events (
  event_id text primary key,
  browser_session_id text not null references cloud_browser_sessions(browser_session_id),
  box_id text not null references actor_boxes(box_id),
  event_type text not null,
  actor_id text not null,
  action_reference text not null,
  occurred_at timestamptz not null,
  payload jsonb not null,
  previous_event_hash text,
  evidence_hash text not null unique,
  created_at timestamptz not null default now(),
  check (jsonb_typeof(payload) = 'object')
);

create index cloud_browser_evidence_chain_lookup
  on cloud_browser_evidence_events (browser_session_id, occurred_at, event_id);

create view active_cloud_browser_sessions as
select s.*
from cloud_browser_sessions s
join actor_boxes b on b.box_id = s.box_id
join capability_grants c on c.capability_id = s.capability_id
where s.session_status = 'ACTIVE'
  and s.started_at <= now()
  and s.expires_at > now()
  and b.current_status in ('ACTIVE', 'RESTRICTED')
  and c.capability_status = 'ISSUED'
  and c.expires_at > now()
  and not exists (
    select 1
    from box_revocations r
    where r.target_id in (s.browser_session_id, s.capability_id, s.box_id)
      and r.effective_at <= now()
  );

commit;
