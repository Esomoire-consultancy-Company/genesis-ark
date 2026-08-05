# Genesis Edge Node Agent v1

## Position in the governed execution fabric

```text
Registered Runtime Node
        ↓
One-time Edge enrollment
        ↓
Vault-bound node credential + attestation
        ↓
Signed heartbeat and command lease channel
        ↓
Local Supervisor Adapter
        ↓
Actor Box / CloudBrowser / Agent runtimes
        ↓
SQLite offline evidence spool
        ↓
RiverOS-compatible evidence outbox
```

The Edge Node is a host execution and observation layer. It does not originate legal authority, Box authority, policy or recovery authority. Those must already exist in the registry and Warden capability state.

## Enrollment

An Edge identity can be created only when:

1. the Runtime Node already exists in `genesis_runtime.runtime_nodes`;
2. an unconsumed, unexpired enrollment token exists for that node;
3. the submitted token hashes to the stored token hash;
4. the request binds a stable `device_id`, `agent_id`, hardware fingerprint, agent version, vault credential reference and attestation reference.

The raw bootstrap token is never persisted. The node credential remains in an external vault.

## Heartbeat integrity

Each heartbeat is signed over canonical JSON containing the node ID, sequence, timestamp, agent version, attestation reference, runtime digest, state and metrics. The controller rejects:

- invalid signatures;
- unknown credential references;
- replayed or out-of-order sequences;
- timestamps outside the configured skew window;
- attestation-reference substitution.

A node cannot clear `QUARANTINED` or `DRAINING` state merely by claiming a healthier state in its own heartbeat.

## Command lifecycle

```text
PENDING → LEASED → SUCCEEDED | FAILED
             ↘ lease expiry → LEASED again, within attempt limit
```

Every command is bound to:

- one Edge Node;
- one Warden capability;
- one required capability action;
- one target reference;
- one expiry;
- one enrolled Edge Agent lease at a time.

The controller verifies the capability when the command is issued. The Edge Agent verifies it again immediately before local execution, preserving revocation precedence.

## Offline evidence

The node-side SQLite spool uses WAL mode and full synchronous durability. Local events receive monotonic sequences and a SHA-256 local hash chain. Flush batches are HMAC-signed and ingested idempotently. The controller preserves the original local sequence/hash inside a separate central evidence chain.

## Not included in v1

- unrestricted shell command execution;
- automatic recovery without a `RUNTIME_RECOVERY_EXECUTE` capability;
- cross-node runtime migration;
- snapshot transfer;
- remote firmware installation;
- direct secret delivery to applications or agents;
- production systemd, containerd or Kubernetes supervisor adapters.
