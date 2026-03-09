# Schemas

This directory contains YAML schemas for Genesis Ark registry entries.

| Schema File | Description |
|---|---|
| `arc.schema.yml` | Schema for Arc identity registry entries |
| `email-mapping.schema.yml` | Schema for Holy Grail email alias mappings |
| `node.schema.yml` | Schema for VSR node registration records |
| `license.schema.yml` | Schema for license definitions |

## Usage

Schemas are referenced by the CI workflow (`.github/workflows/email-mapping-sync.yml`)
to validate registry entries on every pull request.
