# Genesis ARK — Living Gateway R0.1

An **explorable public interface** for Genesis ARK. This is a static, zero-backend **experience prototype**, not a deployed Genesis runtime.

## Open the prototype

Open `index.html` in a modern browser. It loads `styles.css` and `portal.js` from the same folder. No build step, secret, database, registry, or service token is needed. Some browser setups may require a local HTTP server instead:

```sh
python3 -m http.server 8080 --directory gateway
# Open http://localhost:8080
```

## Included experiences

- **Role-aware entrance:** Developer, Member, Operator and Auditor perspectives.
- **Interactive architecture atlas:** conceptual descriptions and explicit system boundaries.
- **Engineering index:** search and type filters grounded in actual repository paths.
- **LBM / OCM guide:** selectable steps for Learn–Build–Maintain and Observe–Correct–Maintain.
- **Evidence orientation:** Alpha verification claims linked to their published record.

The UI is mobile responsive, keyboard-operable, has a skip link and includes reduced-motion support. No backend calls, authentication, personal-data collection or state-changing operations are implemented.

## Status and honesty rules

- **R0.1 preview** applies only to this public interface, not the whole Genesis Stack.
- **E2** on the Alpha engineering card is a description of the existing published verification record, **not a live maturity assertion**. It is not proof of E3/E4 capability.
- The Smart Textile contracts are **DPP-ready**, not an assertion of final regulatory compliance.
- Genesis, Synnergyze, DigitalMe, BNR and VSR descriptions are explicitly **conceptual** where implementation is not evidenced in this repository.
- This interface **must not** expose secrets, private evidence, membership directories, role grants, or API tokens.
- Future live operations need authenticated DigitalMe principals, enforceable Warden policies, explicit Synnergyze MCP tool scoping, and RiverOS evidence, on a separately reviewed backend.

## Architecture for a future release

Public portal (this folder) → public documented capability catalogue → authenticated membership/workspace (separate service) → policy-gated operations and evidence (private endpoints).

A public renderer must never be granted direct privileged execution. Open source is not the same thing as an unrestricted operating environment.

## Publishing

No publishing workflow is enabled by this PR. Review the branch and its diff first. Deploy this static folder to a dedicated **staging preview** only after approval; do not assume GitHub Pages is configured or that a public domain exists. Keep the Gateway and PostgreSQL services private.

## Verification

```sh
node --check gateway/portal.js
python3 gateway/check.py
```

This static portal does not replace existing technical documentation, and the repository root README remains the engineer-facing index.
