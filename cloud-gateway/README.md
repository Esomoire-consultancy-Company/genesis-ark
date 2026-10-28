# Genesis ARK Cloud Gateway — R0.1

Universal, cloud-deployable, **deny-only decision intake** for Genesis ARK. This
is an isolated service, not a replacement for the local GES Alpha control plane.
It deliberately does **not** authorize execution, grant Warden permits, accept
client-provided authority, talk to the Docker daemon, or perform settlement.

## API contract

- `GET /healthz` — liveness only. A 200 response does **not** mean safe to deploy operations.
- `GET /readyz` — 200 only when the API issuer is configured, the PostgreSQL spool
  exists, and the database is reachable; reports `mode: deny-only`.
- `POST /v1/intents` — requires a server-provisioned bearer token; records a
  `warden.decision.denied` event in PostgreSQL **before** returning a denial receipt.
  Reuses of `request_id` are idempotent only for identical issuer and intent.

This spool is a preliminary event buffer, **not** the authoritative RiverOS
ledger. The schema cannot be treated as federation evidence or settlement proof
without a separately governed RiverOS connector, verification and replication.

## Installation and local test

```bash
cd cloud-gateway
python -m pip install -e '.[test]'
pytest -q
```

## Database provisioning

Create a PostgreSQL service **in a staging Railway environment**, with a
separate migration role and restricted runtime role. Apply:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/001_gateway_evidence.sql
```

The runtime database user must be restricted to SELECT and INSERT for the
`gateway_evidence` table, with sequence USAGE required by BIGSERIAL. Migration privileges
must not be present in the runtime credentials. Protect the spool against
alteration and deletion by the application account, and use external backup,
retention, reconciliation, and immutable export controls before any production claim.

## Railway service configuration

Attach the GitHub repository as a **new service**, with **Root Directory** set to
`/cloud-gateway` (leave the old `genesis-ark` service untouched). Use Railpack,
Python 3.11+ and the explicit start command:

```bash
uvicorn genesis_gateway.app:app --host 0.0.0.0 --port ${PORT:-8000}
```

Set `DATABASE_URL` (Railway PostgreSQL reference), `GENESIS_GATEWAY_API_KEY`
(random secret of >=32 characters), and `GENESIS_GATEWAY_ISSUER_ID` (immutable
provisioned DigitalMe Actor/service issuer). Never put keys in GitHub or issue
production credentials through a chat message. Configure Railway's healthcheck
path as `/readyz` after completing DB provisioning.

Initial service deployment intentionally fails readiness until provisioned.
Never attach the host Docker socket, give the gateway Docker administrator
permissions, or make the local Alpha executor public.

## One-shot staging migration and restricted role

**Never configure the gateway's `DATABASE_URL` from the Postgres service's
administrator/superuser connection string.** The HTTP service must not hold
schema-creation privileges. This is an operator-controlled, staging-only
bootstrap, not a web startup hook.

From a trusted, temporary migration environment that can reach staging
PostgreSQL, supply secret values as environment variables (not CLI arguments):

- `GENESIS_MIGRATION_ADMIN_DATABASE_URL` — the **staging** PostgreSQL
  administrator connection string (use only in the temporary migration job)
- `GENESIS_GATEWAY_RUNTIME_ROLE` — a new dedicated PostgreSQL role named
  `genesis_gateway_...`
- `GENESIS_GATEWAY_DB_PASSWORD` — independent random string of at least 32
  characters; do not print or commit it

Then execute:

```bash
cd cloud-gateway
python -m pip install -r requirements.txt
python -m genesis_gateway.provision
```

The bootstrap creates `gateway_evidence` and grants the new runtime role
only schema usage, table SELECT/INSERT, and evidence sequence USAGE. It rejects
pre-existing role names; it does not alter an existing role or grant UPDATE/
DELETE/DDL. Provision a new secret for the app and attach a runtime-role
`DATABASE_URL` to the gateway through Railway variables. Keep the administrator
URL solely in the short-lived migration environment.

This release does **not** include a remote SQL executor. The migration is
**not provisioned with the restricted runtime role** until the one-shot command
has run against staging and its success has been independently checked. A manual
`psql` migration creates only the table; it does not provision runtime credentials. The PostgreSQL 18
contract workflow runs against a disposable CI database, never the user's
Railway services.

After provisioning: check `GET /readyz` for a 200 response with
`mode: deny-only`, and exercise `POST /v1/intents` with a scoped staging
issuer credential, verifying repeat/denial receipts. Never infer these from a
green image build alone.

## Known limits / upgrade gates

1. The bearer key authenticates a **single pre-provisioned service issuer**, not
   end-user identity. SSO, issuer rotation and network-level restrictions remain
   separate work.
2. All intents return `DENY` by design. Real Warden decision validation and
   capability authorization are **not** implemented in this milestone.
3. The local PostgreSQL event spool uses a serialized SHA-256 hash chain, but
   is not externally witnessed, tamper-proof, or the RiverOS canonical ledger.
4. The DB migration is manual, and application roles/backup policies must be
   configured by an operator. Run migrations before treating `/readyz` as ready.
5. No frontend, execution adapters, settlement, or federation endpoints are
   enabled. No production cutover is authorized by this scaffold.
