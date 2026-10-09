# R0.10 — Governed Deployment Execution (Isolated Laboratory)

**Status: implemented lab-only state machine; not a production or staging deployment executor.**

## Runtime contract
R0.8 provides signed provider-review evidence; R0.9 produces RELEASE_REVIEW_READY only after release-review checks. R0.10's `createLabDeploymentExecutor` re-assesses the R0.9 packet on every invocation, rejects all non-lab environments and hard-denies A-1204. It separately verifies two short-lived Ed25519 assertions: **Warden** and **ReleaseOwner** both must issue `APPROVE_LAB_CANARY` with the same plan digest, release SHA, deployment ID, tenant/asset scope, operator, and nonce. A one-use nonce claim is required before simulation.

`createInMemoryLabDriver` is deliberately **not a real deployment transport**. Its canary/health/rollback methods mutate only a private in-process object, never containers, DNS, infrastructure, hosts, routers, user devices, agents, or external accounts. Driver capability marking prevents substituting arbitrary provider modules through the API; this is not a substitute for process sandboxing. The driver event log uses `LAB_EVENTS_ONLY` and is **not River evidence**.

## State transitions
```
PENDING_AUTHORIZATION → LAB_CANARY_SIMULATED → CANARY_HEALTHY_SIMULATED
                                       └─ health/deploy exception → ROLLED_BACK_SIMULATED
                                                                └─ rollback uncertain → ESCALATION_REQUIRED_SIMULATED
```
Both success and failure report `deployment_activated=false`, `operations_enabled=false`, and `public_qr_enabled=false`.

## Security and assurance limitations
- Only isolated `environment=lab` packets are accepted; no override for A-1204 or production in this revision.
- Even perfect issuer signatures in CI are **ephemeral lab test keys**, not estate authority.
- The nonce store supplied in tests is process-memory and must never be used for a deployed execution system. A future production executor requires durable atomic leases, idempotent recovery and signed workload identity.
- No actual canary routing, real runtime health, rollback, monitoring subscription, webhooks, River persistence, credentials, or deployment API is exercised.
- Signature byte conventions and trust-root rotation require ratification before multi-language real-world integration.
- Rollback exceptions are surfaced as escalation; the system cannot guarantee a real action was recovered.
- No property entitlements, titles, customer records, private browser sessions, personal device data or real payment systems are handled.
- **All costs are depiction-only examples, not verified commercial values.**

## Validation
`node arks/bmp/scripts/validate-lab-execution.mjs` is run by the BMP fixture CI. Tests require valid separate signatures, same-release scope, one-time nonce, lab-only asset and clean release review; they also simulate canary health and rollback failures.

## Next governance gate
R0.11 should define a **production deployment adapter specification** and a read-only cross-host topology inventory, including durable replay store, certificate/DNS/egress restrictions, release lock, policy checks, independent health/rollback evidence and a separate explicit human deployment consent. It must not silently enable this lab executor on a real host.
