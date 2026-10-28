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
Disposable PostgreSQL migration rehearsal and integration tests have passed;
independent migration review, credential rotation evidence, backup/restore
rehearsal and human security approval remain required before staging changes.
Do not merge, execute Docker commands, issue Warden PERMIT or settle Silk funds.


## CI migration rehearsal (synthetic only)
The dedicated PostgreSQL 18 CI contract creates a disposable database with a
randomly generated name, applies legacy R0.1 DDL, inserts a synthetic denial
event, rejects a deliberately incompatible schema without destroying its row,
then applies the R0.2 hardening migration. It checks preservation of the original
event hash, single-genesis uniqueness, mutation denial, and idempotent migration
re-application before dropping the disposable database. The test is disabled
unless the explicit ephemeral flag is set and the database target is the
localhost genesis_ci test instance. It does not use or modify Railway data.

## Separate staging migration approval gate
1. Record the staging deployment SHA, existing schema/role grants, evidence
   row count and final digest using a separately authorized read-only account.
2. Perform independently verified encrypted backup and restore to a separate
   isolated test database; verify exact count, keys and head digest.
3. Review existing rows for duplicate genesis predecessors, forks, duplicate
   hashes and schema drift before scheduling maintenance. Do not delete evidence
   to make a migration pass.
4. Obtain explicit authorized change approval and a cutover/rollback owner.
5. Only then execute the R0.2 migration using a temporary migration identity
   and verify readiness, unchanged historical hash chain, and restored roles.
6. Rotate administrator credentials, revoke temporary access and record the
   secret lifecycle without exposing the secret itself.
7. Independently witness the resulting digest before considering it RiverOS
   evidence. A local database hash is not an external attestation.

Reversing an append-only migration in place would weaken assurances. If the
migration is incompatible, stop intake and restore a verified isolated backup
under an approved recovery plan. Never automatically drop the triggers or indexes
on a live evidence spool.
