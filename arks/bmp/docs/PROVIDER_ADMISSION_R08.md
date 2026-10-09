# Provider Admission & Deployment Assurance R0.8

**Repository status:** source-only, draft-PR engineering gate. **No production providers have been admitted, deployed, authenticated, observed or changed.**

## Contract and responsible service owners
DigitalMe signs principal assertions; Genesis signs registered asset/capability records; Warden signs admission/policy; Quantum Room signs pending session requests; River signs evidence receipts. BNR provides a separate assurance review. Each independent provider must submit a signed, release-bound provider-attestation envelope. The platform owner supplies pinned public keys and exact HTTPS origins out of band.

`service/provider-admission.mjs` evaluates a **read-only proposed admission packet**. Five independent Ed25519-signed provider attestations plus independent Warden and BNR reviews must bind the same release SHA, tenant, environment, asset and manifest digest. Evidence references must be checked by an injected trusted River verifier, not guessed or inferred from `river://` strings.

The nine required assurance controls are:
- operator_authority
- domain_tls
- egress_policy
- durable_replay_store
- tenant_isolation
- rate_limits
- key_rotation
- river_custody
- rollback_test

**Important:** Even a correctly signed packet and verified evidence references result in `REVIEW_READY`, never automatic deployment. The gate always returns `operations_enabled=false`, `public_qr_enabled=false`, `deployment_activated=false`. Further controlled deployment authorization is a distinct procedure with independent sign-off. There is no deployment executable in this PR.

## Canonical admission workflow
1. Genesis registers provider identity, verified legal operator, capability and location/estate mapping.
2. Each provider submits signed endpoint, signing-key identification, tenant and release-bound verification evidence.
3. Warden and BNR independently approve the same digest for technical review.
4. An independently configured River retrieval/verification callback confirms evidence exists, was issued by trusted authorities and binds the expected source, tenant, release and scope.
5. `assess()` returns `BLOCKED` with specific reasons, or `REVIEW_READY` for authorized deployment review.
6. Only after separate deploy approvals, managed credentials, routing controls and rollback rehearsals can a registered runtime be provisioned. No stage changes the A-1204 pilot status here.

## Current static fixture
`configs/provider-admission.sample.json` is intentionally expired, missing all attestations and contains `A-1204` which is **hard denied** in this revision. Running it cannot certify any service. The `--require-ready` flag exits nonzero on blocking conditions.

```bash
node arks/bmp/scripts/provider-preflight.mjs
node arks/bmp/scripts/provider-preflight.mjs --require-ready
node arks/bmp/scripts/validate-provider-admission.mjs
```

## Operational constraints
- Adapters from R0.7 use injected HTTPS origins, but runtime DNS-rebinding / internal resolution enforcement, managed egress, credential rotation, actual transport trust and TLS pinning require infrastructure controls. URL parsing alone is not an SSRF defense.
- `JSON.stringify` is the current signature byte convention. Cross-language canonical serialization and key rotation/revocation are unresolved and block external provider admission.
- The River verifier is dependency-injected; a test-only callback returning `true` is not acceptable as production evidence validation.
- Review packets carry references only, not private titles, identity documents, credentials, personally identifying records or actual commercial rates.
- Successful lab tests establish *contract behavior*, not real security posture, legal authority or service availability.
- Quantum remains `PENDING` until a separate confirmed-session lifecycle is implemented.
- A-1204's actual registered entitlement and physical property claims remain unverified; the public Door is disabled and the R0.7 adapter has an explicit hard deny.
- All monetary figures remain **DEPICTION_ONLY** sample values.

## Acceptance evidence before production
Independent operator authorization, verified endpoints and TLS/egress, signed issuer key inventory with revocation, durable nonce / idempotency storage, policy and BNR attestations, verified River custody, cross-provider tenant isolation, performance/abuse tests, rollout/rollback test results, human go/no-go and release commit provenance.
