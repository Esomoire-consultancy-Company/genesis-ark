# Lead intake and progressive disclosure

Entry: BMP enquiry → consent and purpose capture → DigitalMe principal evidence where required → Warden policy decision → permitted listing projection → Synnergyze request queue.

| Tier | May receive | Must not receive in unverified pilot |
|---|---|---|
| GUEST | Public draft teaser, stage explanation | Seller identity, privileged documents, offers |
| REGISTERED | Permissioned account enquiry state | Private title record without specific grant |
| QUALIFIED | Conditional financing / configuration workflow | Unverified commercial claims as binding |
| VERIFIED | Reviewed access to individually authorized records | Blanket estate or owner access |

Required fields: `lead_ref`, `consent_ref`, `purpose`, `estate_ref`, `requested_asset`, `requested_action`, `policy_decision_ref`, `retention_class`, `source_channel`, `created_at`.

Status events: `LEAD_RECEIVED`, `PENDING_PERMISSION`, `SPEC_READY`, `PROVIDER_REQUESTED`, `QUOTE_PENDING`, `CLOSED` or `REJECTED`. Record permitted data minimization and lawful retention before production. Client-side persona toggles in the demo do not satisfy identity or authorization.
