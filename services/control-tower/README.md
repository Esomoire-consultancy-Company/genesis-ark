# Genesis Control Tower

Governed fleet inventory, incident management, command approval/dispatch, dashboard projection and audit evidence for Genesis runtimes and Edge Nodes.

## Security boundary

- API access requires trusted-ingress mTLS confirmation plus a bearer token.
- Fleet state is accepted only as versioned observations; stale observations are rejected.
- Signals are idempotent by `signal_id` and correlated into one active incident per fingerprint.
- Incident acknowledgement and resolution require active Warden capabilities.
- Every fleet command requires an issue capability.
- High-impact commands require an independent approver and a separate approval capability.
- Dispatch revalidates a current Warden capability immediately before emitting `EDGE_COMMAND_REQUESTED`.
- Events are hash-linked per aggregate and remain unpublished in a durable outbox until an external RiverOS relay marks them published.

## Run locally

```bash
python -m pip install -e '.[test]'
CONTROL_TOWER_API_TOKEN=local-token genesis-control-tower
```

The in-memory repository is for tests and local development only. Use `CONTROL_TOWER_REPOSITORY_BACKEND=postgres` and `CONTROL_TOWER_DATABASE_URL` for authoritative state.

## Migration

Apply `db/control-tower/v1/006_genesis_control_tower.sql` only after migrations `001` through `005`.
