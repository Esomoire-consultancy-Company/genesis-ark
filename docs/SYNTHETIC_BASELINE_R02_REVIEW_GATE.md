# Synthetic Baseline R0.2 — first source-controlled admission gate

This is a **bootstrap review slice** of the larger locally tested R0.2 package, not the complete simulator or its 37-test suite.

## Scope committed here

- Canonical *fictional* identities, Commons membership, BNR representation, synthetic licence contracts, and supplier boundaries.
- A 17-scenario, frozen-clock, standard-library permission test oracle.
- Read-only Actions check. No deployment, secrets, operational authority, provider connection, or payments.

The full local R0.2 source package has additional files: a localhost-only workbench, extended tests, fixture hash locks, browser QA, and consumer compatibility documentation. They **are not in this first GitHub import**. This PR must stay draft until the full source and safeguards have been reviewed and committed. Do not merge this partial bootstrap as a claim of complete R0.2 acceptance.

## Commands
    python3 synthetic-baseline/verify.py

## Security boundary

Even an ALLOW from the synthetic oracle is only a fictional expected outcome. This script is non-executable and cannot issue actual Warden tokens, create accounts, represent a legal person, act for a BNR node or write RiverOS production receipts.

## Expected release work

Import the remaining 22-source-file workbench package; check fixture SHA-256 against approved review evidence; independently adapt the Creators Door and control-plane consumer test doubles; run exact-head CI; then obtain human approval. Never map synthetic ALLOW directly to a live authority grant.
