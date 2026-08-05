-- Warden-Enabled Actor Box by Genesis
-- Foundation registry schema v1
-- PostgreSQL / Supabase compatible. IDs are caller-generated canonical text IDs.

begin;

create type actor_box_status as enum (
  'RESERVED',
  'PROVISIONED',
  'CLAIM_PENDING',
  'CLAIMED',
  'ACTIVE',
  'RESTRICTED',
  'SUSPENDED',
  'RECOVERY',
  'TRANSFER_PENDING',
  'COMPROMISED',
  'REVOKED',
  'RETIREMENT_PENDING',
  'RETIRED'
);

create type actor_box_type as enum ('PERSONAL', 'ORGANISATION', 'EDGE', 'AGENT');
create type actor_box_context_type as enum ('PERSONAL', 'ORGANISATION', 'LICENCE', 'ARC', 'TEMPORARY');
create type warden_decision_outcome as enum ('ALLOW', 'DENY', 'RESTRICT', 'ESCALATE');
create type control_object_status as enum ('PENDING', 'ACTIVE', 'SUSPENDED', 'REVOKED', 'EXPIRED');
create type capability_status as enum ('ISSUED', 'CONSUMED', 'EXPIRED', 'REVOKED', 'SUSPENDED');
create type runtime_integrity_status as enum ('ATTESTED', 'DEGRADED', 'FAILED', 'UNKNOWN');

create table actor_boxes (
  box_id text primary key,
  box_type actor_box_type not null,
  genesis_runtime_id text not null unique,
  current_status actor_box_status not null default 'RESERVED',
  policy_profile_id text not null,
  evidence_stream_id text not null,
  sentinel_clock_id text not null,
  provisioned_at timestamptz not null,
  claimed_at timestamptz,
  activated_at timestamptz,
  retired_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (retired_at is null or retired_at >= provisioned_at),
  check (activated_at is null or claimed_at is not null)
);

create table actor_box_bindings (
  binding_id text primary key,
  box_id text not null references actor_boxes(box_id),
  digitalme_id text not null,
  represented_entity_id text,
  relationship_type text not null,
  binding_authority_id text not null,
  binding_status control_object_status not null default 'PENDING',
  effective_from timestamptz not null,
  effective_until timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  check (effective_until is null or effective_until > effective_from),
  check (revoked_at is null or revoked_at >= effective_from)
);

create unique index actor_box_one_active_personal_binding
  on actor_box_bindings (box_id, digitalme_id)
  where binding_status = 'ACTIVE';

create table box_runtimes (
  runtime_id text primary key,
  box_id text not null references actor_boxes(box_id),
  device_id text not null,
  runtime_type text not null,
  hardware_attestation text not null,
  software_version text not null,
  security_patch_level text not null,
  integrity_status runtime_integrity_status not null default 'UNKNOWN',
  last_attested_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (box_id, device_id)
);

create table box_contexts (
  context_id text primary key,
  box_id text not null references actor_boxes(box_id),
  context_type actor_box_context_type not null,
  principal_id text not null,
  represented_entity_id text,
  workspace_id text not null,
  licence_id text,
  arc_id text,
  activated_at timestamptz not null,
  expires_at timestamptz,
  context_status control_object_status not null default 'ACTIVE',
  created_at timestamptz not null default now(),
  check (expires_at is null or expires_at > activated_at),
  check (context_type <> 'ORGANISATION' or represented_entity_id is not null),
  check (context_type <> 'LICENCE' or licence_id is not null),
  check (context_type <> 'ARC' or arc_id is not null)
);

create unique index actor_box_one_active_context
  on box_contexts (box_id)
  where context_status = 'ACTIVE';

create table warden_policy_profiles (
  policy_profile_id text primary key,
  box_id text not null references actor_boxes(box_id),
  policy_bundle_version text not null,
  safe_space_profile text not null,
  data_boundary_profile text not null,
  agent_policy_profile text not null,
  connector_policy_profile text not null,
  effective_from timestamptz not null,
  effective_until timestamptz,
  review_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  check (effective_until is null or effective_until > effective_from),
  check (review_at is null or review_at >= effective_from)
);

alter table actor_boxes
  add constraint actor_boxes_policy_profile_fk
  foreign key (policy_profile_id)
  references warden_policy_profiles(policy_profile_id)
  deferrable initially deferred;

create table consent_receipts (
  consent_receipt_id text primary key,
  box_id text not null references actor_boxes(box_id),
  digitalme_id text not null,
  product_id text not null,
  purpose text not null,
  data_scope jsonb not null,
  action_scope jsonb not null,
  revocation_method text not null,
  receipt_status text not null check (receipt_status in ('ACTIVE', 'REVOKED', 'EXPIRED', 'SUPERSEDED')),
  evidence_event_id text not null,
  effective_from timestamptz not null,
  effective_until timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  check (jsonb_typeof(data_scope) = 'array'),
  check (jsonb_typeof(action_scope) = 'array'),
  check (effective_until is null or effective_until > effective_from)
);

create table delegated_agents (
  delegation_id text primary key,
  box_id text not null references actor_boxes(box_id),
  agent_id text not null,
  delegating_principal_id text not null,
  represented_entity_id text,
  permitted_actions jsonb not null,
  permitted_data_scope jsonb not null,
  workspace_scope jsonb not null,
  approval_threshold numeric(20, 4) not null default 0,
  delegation_status control_object_status not null default 'PENDING',
  effective_from timestamptz not null,
  effective_until timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  check (approval_threshold >= 0),
  check (jsonb_typeof(permitted_actions) = 'array'),
  check (jsonb_typeof(permitted_data_scope) = 'array'),
  check (jsonb_typeof(workspace_scope) = 'array'),
  check (effective_until is null or effective_until > effective_from)
);

create table warden_policy_decisions (
  policy_decision_id text primary key,
  request_id text not null unique,
  box_id text not null references actor_boxes(box_id),
  runtime_id text not null references box_runtimes(runtime_id),
  subject_id text not null,
  agent_id text,
  context_id text not null references box_contexts(context_id),
  resource_id text not null,
  requested_action text not null,
  purpose text not null,
  outcome warden_decision_outcome not null,
  reason_codes jsonb not null,
  policy_bundle_version text not null,
  requested_at timestamptz not null,
  decided_at timestamptz not null,
  evidence_event_id text not null,
  request_payload jsonb not null,
  decision_payload jsonb not null,
  check (decided_at >= requested_at),
  check (jsonb_typeof(reason_codes) = 'array')
);

create table capability_grants (
  capability_id text primary key,
  box_id text not null references actor_boxes(box_id),
  subject_id text not null,
  resource_id text not null,
  allowed_action text not null,
  purpose text not null,
  context_id text not null references box_contexts(context_id),
  issued_at timestamptz not null,
  expires_at timestamptz not null,
  policy_decision_id text not null references warden_policy_decisions(policy_decision_id),
  capability_status capability_status not null default 'ISSUED',
  constraints jsonb not null default '{}'::jsonb,
  consumed_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  check (expires_at > issued_at),
  check (jsonb_typeof(constraints) = 'object')
);

create index capability_active_lookup
  on capability_grants (box_id, subject_id, context_id, resource_id, allowed_action, expires_at)
  where capability_status = 'ISSUED';

create table data_boundary_rules (
  boundary_rule_id text primary key,
  box_id text not null references actor_boxes(box_id),
  source_zone text not null check (source_zone in ('PRIVATE_ACTOR', 'ORGANISATION', 'SHARED_WORKSPACE', 'EXTERNAL_PROVIDER', 'PUBLIC_REGISTRY')),
  destination_zone text not null check (destination_zone in ('PRIVATE_ACTOR', 'ORGANISATION', 'SHARED_WORKSPACE', 'EXTERNAL_PROVIDER', 'PUBLIC_REGISTRY')),
  data_class text not null,
  permitted_purpose text not null,
  permitted_connector text,
  retention_rule text not null,
  evidence_requirement text not null,
  approval_requirement text not null,
  rule_status control_object_status not null default 'ACTIVE',
  effective_from timestamptz not null,
  effective_until timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  check (source_zone <> destination_zone),
  check (effective_until is null or effective_until > effective_from)
);

create table box_evidence_events (
  event_id text primary key,
  box_id text not null references actor_boxes(box_id),
  actor_id text not null,
  agent_id text,
  context_id text references box_contexts(context_id),
  event_type text not null,
  action_reference text not null,
  policy_decision warden_decision_outcome not null,
  event_timestamp timestamptz not null,
  evidence_hash text not null unique,
  previous_event_hash text,
  custody_location text not null,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  check (length(evidence_hash) >= 32),
  check (previous_event_hash is null or length(previous_event_hash) >= 32),
  check (jsonb_typeof(payload) = 'object')
);

create index box_evidence_stream_order
  on box_evidence_events (box_id, event_timestamp, event_id);

create table box_revocations (
  revocation_id text primary key,
  box_id text not null references actor_boxes(box_id),
  target_type text not null check (target_type in ('BOX', 'RUNTIME', 'CONTEXT', 'CONSENT', 'DELEGATION', 'CAPABILITY', 'AGENT', 'WORKSPACE')),
  target_id text not null,
  reason text not null,
  revoked_by text not null,
  effective_at timestamptz not null,
  policy_reference text not null,
  evidence_event_id text not null references box_evidence_events(event_id),
  created_at timestamptz not null default now(),
  unique (target_type, target_id, effective_at)
);

create table box_recovery_authorities (
  recovery_authority_id text primary key,
  box_id text not null references actor_boxes(box_id),
  authority_type text not null,
  authority_principal_id text not null,
  recovery_scope jsonb not null,
  approval_threshold integer not null default 1,
  effective_from timestamptz not null,
  effective_until timestamptz,
  status control_object_status not null default 'ACTIVE',
  created_at timestamptz not null default now(),
  check (approval_threshold >= 1),
  check (jsonb_typeof(recovery_scope) = 'array'),
  check (effective_until is null or effective_until > effective_from)
);

-- Deny-by-default query surface: only presently effective, non-revoked capabilities qualify.
create view active_capability_grants as
select c.*
from capability_grants c
join actor_boxes b on b.box_id = c.box_id
join box_contexts x on x.context_id = c.context_id and x.box_id = c.box_id
join warden_policy_decisions d on d.policy_decision_id = c.policy_decision_id
where c.capability_status = 'ISSUED'
  and c.expires_at > now()
  and b.current_status in ('ACTIVE', 'RESTRICTED')
  and x.context_status = 'ACTIVE'
  and d.outcome in ('ALLOW', 'RESTRICT')
  and not exists (
    select 1
    from box_revocations r
    where r.effective_at <= now()
      and (
        (r.target_type = 'BOX' and r.target_id = c.box_id)
        or (r.target_type = 'CAPABILITY' and r.target_id = c.capability_id)
        or (r.target_type = 'CONTEXT' and r.target_id = c.context_id)
      )
  );

commit;
