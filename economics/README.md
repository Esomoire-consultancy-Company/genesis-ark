# Economics

The economics module implements the **SILK** commodity-backed token economy for Genesis Ark.

SILK is the utility and value-transfer token of the Virtual Silk Road. Each SILK token is backed by a basket of real-world commodities tracked via the Observable Commerce registry.

## Contents

| File / Folder | Description |
|---|---|
| `tokenomics/` | SILK supply, backing ratio, and issuance rules |
| `treasury/` | Treasury management and reserve logic |
| `pricing/` | Commodity price feeds and oracle integrations |
| `flows/` | Value flow models between platform participants |

## SILK Token Properties

| Property | Value |
|---|---|
| Symbol | `SILK` |
| Backing | Commodity basket (tracked in `/registry`) |
| Issuance | Governance-controlled (`/governance`) |
| Contracts | Defined in `/contracts` |

## Integration

- **Registry** – commodity assets are registered in `/registry` to back SILK supply
- **Contracts** – issuance and redemption logic in `/contracts/silk/`
- **Governance** – EmpireOS controls issuance policy via `/governance`
- **Telemetry** – treasury events streamed to RiverOS via `/telemetry`
