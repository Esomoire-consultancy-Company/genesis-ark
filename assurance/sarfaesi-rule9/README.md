# SARFAESI Rule 9 Documentary Assurance R0.3

**Status:** offline screening pilot, not connected to live Genesis Gateway, Warden, RiverOS, Synnergyze, SILK or banks. **No court action or payment action is authorised by this module.**

This isolated component takes a documented auction snapshot and produces a review queue with tentative Rule 9(4) calendar dates. It does not determine legal validity, interpret court orders conclusively, certify a sale, waive obligations or trigger recovery. Designed to prevent an AI agent from treating `subject_to_outcome` as synonymous with `payment_prohibited`.

## Run

From this folder, with Node.js 20+:

```bash
node --test rule9_guard.test.mjs
node run_case.mjs fixtures/chennai-reported-case.json
```

No dependencies, credentials, API access or network connections are needed. The case fixture reflects **secondary-source reported** facts; missing original documents remain explicit. Do not commit private evidence or bank records to a public repository.

## Ownership and boundaries

- **BNR:** register case, asset and authorised actors (future integration).
- **Genesis Gateway / Synnergyze:** authenticated intake, work intent routing and evidence requests (future integration).
- **Warden:** separate policy decisions for money receipt, confirmation, sale certificate, possession and transfer. None of these permissions is emitted by this module.
- **RiverOS:** append-only authenticated evidence/provenance and corrections; this module produces no ledger writes.
- **SILK:** financial reconciliation and statutory accounting only after proof and authorised workflow, not through this screen.
- **Sentinel:** missing-evidence and calendar alerts without automatic legal judgments.

## Evidence gates

A legal reviewer must verify: signed final order; signed interim orders and service; auction confirmation date; written extension (if any); bank payment instructions; remittance proofs and account ledger; valuation; auction records; applicable IBC moratorium and asset ownership. A date-only candidate must be checked against the operative law, court orders and actual receipt records.

## LBM + OCM

- **Learn it:** capture allegations separately from judicial findings and verified bank evidence; acquire court documents.
- **Build it:** test a deterministic rule screen without side effects, register approvals and source provenance.
- **Maintain it:** version controls when law/court orders change, re-run regression tests.
- **Observe it:** monitor missing evidence, dates, status conflicts, and errors.
- **Correct it:** append a correction event referencing the original instead of overwriting an audit fact.
- **Maintain it:** require counsel sign-off on every disputed outcome and keep previous versions reproducible.

## Non-negotiable security rules

Deny-by-default. Input is untrusted; invalid dates/currency are rejected. Missing payment confirmation yields no invented deadline. Judicial restraints are never inferred from a party statement. No autonomous deposit forfeiture, resale, sale certificate, title transfer, possession enforcement or bank posting. Review dispositions are informational only.