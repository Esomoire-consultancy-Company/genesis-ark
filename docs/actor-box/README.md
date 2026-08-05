# Warden-Enabled Actor Box by Genesis

Status: **Foundation contract v1**

The Warden-Enabled Actor Box is the governed execution unit of the Genesis Stack. Genesis provisions and secures the runtime; DigitalMe identifies the principal; Warden evaluates consent, authority, delegation, data boundaries, lifecycle and revocation; the VSR Registry stores authoritative control state; RiverOS preserves evidence.

## Binding invariants

1. A Box cannot become `ACTIVE` without a valid DigitalMe binding and an attested Genesis runtime.
2. Every material application or agent action must receive a narrow, short-lived capability from Warden.
3. Capabilities are bound to one Box, subject, context, resource, action and purpose.
4. Personal, organisation, licence, Arc and temporary contexts remain explicit and separable.
5. Consent, delegation, lifecycle and Sentinel Clock state are evaluated at decision time.
6. Cross-zone data movement is denied unless a matching active boundary rule exists.
7. Revocation takes precedence over earlier consent, delegation or capability issuance.
8. Every material decision and execution result emits a RiverOS evidence event.
9. Genesis administration does not imply Actor impersonation, data ownership or transaction authority.
10. Emergency controls preserve evidence.

## Foundation artifacts

- `schemas/actor-box/v1/actor-box.schema.json` — canonical JSON Schema bundle for Actor Box control objects.
- `openapi/warden/v1/openapi.yaml` — Warden decision, capability, revocation and Box-lock contract.
- `db/actor-box/v1/001_actor_box_foundation.sql` — PostgreSQL/Supabase-compatible registry foundation.
- `examples/actor-box/v1/` — representative request, decision and Box objects.
- `scripts/validate_actor_box_contracts.py` — offline structural and example validation.

## First vertical slice

```text
Genesis runtime attestation
        ↓
DigitalMe principal + representation context
        ↓
Warden policy evaluation
        ↓
Short-lived capability issuance
        ↓
Bounded application or agent action
        ↓
RiverOS evidence event
        ↓
VSR Registry state update
```

## Decision outcomes

Warden returns exactly one of:

- `ALLOW` — action may execute under the issued capability;
- `DENY` — action must not execute;
- `RESTRICT` — only the returned reduced scope may execute;
- `ESCALATE` — human or higher-authority approval is required.

## Deliberately excluded from foundation v1

- unrestricted third-party application installation;
- broad or permanent OAuth scopes;
- silent background sensor access;
- automatic cross-workspace data reuse;
- production deployment manifests;
- settlement execution;
- organisation transfer workflows beyond the registry objects required to support them.

## Acceptance checks

The foundation is structurally valid when:

- the JSON Schema parses and validates the supplied examples;
- the OpenAPI document parses as OpenAPI 3.1;
- every OpenAPI operation has an operation ID and security declaration;
- the database script declares all canonical foundation tables;
- example capability expiry is later than issuance;
- deny-by-default behavior is visible in the API contract.
