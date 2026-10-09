# BMP ARK Genesis v0.1

**Status: documentation-first pilot; NOT production-approved.** This module lives in the existing VSR/Genesis orchestration repository without replacing its root README.

## Mission and responsibility
BMP is the **frontend market** for governed listings, lead intake, partner discovery, JIG catalogues and property-passport experiences. **Synnergyze** composes and operates field-support and provider workflows. **Quantum Room** hosts scheduled live/spatial experiences. **Genesis** registers capabilities. **Warden** admits and governs authority. **BNR** is the wider governance/assurance network. **River** preserves evidence/provenance. **DigitalMe** anchors principal identity, contributor attribution and valid entitlements. **VSR** is the governed experiential shell; it does not itself create legal title.

## Canonical architecture
Earth → Virtual Estate → Place → Location → Door → Room → Window/Stage → Activity. A physical property is recorded as a referenced asset and associated with its Virtual Estate/Place; spatial anchors and a property passport are projected through eligible Windows/Stages.

Canonical runtime: Identity → Authority → Reachability → Orchestration → Execution → Evidence. Provider-side verification precedes Genesis capability registration, Warden admission and River evidence closure.

## Operating board
Intake → Spec Ready → Build Ready → In Progress → Warden / BNR Review → Pilot Ready → Live / Operating → Evidence Closed.

See [board](docs/BOARD.md), [architecture](docs/ARCHITECTURE.md), [pilot plan](docs/PILOT_SCOTTS_AMD.md) and [acceptance](docs/ACCEPTANCE_CHECKLIST.md).

## A-1204 reference pilot
A-1204 is an **unverified demonstration fixture**, not a published property offer. Claimed site, prices, TODAY-state description, River URI and prospective buyer schedules originate from user-supplied planning text, not validated external records. State rail: TODAY → PLANNED → FINISHED → CONFIGURED → DELIVERED. Six anchors: FLOOR_01, ARCH_01, GLAZE_01, KITCHEN_01, BALC_01, LIGHT_01.

The listing has an illustrative amount of ₹4.8 crore plus two separately scoped *unconfirmed* amounts of ₹18 lakh and ₹12 lakh. No price, inclusion, specification, warranty or property right may be represented as verified without authenticated evidence.

## Run the standalone frontend
From the **repository root**:
- Run `node arks/bmp/scripts/validate.mjs` for source/snapshot consistency.
- Run `python3 -m http.server 5173` (or another static server).
- Open `http://localhost:5173/arks/bmp/market/a-1204/`.

The frontend tries to read `docs/LISTING_TEMPLATE.md`; where a static-site renderer transforms Markdown, it falls back to the validated `listing.json` snapshot. No API, live entitlement, payment, River ingestion or provider integration is claimed.

## Do not confuse preview with execution
The visible disclosure persona selector is **not** authorization. No buyer information, title documents, privileged quotes, offers, contracts or owner transitions should be entrusted to client-side gating. Warden/BNR review happens at controlled service boundaries. Registered conveyance is external to VSR.

Issue form blueprints: repository root `.github/ISSUE_TEMPLATE/bmp-*.yml`. Label provisioning: `bash arks/bmp/scripts/create-labels.sh Esomoire-consultancy-Company/genesis-ark` after GitHub CLI authentication.
