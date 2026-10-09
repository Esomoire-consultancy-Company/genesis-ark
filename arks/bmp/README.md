# BMP ARK Genesis v0.1

**Status: documentation-first pilot; NOT production-approved.** This module lives in the existing VSR/Genesis orchestration repository without replacing its root README.

## Mission and responsibility
BMP is the **frontend market** for governed listings, lead intake, partner discovery, JIG catalogues and property-passport experiences. **Synnergyze** composes and operates field-support and provider workflows. **Quantum Room** hosts scheduled live/spatial experiences. **Genesis** registers capabilities. **Warden** admits and governs authority. **BNR** is the wider governance/assurance network. **River** preserves evidence/provenance. **DigitalMe** anchors principal identity, contributor attribution and valid entitlements. **VSR** is the governed experiential shell; it does not itself create legal title.

## Canonical architecture
Earth → Virtual Estate → Place → Location → Door → Room → Window/Stage → Activity. A physical property is recorded as a referenced asset and associated with its Virtual Estate/Place; spatial anchors and a property passport are projected through eligible Windows/Stages.

Canonical runtime: Identity → Authority → Reachability → Orchestration → Execution → Evidence. Provider-side verification precedes Genesis capability registration, Warden admission and River evidence closure.

## Operating board
Intake → Spec Ready → Build Ready → In Progress → Warden / BNR Review → Pilot Ready → Live / Operating → Evidence Closed.

See [board](docs/BOARD.md), [architecture](docs/ARCHITECTURE.md), [pilot plan](docs/PILOT_SCOTTS_AMD.md), [property experience R0.5](docs/PROPERTY_EXPERIENCE_R05.md), [Door resolver R0.6](docs/DOOR_RESOLVER_R06.md), [Service Federation R0.7](docs/SERVICE_FEDERATION_R07.md), [Provider Admission R0.8](docs/PROVIDER_ADMISSION_R08.md), [Release Assurance R0.9](docs/RELEASE_ASSURANCE_R09.md) and [acceptance](docs/ACCEPTANCE_CHECKLIST.md).

## A-1204 reference pilot

**Presentation-only disclaimer (R0.3): Every amount, cost, price, fee, commission percentage, component/replacement value and bundle figure in this BMP A-1204 demonstration is included solely for visual depiction and interface presentation. None is a verified quotation, valuation, financial forecast, payable amount, approved rate or binding offer. Original figures are preserved as examples, not commercially reconciled or certified.**

A-1204 is an **unverified demonstration fixture**, not a published property offer. Claimed site, prices, TODAY-state description, River URI and prospective buyer schedules originate from user-supplied planning text, not validated external records. State rail: TODAY → PLANNED → FINISHED → CONFIGURED → DELIVERED. Six anchors: FLOOR_01, ARCH_01, GLAZE_01, KITCHEN_01, BALC_01, LIGHT_01.

The listing displays sample amounts of ₹4.8 crore, ₹18 lakh and ₹12 lakh solely for depiction. They are not validated or reconciled commercial figures. No price, inclusion, specification, warranty or property right may be represented as verified without authenticated evidence.

## Run the standalone frontend
From the **repository root**:
- Run `node arks/bmp/scripts/validate.mjs` for source/snapshot consistency.
- Run `python3 -m http.server 5173` (or another static server).
- Open `http://localhost:5173/arks/bmp/market/a-1204/`.

The frontend tries to read `docs/LISTING_TEMPLATE.md`; where a static-site renderer transforms Markdown, it falls back to the validated `listing.json` snapshot. No API, live entitlement, payment, River ingestion or provider integration is claimed.

## Do not confuse preview with execution
The visible disclosure persona selector is **not** authorization. No buyer information, title documents, privileged quotes, offers, contracts or owner transitions should be entrusted to client-side gating. Warden/BNR review happens at controlled service boundaries. Registered conveyance is external to VSR.

Issue form blueprints: repository root `.github/ISSUE_TEMPLATE/bmp-*.yml`. Label provisioning: `bash arks/bmp/scripts/create-labels.sh Esomoire-consultancy-Company/genesis-ark` after GitHub CLI authentication.
