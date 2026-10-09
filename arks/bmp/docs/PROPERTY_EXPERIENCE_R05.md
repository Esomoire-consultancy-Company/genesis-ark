# BMP A-1204 Property Experience R0.5

**Status:** static, unverified demonstration; no real property/quote/admission/booking/River receipt claims.

## What is actually implemented
1. Five mutually exclusive stage choices: TODAY, PLANNED, FINISHED, CONFIGURED, DELIVERED. Each offers stage-specific explanation and a prominent statement that the visual is conceptual. TODAY descriptions are not treated as authenticated photographs; FINISHED is not an as-built certificate.
2. Six keyboard-accessible anchor buttons. Selection opens an accessible native `dialog` with current reference, proposed finish, source inclusion, supplier, warranty and evidence ref/status. Everything is labelled unverified. The dialog returns focus to its originating button when closed.
3. QR/Door **link preview** using `getDoorPreview` backed by the R0.2 URL contract. The preview uses reserved `https://example.invalid`, not an asserted real domain. It includes only property navigation state, anchor and locale. Copying is allowed for developer demonstration, but the destination is inactive and no QR is activated.
4. The property URL's `state`, `anchor` and `locale` may initialize a conceptual view through whitelisted `interpretUntrustedDoorUrl`. Any `buyer`, `disclosure`, `river`, `rights`, `role` or token-looking parameter confers **zero privileges**. Effective disclosure remains GUEST.
5. The R0.4 `DEPICTION_ONLY` contract remains in force. Exact sample display amounts ₹4.80 Cr, ₹5.21 Cr, ₹5.41 Cr remain visual labels; nothing is calculated, quoted or chargeable.
6. Original Synnergyze resolver is explicitly a simulation; no Warden policy, Genesis provider, Quantum Room scheduling or River ingest call is performed.

## Architecture alignment
- `Earth → Virtual Estate → Place → Location → Door → Room → Window/Stage → Activity` is the spatial navigation spine.
- `Identity → Authority → Reachability → Orchestration → Execution → Evidence` is the runtime pipeline for future integrations.
- `Window/Stage` is not a transport for privileged facts: admission stays server-side. Shared evidence IDs never become `verified` because a UI can display them.

## Verification
```bash
node arks/bmp/scripts/validate.mjs
node arks/bmp/scripts/validate-presentation.mjs
node arks/bmp/scripts/validate-door-entry.mjs
node arks/bmp/scripts/validate-experience.mjs
```

Tests cover five stage semantics, each of six anchors in all five states, rejection of unknown anchors/states and transaction-enabled fixtures, inactive `example.invalid` links, and QR parameter tampering.

## Not implemented
Actual buyer QR generation/activation, license-cleared construction photo, BIM/render media, site measurement, verified suppliers/warranties, Warden decisions, DigitalMe sessions, River receipts, booking, payments, commercial offer, contract, legal conveyance, or production property resolver. An accessible dialog is not an identity gate.

## Next R0.6 candidate
Implement a separately deployed, server-governed Door resolver and event envelope with authenticated/guest admission, rate limits, trace IDs, policy decision references and River receipt adapter. Keep this R0.5 static artifact isolated until authorization and deployment evidence exist.
