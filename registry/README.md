# Registry

The registry module is the source-of-truth for all Genesis Ark identities, assets, and communication mappings.

It implements the **Observable Commerce** phygitech asset registry and the **Genesis Identity Stack**, linking Arc identities to DNS and Bluesky AT Protocol handles.

## Structure

```
registry/
├── aliases/           # Email alias mappings (Holy Grail Mail Gateway)
│   └── email-mapping.yml
├── arcs/              # Arc identity entries (Tristar key + Bluesky DID + DNS anchor)
│   └── atlas-arc-vjripl.yml
├── nodes/             # Virtual Silk Road network node entries
└── licenses/          # EmpireOS license registry entries
```

## Identity Stack

```
Tristar Key
      │
      ▼
Genesis Ark Registry (registry/arcs/)
      │
      ▼
DNS Layer (_atproto TXT record)
      │
      ▼
AT Protocol Identity (Bluesky DID)
      │
      ▼
Virtual Silk Road Network
```

## Arc Entry Format

See `schemas/arc.yml` for the full schema.

```yaml
arc_id: <arc-id>
tristar_key: <namespace>:<arc-id>:<environment>
identity:
  bluesky_handle: <handle>.bsky.social
  did: did:plc:<identifier>
  dns_anchor: <domain>
network:
  vsr_node: <node-id>
status: active
```

## Email Alias Format

See `schemas/email-mapping.yml` for the full schema.

```yaml
mappings:
  - id: <mapping-id>
    generated: <system-address>@<arc>.arcs.genesis.example
    alias: <human-alias>@<domain>
    display_name: "Human-readable name"
    target: http://gateway.genesis.example/ingest/email
    tristar_key: <namespace>:<arc-id>:<environment>
    status: active
```

## Integration

The registry is consumed by:
- `/economics` – to verify commodity-backed asset provenance
- `/governance` – to enforce licensing policies on registered assets and aliases
- `/telemetry` – to emit asset and identity lifecycle events to RiverOS
- `.github/workflows/email-mapping-sync.yml` – to validate and sync alias changes automatically

