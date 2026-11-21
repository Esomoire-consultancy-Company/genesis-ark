# VSR-FOR-001 R0.4 — Registration handoff and Warden sandbox admission

**Status: REVIEW ONLY. No live registrations, no Warden grants, no engine execution, no RiverOS receipts.**

## Design responsibility

The source reference remains a historical or scientific object with original attribution.
"Road", "navigation", "checkpoint", "bridge", and "engine candidate" are
independent functional roles. They do not transfer ownership of the underlying theorem
or qualify an implementation for operation.

## Added artifacts

- `registration_proposals.json`: 14 immutable-by-convention *proposal* records, external registry IDs null, no grants or execute adapters.
- `admission_contract.py`: canonical SHA-256 route fingerprints, scoped station/version/provenance checks and test-only short-lived signed Warden decisions.
- `test_admission_contract.py`: 24 sandbox regression tests, including replay, expiry, wrong estate, forged signature, route substitution, source/version drift and no-live-authority assertions.
- Existing `navigation.py` remains fail-closed on all protected `navigate.readonly` requests.

## How to run

```sh
python3 -m unittest discover -s knowledge-roads -p 'test_*.py' -v
```

Locally, 32 tests passed (8 R0.3 + 24 R0.4). This does not imply CI passed.

## Local preparation contract

`prepare_route(route, registrations)` checks:
- `navigate.readonly` capability only, no mutation and no engine commands;
- nonempty principal, estate, station, purpose and ordered route;
- registered steps and the correct Knowledge Station;
- registry ID, version, attestation reference and source reference;
- canonical digest includes every ordered step, source, attestation and version.

A caller can supply arbitrary registry data. Therefore even `registration_state=ACTIVE`
does *not* constitute an authenticated registry; a fully populated fixture returns only
`READY_FOR_SANDBOX`. Real admission is never issued.

## Test-only Warden adapter

`SandboxWardenGate.assess` checks the full route intent digest, audience, short
validity window, scope, HMAC signature and in-memory replay identifier. Its highest
disposition is `SIMULATED_PERMIT` with all of:
`authority_granted=false`,
`execution_allowed=false`,
`river_receipt_emitted=false`.

HMAC fixture keys, client-created claims, local replay memory and SHA-256 digests are
**not a trusted Warden service or evidence signing authority**.

## Production HOLD gates

1. A verified Genesis registrar, actual framework identities, immutable source provenance,
   version attestations, qualification and revocation checks.
2. Independently authenticated DigitalMe principal, mandate, estate, location,
   purpose, appointment, consent and session.
3. Separate Warden `navigate.readonly` policy and verifier with trusted key lifecycle.
   Existing GES Alpha `container.instance.restart` authority cannot be repurposed.
4. Durable replay protection, policy/version revocation, station/estate isolation,
   safe clocks, and independent review of policy precedence.
5. Actual signed RiverOS evidence of transitions with reconciliation, not simulated logs.
6. Separate engine qualification and action-specific human approval.

**Review disposition:** A draft pull request is evidence of proposed code, not
membership enrolment, authorization, site publication or production admission.
