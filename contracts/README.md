# Contracts

The contracts module contains **smart contracts** for Genesis Ark, covering:

- SILK token issuance, transfer, and redemption
- EmpireOS licensing agreements
- Observable Commerce asset registration and ownership
- Cross-module governance votes and policy enforcement

## Contents

| File / Folder | Description |
|---|---|
| `silk/` | SILK token contracts |
| `governance/` | Governance and voting contracts |
| `registry/` | Asset registration contracts |
| `licensing/` | EmpireOS licensing contracts |
| `interfaces/` | Shared contract interfaces |

## Design Principles

1. **Minimal on-chain logic** – keep contracts focused; move complexity off-chain.
2. **Upgradeable** – use proxy patterns where long-term upgradability is required.
3. **Auditable** – all state-changing operations emit events for RiverOS.
4. **Access-controlled** – roles are managed by the governance module.

## Deployment

Contracts are deployed and managed via the tooling in `/devkits/contract-tools/`. See that module's README for deployment instructions.
