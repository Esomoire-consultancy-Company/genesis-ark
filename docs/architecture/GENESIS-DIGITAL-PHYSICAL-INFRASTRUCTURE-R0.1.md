# Genesis Digital–Physical Infrastructure Doctrine — R0.1

**Status:** PROPOSED / source implementation; not a commissioned physical infrastructure network  
**Date:** 2026-10-28  
**Scope:** Genesis Stack, Believers Common / BNR, VSR interfaces, ARK/ARC estate, member-operated nodes  
**Change control:** Warden authority + accountable human approvals for physical operations; RiverOS evidence when an approved connector exists

## 1. Definition

**Genesis is a governed digital–physical infrastructure fabric** connecting people,
places, machines, assets, goods, utilities, software and institutions through
identity, explicit permission, operations, observation and evidence.

A website, knowledge hub, GitHub repository or cloud service is only an interface
or component of that fabric. It is not by itself evidence of an operational
factory, public service, physical node, or deployed estate.

The term *infrastructure* describes the target operating model, **not a claim of
public or governmental infrastructure designation, property ownership, or
regulatory approval**.

## 2. Three non-substitutable layers

| Plane | Responsibilities | Source of truth |
|---|---|---|
| Physical | Registered location; buildings/zones; machines; devices; utilities; safety; custody; occupancy; maintenance; physically observed state | Actual owner, operator and statutory registries, plus authorised source records |
| Digital | Identity interfaces; software inventory; connectivity; edge devices; workflow services; AI skill discovery; service lifecycle | Version-controlled code, configuration owners, providers |
| Governance and evidence | Representation, Warden authority, task permissions, contracts, work orders, exceptions, observer receipts, audit, finance | BNR/DigitalMe, Synnergyze, Warden, RiverOS and approved finance systems |

**Boundary:** Digital twins and dashboards are representations; they do not
replace physical verification or confer ownership, possession, control or licences.

## 3. Responsibility map

- **Genesis / EmpireOS:** provisioning and lifecycle control for registered devices, licences and environments.
- **BNR / DigitalMe:** member, legal-actor and location registration; chain of representation; accountable custodian.
- **Synnergyze MCP:** routing people, contracts, skills, tools, work orders and commercial processes within assigned authority.
- **Warden:** consent, policy, physical-safety and legal-authority checks at each consequential step; default DENY on missing or stale evidence.
- **Sentinel:** time-bounded observation and quality of signals; *observation is never a permission*.
- **RiverOS:** durable event and evidence trail with source, timestamps, hashes, reconciliation, retention and independent witnessing where implemented.
- **SILK:** separately authorised obligation, accounting and settlement routes, **never implied by a software receipt**.
- **VSR:** approved public and member experiences, scoped to the person's representation and the node's declared capabilities.

## 4. ARK vs ARC must never collapse

- **ARK:** a governed network/workspace within an independently owned and
  operated physical or digital location. Existing owner/operator/legal authority
  remains intact. ARK registration is **not a takeover**.
- **ARC:** a separate intervention/recovery/takeover vehicle. Activation requires
  documented standing, relevant legal and contractual authority, independent
  review, explicit scope, expiry and safe exit / handback rules.

Both can share data protocols; they must have **distinct authority chains,
contract types, transaction rights and published descriptions**.

## 5. Node passport and the physical–digital binding

A proposed node passport MUST distinguish:

1. **Identity:** stable Node ID, class, registered actor, jurisdiction and lifecycle.
2. **Physical assertion:** site and zone references, verification method/time,
   condition and applicable safety restrictions; absent for digital-only nodes.
3. **Digital assertion:** service/device IDs, approved connectors, environment,
   configuration revision and connectivity status; absent for purely physical assets.
4. **Representation:** legal supplier/owner, operating custodian, authorised
   representative and delegation evidence; all distinct where necessary.
5. **Permissions:** policy IDs, requested capability, bounded scope, expiry,
   revocation, required human authorisations and emergency stop.
6. **Evidence:** event/receipt IDs, timestamps, actor, source confidence and
   independent verification status; distinguish local spool from canonical RiverOS.
7. **Commerce:** commercial supplier, unit of service, chargeable usage, work-order
   and SILK/ledger linkage where lawfully connected.

The attached `infrastructure/` synthetic passport verifier checks **shape and
consistency only**. It is not an identity verifier, surveying instrument, building
safety certificate or Warden grant.

## 6. Mandatory lifecycle gates

```text
DISCOVER -> REGISTER -> VERIFY PHYSICAL + DIGITAL ->
CONFIRM OWNER/OPERATOR -> WARDEN REVIEW ->
SANDBOX / SIMULATE -> FIELD ACCEPTANCE ->
APPROVED ACTIVE OPERATION -> OBSERVE / CORRECT ->
MAINTAIN / REVALIDATE -> SUSPEND / RETIRE / HAND BACK
```

- Do not claim **commissioned** until all required physical and technical
  acceptance checks have passed under an authorised custodian.
- A code deploy can pass while physical readiness remains `NOT_VERIFIED`.
- If a sensor, device, person, asset or connectivity dependency fails,
  restrict/stop only the relevant authorised operation, preserve safe local
  manual procedures, and issue a work order and evidence record.
- Never infer that a remote command is safe solely from permission to view
  the same device. Commands affecting life safety, machinery, energy systems,
  mobility or access control require a separately reviewed control path.
- Use simulation and synthetic data for initial testing. No remote Docker
  adapter, machine command, utility control or payment instruction is enabled
  by this doctrine.

## 7. Persistent LBM and OCM

Every node-oriented workflow is subject to:

**LBM — Learn it → Build it → Maintain it**
- Learn: capture provenance, operational requirements, safety and legislation.
- Build: design, permission-check, test, accept and commission.
- Maintain: service intervals, owner, budget, evidence and corrective history.

**OCM — Observe it → Correct it → Maintain it**
- Observe: timestamp, physical/digital source, signal integrity, operator acknowledgement.
- Correct: authorised corrective work order, human review, reversible change.
- Maintain: periodic proof, recurrence tracking, policy and equipment lifecycle.

Neither protocol implies permission to operate the machine or use private data.

## 8. Events, actions, accounting and evidence

The transaction/accounting model MUST bind a labelled user action to its effect:

`actor -> UI control/action -> intent -> node/resource -> Warden decision ->
work order/operation -> physical or digital observation -> RiverOS receipt ->
commercial obligation / exception / settlement`

For every relevant event capture:
- `action_id`, `ui_label_version`, `actor_id`, `representation_id`
- `node_id`, `asset_id`, `requested_capability`, `policy_revision`
- `decision` / denial reason, human sign-off, execution/not-executed status
- `observation_id`, `source_timestamp`, `quality_flag`, `evidence_hash`
- `contract_id`, `billing_unit`, `charge_basis`, tax/settlement reference if applicable.

Not every click generates a financial obligation; record `non_billable` or
`no_settlement` explicitly instead of inventing an invoice.

## 9. Public Knowledge Hub

The VSR public page may disclose only approved classes, infrastructure
principles, public programme records and **verified claims**. It MUST NOT
publish private floor plans, exact access points, credentials, sensor streams,
members' personal data, privileged logs or unauthorised facility status.

Public labels must distinguish `concept`, `implemented`, `tested`,
`staging`, `operational`, `independently-witnessed`. A dated status page
must say clearly that it is not a live operational feed.

## 10. Acceptance for a first physical node

Minimum independently checkable evidence:
- lawful site/asset/contractual attachment and named real custodian;
- signed boundary between ARK registration and any ARC powers;
- verified location/zone, asset passport and physical-safety checklist;
- digital device/service identity, connectivity, software revision and rollback;
- Warden policy review with explicit DENY cases, manual override procedure;
- event receipt linking a **physical observation to a digital work order**;
- accountable owner, work-order maintenance schedule, retention and exception path;
- independent review of financial obligations and supplier-of-record.

This is the proposed acceptance contract; **no site is certified by writing this document**.

## 11. Immediate programme

R0.1: publish doctrine, synthetic passport validator and source-backed public
overview (this change).  
R0.2: register a proposed ALPHA physical pilot node and a digital-only node,
compare actual evidence completeness without claiming commissioning.  
R0.3: one owner-approved site, one machine or zone, one authorised observation,
one maintenance work order, one reconciled RiverOS receipt.  
R1.0: independent physical, cyber, legal and financial acceptance before
external production use.

**Domain note:** The currently deployed Railway public preview is an
informational surface. No custom `genesis` or `knowledge` DNS domain is
activated by this document. The private Cloud Gateway is not a public API.
