# VSR-FOR-001 — Phase 5: Staging Connector Boundaries

**Version:** R0.5 · 2026-11-21 · **Review only**

## What is implemented

A local Python staging orchestrator composes five explicitly injected ports:

1. Genesis framework registrar `resolve()` — versioned object mapping, provenance, station scope, revocation.
2. DigitalMe identity `verify()` — principal/session/estate/station/location, mandate, purpose, consent.
3. Warden `evaluate()` — separate `navigate.readonly` decision, route hash, audience and short-lived scope.
4. Replay ledger `reserve()` — fixture-only one-shot decision identifier; non-durable.
5. RiverOS evidence `acknowledge()` — fixture event of a simulated transition; **not an actual RiverOS receipt**.

`StagingNavigationChain.evaluate()` runs the ports in order. It returns **HOLD** if any connector is missing or unavailable. Unknown/mismatched/revoked scopes or prohibited actions are denied or held. The maximum permitted result is `STAGING_PREVIEW_ACCEPTED`, and even then `external_authority_granted`, `engine_execution_allowed` and `river_receipt_emitted` remain false.

## Inputs and safety

- Requests must explicitly contain `execute=false` and `mutation=false`; omitted fields are denied.
- Capability is limited to `navigate.readonly`. A separate engine admission and protected Warden execution decision must be developed later.
- The route fingerprint includes ordered framework records, versions, source and attestation references, and principal/estate/station/location/purpose scope; it does not replace signatures.
- Each framework record is a **fixture response**. It is not an actual Genesis registration simply because an injected port labels it `ACTIVE`.
- DigitalMe and Warden assertions are synthetic: this contract does **not** validate cryptographic issuers, key rotation, signed provider attestations or a trustworthy time source.
- The replay store is process-local and non-durable. It must be replaced by a reviewed transactional store before real admission.
- River fixture acknowledgements use `TEST_ONLY` classification; no external side effect or authentic receipt exists.
- Real registry registration, service deployment, test credentials, user-specific information and repository main-branch changes are excluded.

## Test

From the repository root:

```bash
python3 -m unittest discover -s knowledge-roads -p 'test_*.py' -v
```

Phase 5 standalone tests in `test_staging_chain.py`: **31 passing locally**. Existing Phase 3–4 tests should also run in repository CI before merge. The local check is not a claim about GitHub CI, staging hosting or live authorization.

## Admission gates for the next iteration

- Authenticated registrar adapter accepting signed authoritative records, version conflicts and revocation.
- Independently verified DigitalMe attestations with subject, role, mandate, consent and exact scope.
- Server-side Warden policy **separate** from current Alpha container-restart governance, with crypto-verifiable decision chain.
- Durable, transactional replay ledger plus key lifecycle, issuer trust and clock verification.
- Signed RiverOS receipts with reliable enqueue/ack/idempotency/reconciliation.
- Differential tests against actual staging services with appropriately authorized operators and audit review.

**No current user action is necessary for the local preview; promotion remains blocked by the above gates.**
