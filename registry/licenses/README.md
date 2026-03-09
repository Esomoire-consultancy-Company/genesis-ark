# Licenses

This directory contains license definitions and enforcement records for Genesis Ark.

Each YAML file represents a license issued under the EmpireOS governance layer.

## License Record Format

```yaml
license_id: <license-id>
tristar_key: <tristar-key>

holder:
  name: <display-name>
  did: did:genesis:<owner-id>

scope:
  modules: []     # List of platform modules covered
  arcs: []        # List of Arc IDs covered

issued_at: <ISO-8601 timestamp>
expires_at: <ISO-8601 timestamp>

status: active | suspended | revoked
```

## Integration

- **Governance** – EmpireOS evaluates license validity at policy enforcement time
- **Registry / Arcs** – Arcs may reference a license for access control
- **Contracts** – On-chain enforcement of license terms via smart contracts
