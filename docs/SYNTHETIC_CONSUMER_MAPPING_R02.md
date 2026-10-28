# Synthetic Consumer Compatibility Contract R0.2

## Purpose

Genesis ARK should maintain **one versioned fictional actor/Commons/BNR/licence vocabulary**, while individual consumer repositories retain their own contract tests and runtime authority. This contract separates **test equivalence** from **actual identity or entitlement issuance**.

Source: `synthetic-baseline/fixtures.json`, frozen clock `2026-10-28T10:00:00Z`. No real person data, subscription, settlement, service API, or operational node is present.

## Consumers and readiness

| Consumer | Existing pattern observed | Proposed mapping | Readiness |
|---|---|---|---|
| Genesis ARK `control-plane` | Alpha registry of station/resource/capabilities with one-shot Warden decisions | Separate `synthetic-ci` namespace; test actor identity/entitlements before any future Alpha command; deny synthetic actors entering Alpha | Contract only; **not wired** into the Alpha runtime |
| Believers Common `creators-door` | In-memory synthetic DigitalMe session, BNR entitlement, Warden verify, River reservation/receipt, Synnergyze result | Test doubles may consume a canonical `SYN-ACTOR-*` and `SYN-LIC-*` ID; preserve separate campaign-specific consent, digest, relationship, request and receipt gates | Contract only; **not wired** into external repository |
| Genesis public Gateway | Static public exploration without authentication | Public Gateway should not expose the simulator as an authority provider | Intentionally **not connected** |

## Minimum consumer mapping

- Principal: `actor.id` -> test-only `actorRef`; never reuse as a DigitalMe authentication subject.
- Commons: `memberships[actor_id]` -> test-only membership gate; `REVOKED` or absent must DENY.
- BNR: `representations` -> test-only organisation/node delegation; must match actor, node, `ACTIVE` and expiry.
- Licensing: `licences` -> test-only entitlement; must match actor, action, optional node and named legal supplier; expired/missing must DENY.
- Warden: `SyntheticOracle.evaluate()` produces *expected* `ALLOW`, `DENY`, `ESCALATE`; it is not a signed grant, token, or policy enforcement service.
- RiverOS: `evidence_sha256` is a deterministic fixture receipt, **not** proof of a deployed RiverOS journal or external append.
- Synnergyze: the simulator reports `executable:false` and `effects=0` for every result. It cannot run commands, dispatch jobs, transfer funds, grant licences, or alter membership.

## Promoting a consumer fixture bridge

1. Pin the exact fixture content hashes and contract version in the consumer PR.
2. Import only fields required by that consumer's test adapter, never derive runtime credentials or tokens from fixture IDs.
3. Test the normal case plus no membership, revoked membership, expired licence, wrong node, wrong supplier, unbound action, fabricated authority, replay conflict and environment mismatch.
4. Assert **zero external effects** in every synthetic scenario; check River event lineage separately in the actual consumer's own unit tests.
5. Distinguish integration failures from expected DENY and ESCALATE results.
6. Run the consumer's CI on the exact PR head commit, and review provenance before promotion.
7. Require a new signed/approved contract for live identity, official company registration, merchant settlement or any operational execution. This test fixture is ineligible for those grants.

## Known separation

The `creators-door` campaign action/receipt vocabulary is not identical to the ARK `creator.draft.synthetic` contract. No automatic production-action alias is supplied because mapping a synthetic ALLOW into a real capability would constitute privilege escalation.

The Genesis control plane's published `alpha` station/resource registry is intentionally *incompatible* with a `synthetic-ci` membership licence. Both can be exercised in isolated tests; neither should inherit the other's permits.

## CI failure classification

A failure must be logged as `FIXTURE_MISSING`, `AUTHORITY_BYPASS_BUG`, `CONTRACT_MISMATCH`, `INFRA_TRANSIENT` or `DEPENDENCY_UNAVAILABLE`, with branch, SHA, run ID, source fixture hash, test clock and job step. A failing browser smoke should not be “solved” by adding real users or operational licences.
