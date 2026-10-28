# GWIEP R0.5 — Staging Readiness: Subject Consent and Transactional Outbox

**Status:** ALPHA / SYNTHETIC ONLY / SOURCE & TESTS / NO DEPLOYMENT.

Stacked on R0.4 draft PR #21, R0.3 PR #20 and R0.2 PR #18. No real identity provider, ChatGPT live capture, Docker production access or network server is connected.

## Implemented boundary

1. The member presents an externally verified JWT with work:consent scope and opts in to a specified work ID, source, tenant, recording purpose, and expiry up to 30 days. The resulting audited receipt stores pseudonymous token ID hash and a consent generation, not the original bearer token or conversation content.
2. The same member can withdraw their consent; new intake is denied and queued unpublished events are blocked. Previously published evidence is not silently deleted. Re-enabling consent increases the generation and cannot resurrect old blocked captures.
3. Incoming signed source packets pass DigitalMe verification, tenant scope, independently registered Warden grant, signed source envelope, explicit subject consent and unique capture ID. The SQLite transaction commits the accepted metadata packet as PENDING, without writing RiverOS during the request.
4. The trusted local outbox consumer rechecks live consent and Warden scope, verifies the stored signature, and projects pending metadata into the existing RiverOS JSONL journal. A successful projection stores its River event ID/hash and is marked PROJECTED.
5. On an interruption after the River write but before the SQLite acknowledgment, the consumer finds the existing hash-chain record and acknowledges it instead of writing another copy.
6. Reconciliation detects projected index mismatches and unacknowledged River records. Reads require work:read and enforce exact tenant/principal/work ID, exposing pending, blocked and projected counts.
7. LBM/OCM status remains external. A recorded command, queued event or tool attempt does not establish executed or verified work.

## Technical limitations requiring remediation before any live staging rollout

- **Not a production consent UX:** this is a user-authenticated technical opt-in record, not evidence of an adequate notice, purpose explanation, legal basis or informed consent. Human-readable policy version, purpose acceptance and withdrawal confirmation must be incorporated.
- **Not a distributed event store:** one local SQLite outbox coordinates acceptance; the shared hash-chain JSONL journal remains a downstream side effect. A single authorized consumer/writer is essential; separate direct journal writers are prohibited.
- **Crash recovery remains conditional:** River append+ack are not one ACID transaction. Reconciliation flags drift but independent checkpoint anchoring and filesystem durability are not implemented.
- **Not an API server:** no public endpoints, network ACLs, live external identity issuer, cloud KMS integration or installed ChatGPT source extension are supplied.
- **Replay claims are metadata-only:** the capture signature proves an adapter signed the input, not that ChatGPT itself emitted microphone or keyboard provenance.
- **Withdrawal is prospective:** already published evidence must follow separately configured retention and erasure policy. Pending events are blocked in the outbox.
- **Source key versions:** key rotation and offline queue lifetime require explicitly versioned keys and grace/revocation policy.
- **Read models:** private_progress uses outbox status data; it is not a signed River execution-verification report. It must distinguish submitted/queued from projected/verified.
- **Multi-tenant controls:** the prototype isolates read data by tenant/principal/work IDs but still needs an independently reviewed API perimeter, per-tenant encryption, rate limits and safe metadata IDs.
- **Admin grants:** R0.4's local work:admin record alone does not prove two-person approval or genuine legal delegation. High-privilege operations require independent Warden decisions and human-signature evidence.

## Acceptance tests

Run in the control-plane workspace:

    python -m pytest tests/test_work_r05.py tests/test_work_identity_r04.py -v

Run all existing non-Docker control-plane tests:

    python -m pytest tests -v -m "not docker_e2e"

R0.5 scenarios include opt-in required, withdrawal, reconsent without old-event resurrection, denial after Warden revocation, modified-signature rejection, same-ID conflict, exact-tenant reads, lack of read/capture permissions, crash-after-append recovery and journal tampering.

## Hard release gates

- [ ] Independent identity issuer/SSO staging configuration and trust review
- [ ] Versioned user-facing notices and member-consent UI, authorized opt-out
- [ ] Warden administration with separate grant signatories and audit receipts
- [ ] Transactionally durable outbox with single writer, independent evidence hash checkpoints, backups, secrets/PII audit and disaster-recovery drill
- [ ] Resource-limited, authenticated, private, monitored staging API (not deployed)
- [ ] Formal segregation: no external ChatGPT capture, no production Docker execution, no unrestricted transcript storage
- [ ] Tenant-level retention, export, correction, deletion and legal-policy review
- [ ] Security and operations approval before merge/deploy

### Release decision

R0.5 is a reviewable, synthetic-only technical increment, **not production ready**.
