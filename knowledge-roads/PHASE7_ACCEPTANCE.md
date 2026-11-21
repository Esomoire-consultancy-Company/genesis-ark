# VSR-FOR-001 R0.7 — Independent Staging Acceptance Contract

**Engineering status:** REVIEW-ONLY; no connected Genesis registrar, DigitalMe issuer, Warden policy service or authentic RiverOS evidence producer. No staging service was created, contacted, or authorized.

## Goal

Create a reproducible acceptance **contract** for the prior Knowledge Roads phases, deliberately separating simulation from real deployment. Only readonly framework navigation is in scope. The fourteen framework records remain unregistered proposals. A scientific theory or historical technique's role as a road, navigation method or engine candidate does not mean that the scientific object is executable, owned by Genesis, or qualified for action.

## Required independently signed checks

| Role | Expected evidence before staging promotion | Test-only implementation |
|---|---|---|
| GENESIS_REGISTRAR | Authenticated versioned framework ID, source attribution, station scope, revocation, provenance | Fixture assertion; real registrar absent |
| DIGITALME | Verified human originator, session, estate, mandate, consent, purpose and revocation status | Fixture assertion; no SSO bound |
| WARDEN | Dedicated `navigate.readonly` policy and decision, exact route/identity binding | Fixture assertion; Alpha restart policy not reused |
| RIVEROS | Real signed receipt with event and transaction/outbox identity, reconciliation | Fixture assertion; no real receipt |
| REPLAY_LEDGER | Durable uniqueness and recovery evidence under retry/partial failure | Fixture assertion; no distributed ledger |
| SECURITY | Peer-validated threat model, key custody, isolation and incident rollback | Fixture assertion; no security sign-off |
| HUMAN_REVIEW | Authorized separate reviewer and release mandate | Fixture assertion; no human approval |

Each accepted fixture is Ed25519-signed by a **different pinned test public key** and provides a unique issuer and evidence ID. Its signature covers the role, audience, route digest, Git commit SHA, run ID, Estate, station, purpose, issue/expiry and result. The input plan is hashed deterministically. Only the seven above roles count.

The verifier deliberately accepts only `classification=TEST_ONLY` and `is_fixture=true`, with `promotion_requested=false` and no engine execution or mutation. Even seven passing fixtures yield `SIMULATED_ACCEPTANCE_COMPLETE`, with **all operational permission flags false**. Actual provider evidence without a separate trusted production verifier yields `HOLD`, not real acceptance.

## Test execution

From the repository root, with Python 3.11+ and `cryptography>=42,<47`:

```bash
python -m pip install -r knowledge-roads/requirements-phase7.txt
python -m unittest discover -s knowledge-roads -p 'test_*.py' -v
```

For this R0.7 subset, 33 Phase 7 tests and 36 Phase 6 tests passed locally on 21 November 2026 (69 from the subset in the standalone bundle). This is not a claim of a passing GitHub Actions run or independently certified staging services.

## Acceptance artifacts for a future authorized staging operator

The staging operator must provide real, service-origin attestations through approved private infrastructure and independently verifiable public-key trust anchors. Do **not** commit live keys, personal details, provider secrets, unredacted identity records or real authorization tokens to this public repository. Record accepted service versions, tenant and station scope, verifier build hash, route hash, clock source, reproducible threat-model tests, failures and human review. Use restricted audit storage with references in the review packet, not embedded private material.

## Release governance

**Phase 7 cannot approve merging, deployment, registration or engine execution.** Only a later, independently approved integration may change that disposition after real service verification, key-management review, signing and replay guarantees, proper RiverOS receipts and signed human authorization. The current Alpha Warden `container.instance.restart` right is not a navigation right.

Next engineering deliverable: separately reviewed provider adapter implementations for actual staging services; expose verifiable service credentials and issuer trust roots through a secured deployment environment, **not** through PR fixtures.
