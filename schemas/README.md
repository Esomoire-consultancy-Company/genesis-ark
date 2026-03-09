# Schemas

This directory contains YAML schemas that define and validate registry entries used across Genesis Ark.

Schemas are used by:
- The `email-mapping-sync` GitHub Actions workflow to validate alias entries before sync.
- The governance policy engine to verify entry structure before acceptance.
- Developer tools in `/devkits` for generating and linting registry files.

## Schemas

| File | Validates | Status |
|---|---|---|
| `arc.yml` | Arc registry entries (`registry/arcs/*.yml`) | Available |
| `email-mapping.yml` | Email alias mappings (`registry/aliases/email-mapping.yml`) | Available |
| `node.yml` | Node registry entries (`registry/nodes/*.yml`) | Planned |
| `license.yml` | License registry entries (`registry/licenses/*.yml`) | Planned |
