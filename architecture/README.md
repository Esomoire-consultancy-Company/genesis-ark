# Architecture

This directory contains the system architecture for Genesis Ark, including integration maps, sequence diagrams, and component boundaries.

## Contents

| File / Folder | Description |
|---|---|
| `overview.md` | High-level platform architecture |
| `integration-map.md` | Integration relationships between sub-systems |
| `decisions/` | Architecture Decision Records (ADRs) |

## Platform Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Genesis Ark                              │
│                   (Platform Control Plane)                      │
├───────────┬───────────┬───────────┬──────────────┬─────────────┤
│  RiverOS  │ EmpireOS  │SynergizeOS│     SILK     │ Observable  │
│ Telemetry │Governance │  Planning │    Economy   │  Commerce   │
└───────────┴───────────┴───────────┴──────────────┴─────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
    /telemetry           /governance          /economics
    /core                /contracts           /registry
    /infrastructure      /applications        /devkits
```

## Architecture Principles

1. **Modular** – each sub-system is independently deployable and replaceable.
2. **Telemetry-first** – all workflows emit structured events consumed by RiverOS.
3. **Contract-governed** – cross-system interactions are mediated by smart contracts in `/contracts`.
4. **Extension-ready** – external repositories integrate via the `/devkits` SDK surface.
