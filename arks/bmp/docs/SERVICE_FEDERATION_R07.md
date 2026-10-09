# BMP ARK R0.7 — Service Federation Adapter Contract

**Status:** implemented adapter orchestration and isolated lab tests only. **Not configured, deployed, connected, or authorized against live DigitalMe, Warden, Genesis, Quantum Room or River.** Do not describe any pilot Door, QR, buyer slot or receipt as live.

## Trusted transport
`service/transport.mjs` enforces separately configured HTTPS service origins, fixed internal paths, no redirects, no user-provided service URLs, bounded response payloads, short timeouts, service-scoped bearer credentials through an injected callback, and sanitized upstream error codes. Network-level egress restrictions, provider DNS allowlisting, certificate policy, secret issuance/rotation, rate limiting, abuse defense and logging remain an infrastructure responsibility, **not delivered in this PR**.

`service/adapters.mjs` binds five independent roles:
- Genesis: signed, expiring, resource-bound asset assertion from `GET /v1/assets/{assetRef}`.
- DigitalMe: short-lived signed identity assertion from `POST /v1/assertions/resolve`. The input bearer is sent only to the configured DigitalMe service.
- Warden: signed policy decision from `POST /v1/admissions/evaluate`. The Door resolver checks identity, resource, Door, action, requested state, anchor and correlation.
- River: signed receipt from `POST /v1/evidence/ingest`, which must match the immutable event digest, correlation and Warden decision.
- Quantum Room: `POST /v1/sessions/request` yields **PENDING only**, separately authorized by a signed Warden action and recorded through River. No actual booking is asserted.

All five public issuer keys are supplied by a trusted administrator outside the user request; the code generates no production keys. Signed envelope uses R0.6 payload-byte conventions; **cross-language canonical serialization is unresolved** and must be specified and tested before adopting external issuers.

## Asset admission
The adapter requires an explicit, server-owned `allowedAssets` list; missing registry record fails closed. For A-1204, there is an **absolute deny override** that always returns the original `DRAFT_UNVERIFIED`, `live_enabled=false` registry record, even if an external mock claims the property is active. Its removal requires a distinct reviewed revision backed by verified rights, approvals, privacy and estate authority.

## Nonce / replay
The caller must inject an atomic durable `nonceStore.consume(nonce,exp)` implementation. No in-memory nonce store is part of the release. Tests use an ephemeral in-memory stand-in strictly inside the CI process. A replay, storage failure, expired assertion or forged event fails closed.

## Quantum protocol
`createServiceFederation` wraps the Door resolver with an internal WeakMap-scoped admission capability. Callers cannot manufacture this capability by posting a JSON object. `requestQuantumSession(admission,{requested_slot})` requires a prior admitted object, a separately signed Warden authorization specifically for `quantum.session.request`, a signed Quantum `PENDING` response and signed River receipt. No confirmed time, reservation, owner rights or payment is issued. A production booking workflow would need confirmation/cancellation/webhook and host availability contracts independently.

## Source-to-execution ordering
Identity → Authority → Reachability → Orchestration → Execution → Evidence is the canonical runtime model. Registry admission screening occurs before requesting private identity data as a data-minimization optimization; independent provider operations still require authorization. The ARK remains a quantum network; VSR is the digital Earth substrate, not an individual mission vessel.

## Local validation
```bash
node arks/bmp/scripts/validate.mjs
node arks/bmp/scripts/validate-door-runtime.mjs
node arks/bmp/scripts/validate-federation.mjs
```
No production endpoints or secrets are checked in. Run only on registered engineering stations with operator approval.

## Live integration blockers
1. Real service URLs, owned domains, and issuer key trust roots verified by independent owners.
2. Actual interface specifications and signed assertion formats accepted by DigitalMe, Warden, Genesis and River.
3. Durable nonce store, TLS and network controls with least-privilege credentials.
4. Tenant isolation, BNR governance, key rotation, consent and River custody verification.
5. Real Quantum scheduling/host availability; current method returns pending and no booking.
6. Deploy with rollback plan, authorized environment, runtime trace and signed review evidence.
7. Property/site legality and asset authority before considering any A-1204 admission.

**All property, JIG, bundle and service amounts stay DEPICTION_ONLY.**
