# Applications

The applications module contains platform-level applications and workflow modules built on the Genesis Ark control plane.

These applications leverage the integrated sub-systems (RiverOS, EmpireOS, SynergizeOS, SILK, Observable Commerce) to deliver end-to-end Virtual Silk Road functionality.

## Contents

| File / Folder | Description |
|---|---|
| `synergize/` | SynergizeOS operational planning module |
| `marketplace/` | SILK-denominated marketplace application |
| `asset-tracker/` | Observable Commerce phygitech tracker |
| `analytics/` | Telemetry-driven analytics dashboard |

## Adding a New Application

1. Create a subdirectory under `applications/`.
2. Add a `README.md` describing the application.
3. Register the application in the service registry (`/registry`).
4. Instrument the application to emit telemetry events (`/telemetry/schemas`).
5. Define any governance policies required (`/governance`).

## Extension

External teams can contribute applications from independent repositories using the `/devkits` SDK. See [`devkits/README.md`](../devkits/README.md).
