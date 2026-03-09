# Schemas

This directory contains JSON Schema definitions (YAML format) for Genesis Ark registry entries.

| Schema File | Description |
|---|---|
| `arc.yml` | Schema for Arc identity registry entries |
| `email-mapping.yml` | Schema for Holy Grail email alias mappings |
| `node.schema.yml` | Schema for VSR node registration records |
| `license.schema.yml` | Schema for license definitions |

## Usage

Schemas are referenced by the CI workflow (`.github/workflows/email-mapping-sync.yml`)
to validate registry entries on every pull request.

Schemas use [JSON Schema draft-07](https://json-schema.org/specification-links#draft-7) format,
expressed as YAML for readability.
