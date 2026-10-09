# Commercial Presentation Contract R0.4 — Depiction Only

**Status:** demo-only; not a ratified commercial pricing schema. Applies to all consumer-facing displays, QR-linked views, printouts, provider previews, MIS demonstrations and JIG catalogues using A-1204 data.

## Non-negotiable interpretation
All monetary values in the pilot are illustrative **depiction-only figures** to demonstrate layout and information architecture. They are not verified prices, supplier quotes, fees payable, actual costs, property valuation, taxes, commissions earned, revenue projections or binding offers.

The user-supplied examples **₹4.80 Cr**, **₹5.21 Cr**, **₹5.41 Cr**, **₹18 L**, **₹12 L**, **₹2.85 L**, **$49**, **$19**, **15%**, **3%** and **$5–10** are examples of what the interface can render, not approved amounts. **Preserve these as display examples without forcing arithmetic reconciliation or business commitments.**

## Contract
- Canonical source: `docs/LISTING_TEMPLATE.md` fenced YAML-1.2 compatible JSON.
- Snapshot: `market/a-1204/listing.json` must match canonical source.
- `schema_version=bmp.property-listing.v0.2`
- `presentation.cost_mode=DEPICTION_ONLY`
- `property_price.amount_purpose=VISUAL_MOCKUP_ONLY`
- `transaction_enabled=false`
- `presentation.quote_enabled=false`, `payment_enabled=false`, `commercial_settlement_enabled=false`.
- `presentation.arithmetic_policy=DISPLAY_EXAMPLES_AS_PROVIDED_DO_NOT_RECONCILE_OR_REPRICE`.
- `presentation.bundle_examples[].amount_display` stores user-supplied visual labels as strings.

## UI
A-1204 listing displays the disclaimer and explicit sample bundles. It must not label a number `verified`, `amount due`, `pay now`, or `approved quote` based on this file. The persona switch is a frontend preview only; it cannot admit qualified buyer access.

## Later transition to actual commerce
A production offer/transaction requires a **separate, provenance-backed contract**, not a flag flip on this fixture: legally authorized asset/operator, signed supplier quote/pricebook, policy/admission evidence, tax treatment, counterparties, scope, offer validity, offer/contract workflow and trusted evidence store. Importers must reject this demo object for settlement.

## Test
```bash
node arks/bmp/scripts/validate.mjs
node arks/bmp/scripts/validate-presentation.mjs
node arks/bmp/scripts/validate-door-entry.mjs
```
