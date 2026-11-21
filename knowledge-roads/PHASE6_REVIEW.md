# VSR-FOR-001 · R0.6 — Verified Staging Trust Boundary

**Status: REVIEW ONLY — no live Genesis, DigitalMe, Warden or RiverOS service connected.**

## Why this exists

Phase 5 checked the shape of registered-route, identity, Warden and River assertions through injected fixture ports. Phase 6 adds a stronger **offline staging proof**: cryptographically signed fixture payloads (Ed25519) and durable one-shot replay prevention (SQLite). This prepares service integration requirements without mistaking test keys for operational authority.

## Demonstrated verification sequence

1. **VSR intent:** `navigate.readonly`, explicit `execute=false` and `mutation=false`, scoped principal/session/estate/station/location/purpose, short expiration and bounded framework steps.
2. **Genesis:** signed staging snapshot with trusted, pinned *fixture* public key, correct issuer and audience, station scope, framework provenance, version, state and revocation flags.
3. **DigitalMe:** separately signed scope, verified identity, active mandate and affirmative consent; session and purpose must match.
4. **Warden:** signed scoped decision tied to a digest of the route and DigitalMe assertion, short expiry, policy identifier/version and one-shot identifier.
5. **River fixture:** separately signed `TEST_ONLY` simulated acknowledgment, matching decision and route. This is **not** an actual RiverOS receipt.
6. **Replay ledger:** SQLite transaction records the simulated acknowledgment under a unique `(issuer, decision_id)` key; reuse is denied, including different nonces or reopened SQLite connections.

A successful result is always `STAGING_CRYPTO_VERIFIED_ONLY`. In **every** result: `authority_granted=false`, `engine_execution_allowed=false` and `real_river_receipt_emitted=false`.

## Scope and exclusions

- None of the 14 proposed framework references is registered in a real Genesis registrar by this code.
- No live credentials, real trust anchors or partner data are included. Test keys are freshly generated in tests.
- The current Alpha Warden's `container.instance.restart` permission is not reused.
- No live SSO, DigitalMe consent API, Warden policy engine, network gateway, RiverOS writer or engine executor is connected.
- No main-branch deployment, production registration, physical movement, IoT action, SILK payment or commercial entitlement is changed.
- SQLite is an adequate **local test** for uniqueness, not a distributed, multi-region production ledger or transactional outbox.
- SHA-256 digests identify the route inputs; they do not alone prove source authenticity or Warden permission.
- Testing cannot by itself establish the accuracy, applicability or provenance of the listed scientific and historical references.

## Local verification

From this archive:

```bash
python -m pip install 'cryptography>=42'
python -m unittest discover -s knowledge-roads -p 'test_phase6_*.py' -v
```

36 Phase 6 tests passed in the local container on 21 November 2026. This does **not** assert GitHub Actions CI success or independently observed production behavior.

## Production HOLD gates

- Signed authoritative Genesis registrar records and independently qualified framework references.
- Operationally governed trust root distribution, pinned issuer IDs, key rotation, revocation and timestamp validation; never accept keys from an untrusted envelope.
- Independent DigitalMe authentication, effective appointment, consent, purpose restrictions and revocation.
- A dedicated Warden `navigate.readonly` policy with a tamper-proof decision service; source authorization remains outside this module.
- Durable **distributed** replay store/outbox semantics and reconciliation for timeouts and partial failures.
- Real RiverOS event attestation/signatures, privacy filters, sequencing and recovery semantics.
- Assured sandbox, signed staging acceptance record, risk assessment and authorized human release approval before actual navigation or execution.

## Source

`knowledge-roads/phase6_trust.py`, `knowledge-roads/test_phase6_trust.py`, and this review document. `cryptography` is an explicit test dependency. No production signer is included.