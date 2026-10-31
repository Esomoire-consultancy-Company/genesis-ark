# Genesis Estate R0.9 — Independent-host operational acceptance

**Assessment date:** 31 October 2026

**Decision:** INDEPENDENT STAGING = HOLD; PRODUCTION = HOLD.

This is a read-only assessment and a review of a local acceptance package, not a deployment approval or remote deployment.

## Verified local engineering evidence

- R0.9-S1 distributable archive SHA-256: `07cb90bacd32aaa9a9a683a920f6d01d09e238d0d0ee8d3bb1336b101c56303b`.
- R0.8 source ZIP SHA-256: `c900b18b4f431394314600918a0ab9669ef22994869dc92790e0ef4dfa958795`.
- New R0.9 tests: 45/45 PASS (attestor, mTLS, challenge/replay, signatures, denial).
- Re-run inherited R0.8-family unit tests: 113/113 PASS; 158 fresh local tests total.
- Actual independent-staging preflight: HOLD (exit 2).
- Independent remote hosts attested: 0/4. Remote drills completed: 0/12. Independent sign-offs: 0/2.
- All business, connector, settlement and production mutations: disabled.

## Connected infrastructure snapshot (read-only)

The Railway `genesis-ark-gateway-staging` environment contains three deployed Genesis gateway/preview application services plus PostgreSQL in region `us-east4-eqdc4a`. Those services are based on other branches of this repository and are **not verified R0.8 or R0.9 hosts**. Railway project `estate-r05-assurance` sandbox has no listed services.

A successful deployment in one cloud project is not equivalent to independent federation control or evidence of separately governed trust roots.

## Required before stage approval

1. Separately hosted registry/Warden authority, gateway, receiver and independent auditor/witness services, with independently governed operators.
2. Signed deployment manifests and immutable image digests bound to running workloads, verified by approved host attestors.
3. Separate credential custody, trust pins, mTLS service identities and controlled rotation/revocation.
4. Cross-host tests of Warden policy-epoch updates, stale-policy denial, delayed/lost acknowledgements, durable receiver terminal fencing and signed readback.
5. Independent RiverOS evidence receipts, backup/restore tests, incident drills, monitoring and approved operational runbooks.
6. Separate signed Security and Operations approvals; no implied promotion from passing local software tests.

## Restrictions

Do not modify or promote the existing Railway services on the basis of this assessment. Do not expose synthetic receiver or issuer endpoints as production. Do not claim actual host independence, real financial settlement, physical-device attestation or live partner consent without separate evidence.

R0.8 earlier HOLD review: [PR #32](https://github.com/Esomoire-consultancy-Company/genesis-ark/pull/32).
