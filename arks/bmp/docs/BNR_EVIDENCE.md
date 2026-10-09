# BNR / Warden evidence review

The acceptance ledger is **nine controls**:
1. Identity provenance
2. Permission / lawful authority
3. Place, asset, context and jurisdiction
4. Authorized action and workflow instance
5. Source-backed evidence and hashes
6. Warden admission/review decision (or policy-documented N/A)
7. BNR assurance review (or policy-documented N/A)
8. Outcome with accountable operator
9. Record closure and retention reference

A River-looking URL is not evidence until the object exists, is retrievable by authorized reviewers, integrity is verified and issuer/source are authenticated. The sample `river://a-1204/floor/marble/spec#abc123` is a **placeholder, not a validated receipt**.

Evidence schema proposal: `record_ref`, `asset_ref`, `anchor_ref`, `issuer`, `event_time`, `content_digest`, `source_uri`, `custody_chain`, `policy_decision_ref`, `verification_state`, `retention_rule`. Keep financial contracts, identity documents, title and consent in protected storage, never an open repo.

Governance and evidence are separate: Warden grants/denies admission; BNR can perform network assurance; River persists receipts and provenance. No assertion of cryptographic security without actual verification.
