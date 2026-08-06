# Genesis Control Tower v1

## Role

Genesis Control Tower is the governed operational projection over registered runtime, Edge Node, Actor Box and browser state. It does not create legal or operational authority. Commands execute only after the relevant Warden capabilities are verified and the Edge Node accepts the resulting command request.

Canonical authority flow:

```text
Anchor / owner / operator authority
→ BNR canonical registration
→ DigitalMe principal and representation
→ Warden capability and approval
→ Genesis Control Tower operational decision
→ Edge Node or Runtime Manager execution
→ RiverOS evidence publication
→ SILK settlement where value moves
```

## Implemented scope

### Fleet projection

Control Tower stores the latest accepted observation for each managed asset. Observations include the anchor, owner, region, jurisdiction, status, health score, attestation reference, policy version and source metadata. Older observations cannot overwrite newer canonical state.

### Incident centre

Operational signals are idempotent by `signal_id`. Signals sharing an active fingerprint correlate into one incident, increase its occurrence count and can escalate severity. Acknowledgement and resolution are capability-gated and evidence-producing.

### Governed command queue

Every command requires an active `CONTROL_TOWER_COMMAND_ISSUE` capability. Low-impact diagnostics and log collection become approved immediately. High-impact actions require a second DigitalMe principal with `CONTROL_TOWER_COMMAND_APPROVE`; the issuer cannot approve their own command. Dispatch requires a fresh `CONTROL_TOWER_COMMAND_DISPATCH` capability and emits an `EDGE_COMMAND_REQUESTED` outbox event.

### Dashboard and audit

Dashboard values are projections from canonical Control Tower tables whose material transitions also produce hash-linked evidence events. The events table is a durable RiverOS publication outbox; `published_at` remains null until an external relay confirms publication.

## Data boundary

The `genesis_control_tower` schema is private. RLS is enabled on all tables. `anon` and `authenticated` receive no table access. The private `genesis_control_plane` role receives explicit access. Security-invoker views expose only open incidents and aggregate fleet status to that role.

## Deliberate exclusions

Control Tower v1 does not:

- bypass Warden or originate authority;
- run arbitrary host commands;
- install firmware or runtime upgrades directly;
- execute cross-node migration;
- replace BNR, RiverOS, SILK or specialist telemetry systems;
- claim production readiness without a live PostgreSQL/Supabase integration run and operational deployment review.
