# R0.9 — Deployment Admission and Runtime Assurance

**Status:** read-only, source-controlled acceptance contract with laboratory-signed attestations. No production deployment, live health checks, credentials, monitoring subscription, A-1204 admission, QR activation, or property authorization has been performed.

## Source-of-truth chain

R0.8 can declare a **provider packet** `REVIEW_READY`. R0.9 evaluates a separate **release-review packet**. It re-invokes the injected R0.8 provider gate and verifies its report against the actual provider packet's digest. A free-text or client-provided `REVIEW_READY` field has no standing.

R0.9 binds the following to one SHA-256 release-plan digest: release commit SHA, proposed deployment ID, tenant, asset, environment, artifact SHA-256, distinct rollback artifact SHA-256, canary plan (initial 1–10%), operator and runbook, provider-manifest digest and proposed evidence references. The current JSON signature byte convention is inherited from R0.8 and is not cross-language ratified.

## Signed attestations for technical review

Three *independently named* attestors must sign the same release digest:
- **RuntimeProbe:** recent `HEALTHY` assertion plus `readiness`, `denial_behavior`, `health`, `error_budget`, `telemetry_stream` checks.
- **RollbackOperator:** recent `DRILL_PASSED` assertion bound to the exact rollback artifact and rollback operator.
- **Monitor:** recent `ACTIVE` assertion including a tested alert route and enabled error-budget guard.

Three reviewers — **Warden**, **BNR**, and **ReleaseOwner** — independently sign `APPROVE_FOR_REVIEW` decisions. Their assertions are not deployment commands. Actual evidence references are checked via an injected trusted River retrieval/verifier, never inferred from a string alone.

The gate itself does not perform health probes, publish a deployment, activate monitoring or verify a physical property. A signed issuer assertion must be corroborated by separately observed and retained evidence before operational signoff.

## Release outcomes

`BLOCKED` reports unresolved conditions. `RELEASE_REVIEW_READY` means the lab-defined signed-review conditions have passed; **it is not a go-live decision**. Every result has:
- `operations_enabled=false`
- `public_qr_enabled=false`
- `deployment_activated=false`
- `booking_confirmed=false`
- `monetary_values=DEPICTION_ONLY`

A-1204 is hard-denied even if every other laboratory criterion passes. Its proposed prices, component values, taxes, fees and bundle totals remain illustrative presentation examples and must not be treated as verified financial figures.

## Local verification (from repository root)

```bash
node arks/bmp/scripts/validate-release-assurance.mjs
node arks/bmp/scripts/release-preflight.mjs
node arks/bmp/scripts/release-preflight.mjs --require-ready
```

The supplied static packet is deliberately expired and tied to the unverified A-1204 reference asset; the final command is expected to exit nonzero.

## Production prerequisites

An independently authorized release owner must supply verified trust roots, key revocation, DNS/TLS/egress constraints, tenant-scoped credentials, durable replay/idempotency stores, health/latency probes, actual rollback drill artifacts, evidence custody and retention, incident escalation routes, and an explicit human change-control decision. A separate deployment executor and verified rollback process would be required for an eventual rollout; neither is introduced here.

Architecture boundary: Virtual Silk Road is the digital Earth substrate. Estate ARKs are governed vessels/networks operating within it. Spatial containment is Earth → Virtual Estate → Place → Location → Door → Room → Window/Stage → Activity. Release assurance is read-only and does not access personal desktop, browser, local device, or third-party session data.
