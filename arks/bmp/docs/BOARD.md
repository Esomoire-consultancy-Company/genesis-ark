# GitHub Projects BMP ARK board schema

Proposed title: `BMP ARK v0.1 — Operating Board`.

**Status values, in order:**
Intake → Spec Ready → Build Ready → In Progress → Warden / BNR Review → Pilot Ready → Live / Operating → Evidence Closed.

Suggested fields:
- `Status` (single select, values above)
- `ARK` (BMP)
- `Estate / Place / Location` (text or linked registry IDs)
- `Owner` (role / DigitalMe principal ref, bind after appointment)
- `Workstream` (Market / Synnergyze / Quantum / DigitalMe / BNR / SCOTTS)
- `Risk` (P0 to P3)
- `Evidence Ref` (URL / River ref)
- `Policy Gate` (Pending / Approved / Denied / Not applicable with rationale)
- `Commercial Impact` (estimate and actual separately)
- `Target Date`, `Accepted Date`.

**Important:** Project-board field creation is not performed by these documents. GitHub issue templates, labels and CI are delivered as code; the GitHub Projects board itself requires a separately authorized supported Projects operation or manual creation.

Pilot epic candidate: `[BMP/A-1204] Establish governed property passport and demo showing` with tasks intake, anchor specs, front-end, resolver, review and evidence closure.
