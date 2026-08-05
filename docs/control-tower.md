# Genesis Control Tower v1

The Control Tower is the governed operational command and observability layer above the Genesis Runtime Platform and Genesis Edge Nodes. It is not a registry authority and cannot create ownership, identity, Box, node or recovery authority.

## Authority path

```text
Anchor / BNR registered state
  → DigitalMe principal
  → Warden capability
  → Control Tower authorization queue
  → Edge Node command queue
  → local Edge Agent execution
  → RiverOS evidence publication
```

## Fleet read model

The fleet dashboard is a derived operational snapshot. Runtime Node registration remains in `genesis_runtime.runtime_nodes`; Edge identity and heartbeat state remain in `genesis_edge`. Control Tower snapshots may be rebuilt and never supersede those source records.

Effective node state uses the following precedence:

1. Retired
2. Quarantined
3. Draining
4. Offline by source state or heartbeat threshold
5. Degraded by source state or heartbeat threshold
6. Online
7. Unknown

Offline, quarantined and degraded observations create deduplicated system incidents. A healthy observation resolves only system-created incidents; manual incidents remain under operator control.

## Governed commands

A command request starts in `AUTHORIZATION_REQUIRED`. Approval verifies the Warden capability against the node and exact Edge action. Dispatch is a separate operation and re-verifies the same capability immediately before atomically inserting the command into `genesis_edge.edge_commands`. Revocation therefore takes precedence over earlier approval.

Control Tower v1 requires the authorizing DigitalMe Actor to dispatch the command. Delegated dispatch requires a future explicit delegation record and is not inferred.

## Evidence publication

Runtime, Edge and Control Tower events remain in their source outboxes until a publisher acquires a bounded lease. Acknowledgement must cover exactly the leased event set and records a destination reference for every item. Expired leases may be reclaimed; duplicate publication acknowledgement is rejected.

## Deployment boundary

No unrestricted shell execution, firmware installation, cross-node migration, production Supabase migration or live RiverOS delivery is included in this slice. The publisher contract ends at lease and acknowledgement.
