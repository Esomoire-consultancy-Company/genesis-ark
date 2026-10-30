# Genesis Estate R0.8 — Independent Staging Gate (2026-10-30)

**Decision: HOLD.** This is an evidence-based staging assessment, not a deployment receipt or production approval.

## Verified release input
- Local R0.8 source archive SHA-256: `c900b18b4f431394314600918a0ab9669ef22994869dc92790e0ef4dfa958795`.
- Local R0.8 report: 218 synthetic, same-host regression and process checks; **not** proof of independent-host staging.
- Independent-staging preparation: read-only release-integrity/evidence gate script and 12 passing preflight tests, archived as a separate handoff. No live cloud mutation performed.

## Read-only infrastructure observation
- Railway: `genesis-ark-gateway-staging` / `staging`, three successful Genesis gateway/preview application deployments and PostgreSQL with a persistent volume, all listed in region `us-east4-eqdc4a`.
- The deployed sources are branches in `Esomoire-consultancy-Company/genesis-ark`, **not verified builds of the local R0.8 receiver/authority package**.
- Railway `estate-r05-assurance` / `sandbox` had zero services.
- Render workspace was readable but its service query returned no usable inventory. Absence cannot be inferred.
- R0.8 launcher uses `127.0.0.1`, same-machine key bootstrap and shared local test CA; no host-separated readiness is established.

## Non-negotiable independent-staging gates
1. Operator-approved, separated gateway; Warden/registry; policy publisher; receiver; independent auditor/witness hosts.
2. Independent authority signers and non-shared hardware/KMS key custody, private mTLS service identities with DNS SANs, credential rotation/compromise drills.
3. Signed image/commit digests and deployment receipts identifying actual environments, operators, authority and observed health.
4. Cross-host signed revocation propagation + exact matching receiver ACK and stale-policy/partition drills.
5. Exact command idempotency and recovery, including receiver terminal-fence readback, without blind replay.
6. Independently signed RiverOS evidence, audit retention and independent recovery access.
7. Monitoring, backups, restored state, incident escalation, security assessment and real browser acceptance.
8. All live business, bank, financial-settlement and physical-device mutations **disabled** in this synthetic staging phase.

## Decision
**HOLD** until independently verifiable host/operator/deployment/incident evidence is reviewed by the authorised operators. Do not relabel the existing Railway ARK preview as an R0.8 independent-federation deployment.

## Next handoff
Replace the local-only launcher and shared CA with independently hosted, operator-provisioned services and documented trust roots; run signed cross-host revocation, ACK-loss, receiver-fence and readback drills; then submit a distinct real staging receipt for review.
