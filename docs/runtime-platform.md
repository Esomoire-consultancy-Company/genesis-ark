# Genesis Runtime Platform

Status: **Executable foundation v1**

The Genesis Runtime Platform is the governed execution fabric beneath Actor Boxes, CloudBrowser, agents, workspaces, merchant operations, vehicles and future specialist runtimes. It does not originate authority. It provisions and operates only runtime state backed by registered Actor Boxes, active Warden capabilities and attested infrastructure.

## Runtime authority chain

```text
Anchor authority
  → BNR / VSR Registry state
  → DigitalMe principal and representation
  → Warden policy decision and capability
  → Genesis Runtime Manager
  → runtime instance, session and resources
  → durable runtime event outbox
  → RiverOS evidence consumers
```

## Binding invariants

1. A runtime instance is bound to one registered Actor Box.
2. An instance cannot become `ACTIVE` until its runtime integrity is `ATTESTED`.
3. A runtime session requires a live Warden capability for `RUNTIME_SESSION_START` or `RUNTIME_MANAGE`.
4. Resource allocation requires a live Warden capability for `RUNTIME_RESOURCE_ALLOCATE` or `RUNTIME_MANAGE`.
5. Session expiry cannot exceed capability expiry or the platform session ceiling.
6. Runtime node capacity and instance resource limits are enforced independently.
7. Every material lifecycle transition produces a hash-linked runtime event.
8. Runtime events are durable outbox records; downstream delivery does not erase local evidence.
9. Critical health never triggers autonomous recovery. It creates a recovery job in `AUTHORIZATION_REQUIRED` state.
10. Recovery execution requires a separate Warden capability for `RUNTIME_RECOVERY_EXECUTE`.

## First executable slice

- runtime node registration;
- capacity-aware instance provisioning;
- instance attestation and activation;
- capability-aware session creation;
- capability-aware resource allocation;
- health reporting and recovery escalation;
- session termination and allocation release;
- durable, per-aggregate event hash chains;
- PostgreSQL/Supabase adapter and private-schema migration;
- in-memory adapter for deterministic tests.

## Deliberately outside this slice

- Kubernetes or Nomad scheduling;
- remote host agents;
- automatic runtime placement optimisation;
- event relay to an external broker;
- recovery execution;
- runtime snapshots and cross-node migration;
- production deployment to a live Supabase project.
