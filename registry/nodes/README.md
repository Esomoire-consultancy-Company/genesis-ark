# Nodes

This directory contains registry entries for Virtual Silk Road network nodes.

Each node entry maps a node identifier to its network metadata, Arc affiliation, and governance status.

## Entry Format

```yaml
node_id: node-<id>
arc_id: <arc_id>            # parent Arc from registry/arcs/
hostname: <hostname>
location:
  region: <region>
  city: <city>
network:
  vsr_node: <vsr-node-id>
  endpoint: <endpoint-url>
status: active | inactive | maintenance
```

## Naming Convention

Node files are named `<node-id>.yml`, matching the `node_id` field inside the file.
