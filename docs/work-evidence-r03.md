# GWIEP R0.3 — Genesis Gateway Work Admission, Warden Consent & River Reconciliation

**Status:** review-only Alpha Python library and tests. **No deployment.** Stacked on GWIEP R0.2 (draft PR #18). Does not replace the Docker restart authority contracts or production DigitalMe SSO.

## Architecture and trust boundaries

1. A trusted, approved client or device signs one metadata-only packet, scoped to a workstream and tenant.
2. A separate identity issuer signs a maximum-15-minute local Alpha session with tenant/principal/station/source/session and exact expected audience. The local test issuer is a contract fixture, **not production DigitalMe authentication**.
3. The Genesis Work Intake Gateway verifies the session, calls the Warden work-admission policy, then validates the capture adapter signature before any receipt or replay lookup. The client cannot grant itself a permission.
4. Warden checks a trusted registered source and an externally provisioned consent grant for source, tenant, principal, station, channel, work ID, event type, active status and expiry.
5. A SQLite BEGIN IMMEDIATE transaction coordinates cooperating gateway writers. The existing signed source intake and River JSONL hash-chain journal record the event. The durable acceptance index stores tenant/source/capture ID, scoped fingerprint, work ID, consent/policy IDs and the River receipt.
6. The reconciliation method verifies River hash-chain integrity and checks indexed receipts against River records, flagging missing receipts and unindexed captures. A River-first interruption may be recovered by retrying the original authenticated packet.
7. Existing work-summary logic can count admitted events, but a dashboard still requires tenant-scoped read authorization.

This R0.3 contract does NOT widen existing Docker Warden or WEG execution authority. Sources can submit only work.input, work.output, work.tool and work.revision. They cannot approve, verify, finalize, reopen, mutate Docker, or grant permissions.

## Security boundaries

- Library only: no network listener, no ChatGPT session hook, no automatic history capture, no Docker operations and no production deployment.
- Local HMAC sessions are fixture contracts, **not** DigitalMe SSO, production JWT/OIDC or remote access controls. Real identity must independently validate issuer, audience, time, revocation and rotating keys.
- RegisteredSource and ConsentGrant MUST come from a trusted, authenticated administrative authority and must not be populated from the requesting client.
- A signed device claim of voice versus typed is only as reliable as that device's capture code. Historical exports remain unknown origin.
- Use separate, protected keys for identity issuer and each source; do not commit keys.
- The two stores (SQLite index and JSONL River) are not an atomic distributed transaction. Interrupted or concurrent writes, and journal writers bypassing this gateway, require additional controls before rollout.
- River hash chaining requires independent checkpoints and backups for stronger tamper resistance.
- No full prompt, transcript, attachment name or secret belongs in metadata payloads; identifier fields also require stricter syntax/privacy rules for real users.
- Work reports are private and must enforce tenant / work ID / principal access control.

## Test command

From the control-plane directory, after installing package test dependencies:

    python -m pytest tests/test_work_gateway.py tests/test_work_capture.py tests/test_work_evidence.py tests/test_work_import.py -v

Full existing GES Alpha non-Docker tests must also pass on Python 3.11 and 3.12 before approval.

## Promotion gates

- [ ] Independent DigitalMe identity provider verification and short-lived session revocation
- [ ] Warden-signed, server-resolved source and consent registry with scope/revocation
- [ ] Tenant-scoped access to every read, capture, work, artifact and reconciliation endpoint
- [ ] Production-grade idempotency, transactional outbox or equivalent safe evidence consistency
- [ ] Per-source key management and provenance from trusted capture UI
- [ ] Secure historical import with explicit consent; no silent prior-chat access
- [ ] Durable backup, evidence anchoring, retention and privacy review
- [ ] Negative test coverage, performance checks and staging review before any deployment
- [ ] Separate authenticated approval, verification, finalization and version/reopen lifecycle
- [ ] LBM and OCM maintained across each work state and correction

**Governance:** an accepted input is RECEIVED, not EXECUTED; a tool invocation is ATTEMPTED, not VERIFIED; and evidence of an approval does not alone establish legal or operational authority.
