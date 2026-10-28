# Genesis Living Gateway R0.1 — Staging Acceptance Evidence

**Verification date:** 2026-10-28 (UTC)  
**Environment:** `genesis-ark-gateway-staging` / `staging`  
**Service:** `genesis-living-gateway-preview-r01`  
**Service ID:** `2e974f4f-99f4-4a9f-97f5-0b5d933bb6cc`  
**Pinned source:** `preview/genesis-living-gateway-staging-r01` @ `2403ecd5e40e3d9bd840757eb6e70e29bf95eced`  
**Container:** Nginx static only, port 8080; no application backend.  
**Deployment ID:** `d8bba329-2346-49e1-9e45-6d07b108f766` — Railway status SUCCESS.  
**Public preview:** https://genesis-living-gateway-preview-r01-staging.up.railway.app/

## Build provenance and pre-deploy verification

[GitHub Actions container acceptance run 40689126426](https://github.com/Esomoire-consultancy-Company/genesis-ark/actions/runs/40689126426): SUCCESS on commit `2403ecd5e40e3d9bd840757eb6e70e29bf95eced`.

Validated static sources, the 25 regression tests, JavaScript syntax, Nginx container build and HTTP contract, security headers, and absence of exposed documentation files. The image copies only `index.html`, `styles.css`, `portal.js`, `favicon.svg` and its Nginx configuration; `.dockerignore` excludes the wider repository context.

## Public-host evidence

Read-only browser navigation and Railway HTTP logs confirmed:

| Route | Observed status | Expected |
| --- | --- | --- |
| `/` | 200 | Public home |
| `/styles.css` | 200 | Public stylesheet |
| `/portal.js` | 200 | Public interactive script |
| `/favicon.svg` | 200 | Public icon |
| `/healthz` | 200, body `ok` | Health response |
| `/README.md` | 404 | Not published |
| `/control-plane/README.md` | 404 | Not published |

`favicon.ico` also returned 404 when a browser probed the conventional URL; `favicon.svg` is explicitly linked and succeeded. A 404 for unpublished files is intended, not a failed application route.

## Visual and semantic accessibility checks

Read-only browser inspection of the public URL observed:

- Desktop viewport 1440 × 900: fixed side navigation, readable hero and structured sections; no horizontal overflow.
- Mobile viewport 390 × 844: wrapped navigation, stacked buttons and three-column hero metrics; no horizontal overflow.
- Focusable skip-to-content link with visible focus treatment and `#main` destination.
- Readable button accessible names for all inspected role controls, architecture nodes, filters and method steps.
- Seven architecture selection buttons with `aria-pressed` states; this is a toggle-button group, not an ARIA tab interface.
- In-page navigation to Architecture, Capabilities and Evidence worked.

The original feature branch's [Chromium acceptance run 40664815896](https://github.com/Esomoire-consultancy-Company/genesis-ark/actions/runs/40664815896) also passed layouts and interactions at 320, 390, 768 and 1440 pixels. The static preview container was pinned to the tested repository content plus isolation configuration.

### What is *not* claimed

This public browser observation is **not** a formal WCAG 2.2 certification, a manual NVDA or VoiceOver session, or an audit of every component/state/contrast pairing. Assistive-technology acceptance remains a separate gate before production promotion.

It is also **not** a test of login, live DigitalMe/BNR membership issuance, Warden authority, Synnergyze execution, private Gateway routing, or RiverOS end-to-end evidence flows. None are connected to this static preview.

## Release and segregation

- New service created **only in Railway staging**. No shared database mount, private token, or secret was required.
- Public domain belongs to the new static preview service, target port 8080.
- The source is pinned to an immutable commit rather than tracking unreviewed pushes.
- Existing Cloud Gateway and PostgreSQL service configurations were not modified by this deployment.
- No action was taken to deploy production or to merge this preview branch.
- The existing PR #19 for the Gateway itself had already been merged independently before this staging work.

## Remaining gates

1. Human review of the live preview for copy, visual accuracy, and product architecture vocabulary.
2. Native assistive technology QA (VoiceOver and NVDA, ideally mobile and desktop).
3. Any revised production claim must be supported by its own Warden authority, RiverOS evidence, and deployment authorization.
