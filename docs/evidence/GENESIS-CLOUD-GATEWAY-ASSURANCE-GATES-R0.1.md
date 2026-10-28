# Genesis ARK Cloud Gateway R0.1 — assurance gates

This branch remains deny-only; its PostgreSQL spool is not RiverOS authority.

## Safeguards
- Reject unsafe PostgreSQL column, schema, database, sequence, server-file and
  privileged-SET grants before readiness or read-only audit.
- R0.2 schema migration checks the expected table shape, enforces a unique
  predecessor and a single genesis row, blocks UPDATE/DELETE/TRUNCATE using
  triggers, and revokes PUBLIC schema CREATE.
- Shared database-backed intake limits: 60 new intents per minute and 100,000
  total spool rows; exact idempotent replays still return their original receipt.
- The limits are a bounded safety guard, not a replacement for network-edge rate
  limiting, data retention rules or database capacity monitoring.
- Local sequence numbers are not cryptographically authenticated by the event
  hash; absence of an independent RiverOS witness must remain explicit.
- The provisioner creates a PostgreSQL SCRAM verifier offline and embeds only
  the verifier in role-creation SQL, not the plaintext password. Restrict SQL
  statement logging and access to verifiers.
- Database owners or superusers can still disable triggers or destroy data:
  external independent witnessing and backups remain mandatory.

## Deployment boundary
The new migration has not been run against Railway staging or production.
Complete disposable-database tests, migration review, credential rotation
evidence, backup/restore drill and security approval before staging changes.
Do not merge, execute Docker commands, issue Warden PERMIT or settle Silk funds.
