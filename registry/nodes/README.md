# Nodes

This directory contains VSR (Virtual Silk Road) node registration records for Genesis Ark.

Each YAML file represents a registered network node.

## Node Record Format

```yaml
node_id: <node-id>
tristar_key: <tristar-key>

location:
  region: <region>
  city: <city>

network:
  hostname: <hostname>
  protocol: vsr

status: active | suspended | deregistered
```

## Integration

- **Registry / Arcs** – Arcs reference nodes via `network.vsr_node`
- **Telemetry** – Node health and heartbeat events streamed to RiverOS
- **Governance** – Node eligibility enforced by EmpireOS policies
