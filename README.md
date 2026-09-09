# genesis-ark
Root orchestration repository for the Virtual Silk Road and Genesis Stack ecosystem.

## Knowledge Hub Proxy Blueprint
- Reference architecture for an enterprise-wide “holy grail” knowledge hub proxy with Virtual Silk Road sub-arcs: `docs/knowledge-hub-proxy.md`.
- Example Helm values for deploying the proxy and its partner-facing slices: `docs/snippets/knowledge-hub-proxy.values.yaml`.

## Genesis Engineering Station Alpha Control Plane

The first governed execution slice for `GES-ALPHA-001` lives under `control-plane/`.

- Design: `docs/superpowers/specs/2026-09-09-genesis-engineering-station-alpha-design.md`
- Implementation plan: `docs/superpowers/plans/2026-09-09-genesis-engineering-station-alpha.md`
- Operator/setup guide: `control-plane/README.md`
- Verification record: `docs/evidence/GES-ALPHA-CONTROL-PLANE-R0.1.md`

R0.1 is Alpha-only and remains E2 until the real Docker acceptance suite passes on the registered Alpha station.

## Smart Textile Product Passport Registry

The R0.1 smart-textile taxonomy, compatibility compiler, human-readable SKU grammar, and DPP-ready passport contracts live under `smart-textiles/`.

- Design: `docs/superpowers/specs/2026-09-09-smart-textile-product-passport-registry-design.md`
- Implementation plan: `docs/superpowers/plans/2026-09-09-smart-textile-product-passport-registry.md`
- Operator guide: `smart-textiles/README.md`
