# Service and authority boundaries — R0.1

| Layer | Owner role | Calls / contracts |
|---|---|---|
| BMP Market | Discovery / listing / leads | Read approved catalogue, request disclosure, hand off intent |
| DigitalMe | Principal / attestation / contributor | Prove identity and authenticated relationship |
| Genesis | Registered capabilities | Expose eligible provider capability metadata |
| Warden | Admission / policy / grant | Evaluate identity, permission, context and purpose before provider work |
| Synnergyze | Workflow composition / field operations | Resolve intent against capability graph and provider availability |
| Quantum Room | Spatial command and session | Schedule admitted host/guest session with scoped stage access |
| Provider network | Actual delivery | Confirm specification, cost, capacity, work and warranty |
| River | Evidence / provenance | Record tamper-evident receipts, source, issuer, timestamp and lifecycle |
| BNR | Governance / assurance | Review governance policy and closed-loop network controls |

**Runtime ordering:** Identity → Authority → Reachability → Orchestration → Execution → Evidence.

**Spatial hierarchy:** Earth → Virtual Estate → Place → Location → Door → Room → Window/Stage → Activity. Property identity, property passport and component anchor graph are associated records, not substitute hierarchy levels.

**Illustrative call trace:** POST /leads (BMP) → DigitalMe proof → Warden admission decision → Genesis capability lookup → Synnergyze resolution → provider quote request → verified commercial projection → Quantum session booking → River evidence ingestion → gated lifecycle close. These are contract sketches; no routes are asserted live.

**Ownership boundary:** BNR is not interchangeable with Warden. DigitalMe records cannot transfer registered property title. The physical operator/provider executes, not the ARK or a preview webpage.

**Admission response contract (proposed):**
- `decision_id`, `principal_ref`, `estate_ref`, `purpose`
- `resource_ref`, `allowed_actions`, `expiry`, `policy_version`
- `evidence_required`, `issuer`, `review_status`

No secrets, raw ID scans or private buyer details belong in client-side logs.
