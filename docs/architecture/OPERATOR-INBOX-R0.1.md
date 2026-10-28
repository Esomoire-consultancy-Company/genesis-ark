# Genesis/Warden Private Operator Inbox R0.1

**Status: synthetic-only, not deployed.** Stacked on Cloud Gateway PR #15; public-site PR #16 remains unchanged.

## Required routing

1. Public routes such as /v1/intents, /secrets and /.env must continue responding 404 without forwarding the visitor to a privileged user.
2. A private Railway log collector may classify selected denied requests using allowlisted metadata, stripping URL queries, headers, bodies and attacker-supplied identifiers.
3. An authenticated gateway DENY receipt belongs to a verified node; a public unauthenticated probe must never be associated with a DigitalMe Actor by inference.
4. Secret-inventory events expose only variable names, scope, owner and rotation state. No .env contents, DSNs, bearer keys or full environment dumps are ingested or displayed.
5. A case records **origin_service_id** (trusted service), **node_id** (if verified) and **node_resolution**: `unknown_external`, `pending_mapping` or `verified`. Origin service and verified actor/node ownership are different concepts.
6. Synnergyze assigns cases by registry-owned role, environment, service **and** node; Warden checks every private read or acknowledgement. A matching role/environment alone NEVER exposes all cases lacking a verified node. Unassigned or ambiguous cases remain in a restricted service-scoped work queue.
7. Each human acknowledgement creates a separate evidence receipt. Acknowledging is not granting authority or rotating a secret. Actual remediation uses vault-native controls and independent approvals.

## Role matrix

| Case kind | Minimum queue role | Scope | Disclosure |
| --- | --- | --- | --- |
| Public /v1/intents 404 | security_custodian | Environment | Masked probe classification and receipt |
| Public /.env or /secrets 404 | security_custodian | Environment | Masked protected-path classification and receipt |
| Authenticated gateway DENY | node_operator | Verified node | Correlation, reason and ledger hash |
| Secret state missing / rotation_due / revoked | configuration_custodian | Assigned custodian | Secret *name*, status and registry receipt, never value |

## Operator Inbox columns and ID contract

The synthetic preview exposes 13 columns: `Case`, `Event`, `Environment`,
`Origin service`, `Node`, `Node resolution`, `Queue`,
`Recipient`, `Assignee`, `Reference`, `Severity`, `Status`, `Receipt`.
The `Node` column now displays `Not verified` instead of the ambiguous `Unassigned`.

- `event_id`: up to 128 constrained alphanumeric/dot/underscore/colon/hyphen characters.
- `origin_service_id`: trusted service identifier; a public probe resolves only to `genesis-public-site-preview`, **not** a user or originating node.
- `node_id`: server-validated BNR registry node identifier, or null; anonymous public probes must have null.
- `node_resolution`: `unknown_external` for unauthenticated probes, `pending_mapping` when a secret inventory entry has no verified node, `verified` when an authenticated gateway or trusted vault registry mapping supplies the node.
- `case_id`: `CASE-` + first 20 hex characters of SHA-256 of `environment:origin_service_id:event_id`. This changes synthetic case IDs from earlier draft fixtures; do not use raw case IDs as cross-version evidence.
- `receipt`: first 16 characters of the deterministic 64-hex evidence digest in the preview. A local hash is not RiverOS witnessing.
- `intended_recipient_id` and `assignee_id`: distinct operator identity references; an unresolved recipient displays Pending.
- `queue_role`: `security_custodian`, `node_operator`, `configuration_custodian`. Operator's role must match, plus authorized environment and service, and verified node when present.

A trusted secret inventory connector MAY supply `trusted_node_id` and
`trusted_origin_service_id` for its server-side registry mapping. It must
never take those values from a visitor or user-submitted secret description.
The offline factory does not prove that supplied mappings are authentic.

**Safety invariant:** events without a verified node do not disappear. They
stay within a role + environment + service-scoped queue for ownership resolution.
A real centralized security role should be a separately provisioned permission
grant, not a wildcard bypass.

## Included code

- cloud-gateway/genesis_gateway/operator_inbox.py: synthetic typed events, allowlist validation, role/node filtering, deterministic case IDs, duplicate/conflict checks, single-recipient offline handoff planning, human acknowledgement receipts.
- cloud-gateway/genesis_gateway/operator_preview.py: local static HTML examples per role, no listener or actual authentication.
- cloud-gateway/tests/test_operator_inbox.py: expanded offline unit tests covering service scope, unknown-node resolution, cross-node isolation, fake/unverified roles, raw-secret rejection, idempotency, unique-recipient handoff and sanitized display.
- cloud-gateway/genesis_gateway/secret_workflow.py: staging-only **synthetic** change request -> independent approver -> separate inventory checker; never accepts secret values or executes vault writes.
- cloud-gateway/tests/test_secret_workflow.py: additional tests for dual control, service and node scope, environment scope, unauthorized callers and valid status transitions.

From cloud-gateway: python3 -m pytest -q tests/test_operator_inbox.py tests/test_secret_workflow.py
Example preview: python3 -m genesis_gateway.operator_preview --role security_custodian --output /tmp/preview.html

## Production integration gates (NOT IMPLEMENTED)

1. DigitalMe identity and BNR node roster must be verified using trusted SSO session, issuer, audience, expiry, MFA and Warden policy; never trust role labels in request bodies.
2. Authorize a narrow read-only Railway log adapter (private connector) with batching, throttling, retries, dead-letter queue, dedup and structured redaction before durable storage.
3. Map gateway denial spool to trusted issuer/node registry; preserve append-only evidence; no inferred authorization.
4. Connect secret-manager inventory only for name, vault reference, assigned owner, expiry and rotation state. Never transmit secret values.
5. Implement durable case/outbox store, signed Warden decisions, duty roster resolution, reassignment escalation, tamper-evident audit, and separately reconciled RiverOS receipts. Persist a stable event-schema version so that case IDs/hashes are not silently recomputed across migrations.
6. Bind vault edit/rotation requests to a configuration custodian, a different approver, and a third independent checker. Status checks must consume trusted, signed vault inventory receipts; the offline synthetic fixture does NOT verify real inventory state.
7. Provide authenticated private Genesis/VSR operator UI, **service, environment and node scoped** row-level policy, actor-specific read/ack checks, and vault-native remediation deep links; no public operator console.
8. Run synthetic tests for unknown actor, stale membership, absent custodian, duplicate delivery, rate spikes, signed/unsigned events, unauthorized rotation and failures before staging enablement.

**No live collector, delivery, vault access, user/SSO connection, deployment, public DNS, Warden PERMIT or production write is provided by this R0.1 proposal.**
