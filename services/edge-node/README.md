# Genesis Edge Node Service

Genesis Edge Node v1 binds an already registered `genesis_runtime.runtime_nodes` record to a physical or virtual host identity. It does not create node authority by itself.

## Responsibilities

- consume a one-time hashed enrollment token;
- persist device, agent, hardware, credential-reference and attestation bindings;
- verify HMAC-signed, monotonic heartbeats within a bounded clock-skew window;
- issue Warden-capability-bound host commands;
- lease each command atomically to the enrolled Edge Agent;
- re-check capability validity immediately before local execution;
- execute through a supervisor adapter rather than direct ungoverned shell access;
- preserve disconnected node evidence in an SQLite WAL spool;
- ingest spooled evidence idempotently into a hash-linked control-plane event stream.

## Deliberate boundary

The included `DeterministicSupervisor` has no host access. A production systemd/containerd/Kubernetes adapter must implement the same `SupervisorAdapter` contract and must not bypass command leasing, capability verification or evidence emission.

Raw node secrets are not stored in the registry. `credential_reference` points to an external vault. Enrollment tokens are stored only as SHA-256 hashes and are consumed once.

## Run

```bash
python -m pip install -e './services/edge-node[postgres,test]'
EDGE_NODE_API_TOKEN=change-me \
EDGE_NODE_REPOSITORY_BACKEND=memory \
genesis-edge-node
```

The PostgreSQL backend expects migrations `001 → 002 → 003 → 004 → 005` and a database role with membership in `genesis_control_plane`.

## Test

```bash
PYTHONPATH=services/edge-node/src pytest -q services/edge-node/tests
python scripts/validate_edge_node_contracts.py
```
