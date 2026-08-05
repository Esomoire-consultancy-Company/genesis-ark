# Genesis Warden Service

Deny-by-default policy, capability and emergency-control service for the Warden-Enabled Actor Box.

## Operations

- `POST /v1/policy-decisions/evaluate`
- `POST /v1/capabilities/issue`
- `POST /v1/capabilities/{capabilityId}/revoke`
- `POST /v1/boxes/{boxId}/lock`
- `GET /v1/boxes/{boxId}/control-state`

Every operation requires a bearer token and a trusted mTLS-ingress assertion. The ingress must remove caller-supplied verification headers and inject them only after certificate validation.

## Repository modes

`memory` is for tests and local contract development. `postgres` is the authoritative PostgreSQL/Supabase adapter. It uses pooled transactional connections, per-Box advisory locks and atomic state-plus-evidence writes.

Unknown-Box denials are recorded in the separate unbound decision/evidence ledger rather than being dropped or forced through foreign keys to registered Box state.

```bash
cd services/warden
python -m pip install -e '.[postgres,test]'
export WARDEN_REPOSITORY_BACKEND=postgres
export WARDEN_DATABASE_URL='<protected connection string>'
export WARDEN_API_TOKEN='<secret>'
warden-service
```

`WARDEN_DATABASE_PREPARE_THRESHOLD` defaults to `none`, which is compatible with Supavisor/PgBouncer transaction mode. Persistent deployments should normally use a direct or session-pool connection.

## Container

Build from the repository root:

```bash
docker build -f services/warden/Dockerfile -t genesis-warden .
```

The image runs as a non-root user. It does not contain database credentials.

## Test

```bash
PYTHONPATH=services/warden/src pytest -q services/warden/tests
```

The suite covers deny-by-default evaluation, runtime and boundary failures, delegated restrictions, capability lifecycle, emergency lock, evidence chaining and authoritative transaction construction.
