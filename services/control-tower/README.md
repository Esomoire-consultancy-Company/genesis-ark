# Genesis Control Tower v1

Governed fleet operations over the Genesis Runtime Platform and Edge Node control planes.

The service does not originate node, Box, command or recovery authority. It builds operational read models from registered Runtime/Edge state and requires an active Warden capability before an authorized command can be dispatched to the Edge Node queue.

## Capabilities

- Fleet refresh and effective node-state calculation.
- Automatic offline, degraded and quarantine incidents.
- Explicit incident lifecycle transitions.
- Two-step command authorization and dispatch with revocation re-check.
- Dashboard scorecard for nodes, incidents, command queues and unpublished evidence.
- Durable leasing and exact acknowledgement of Runtime, Edge and Control Tower evidence outboxes.
- In-memory and PostgreSQL/Supabase repository adapters.

## Run

```bash
export CONTROL_TOWER_API_TOKEN='replace-me'
python -m control_tower_service
```

All endpoints require bearer authentication and a trusted mutual-TLS assertion header.
