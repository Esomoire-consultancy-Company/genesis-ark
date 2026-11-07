# Genesis ARK static Gateway — explicit preview deployment target R0.1

**Status: REVIEW CANDIDATE / NO RAILWAY CHANGE / NO PRODUCTION ADMISSION.**

## Root-cause evidence

The existing Railway service `zoological-recreation/genesis-ark` is offline, with three warnings and a failed build. Deployment `3fbcbf78-002f-4114-af73-9f2e10e664aa` used the repository's `control-plane/` directory as its Railpack root. Railpack 0.43.0 detected Python, but found no server startup target (`No start command detected`).

This is correct: `control-plane/` is the `ges-alpha` one-shot CLI for governed local Docker operations, not a continuously running HTTP server. **Never make it remotely callable simply to satisfy Railway's start-command check.**

The repository already has `gateway/` as a standalone, public static prototype with HTML/CSS/JS and static validation. A separate Railway **Genesis ARK staging** project already hosts gateway preview resources. The owner should first determine whether this new container is needed at all, or whether the existing approved preview can be reused.

## This PR's proposal — not a deployment action

A dedicated file `gateway/Dockerfile.preview` defines a nonroot (UID 10001) container with an allowlisted build context. It copies only:

- `index.html`
- `styles.css`
- `portal.js`
- `favicon.svg`
- `preview_server.py`

The server provides `GET/HEAD` for these five exact URL paths (the home page maps to index.html) and `GET/HEAD /healthz`. All other GETs return 404. It offers **no API routes, authentication, real user/tenant data, payments, Docker daemon, Warden, RiverOS, Registry or database access**. It emits restrictive CSP/frame/caching headers and does not record query strings or client IPs in application logs.

The image is intentionally inert by default. Starting it requires **`GENESIS_STATIC_PREVIEW_ENABLE=true`**, set only after a separate authorized staging decision. Build CI performs no publication or release.

## Local build and checks, without cloud deployment

```sh
python3 gateway/check.py
python3 -m unittest discover -s gateway -p 'test_*.py'
docker build -f gateway/Dockerfile.preview -t genesis-ark-static-preview:review gateway
```

The image's default startup must exit 78 with a HOLD message, not open a port. The CI workflow enforces this. For owner-approved, isolated staging later, the **proposed** configuration (not currently applied) would be: build context `gateway/`, Dockerfile `Dockerfile.preview`, `PORT=8080` (or provider-selected unprivileged port), preview opt-in flag, no privileged variables, no mounts or public customer domain, and a health probe at `/healthz`.

For a manually authorized disposable local review only:

```sh
docker run --rm --read-only --cap-drop=ALL --security-opt=no-new-privileges \
  --network bridge -e GENESIS_STATIC_PREVIEW_ENABLE=true \
  -p 127.0.0.1:8080:8080 genesis-ark-static-preview:review
```

This is a suggested local command, **not a claim it was run**. A provider deployment requires an independently accepted, non-production ingress/egress plan and security review. Pin the base image digest before any reproducible release.

## Decision gates

1. Genesis service owner must decide **CLI job / static public preview / existing staging preview reuse / disable proposed resource**. An offline resource is not an instruction to redeploy it.
2. Review the differences between the already-operational `genesis-ark-gateway-staging` services and this candidate. Avoid duplicate billing, identity confusion and accidental public authority.
3. Review container build and static tests; confirm OCI platform, egress rules, allowed origin, abuse/rate limits, accessibility, security headers and scan results.
4. Confirm account and data locality. No real DigitalMe, Warden, Registry, RiverOS or provider data is required for this static preview.
5. If approved, deploy to a **new isolated preview target**, not to the existing failing service, unless the owner explicitly approves its reassignment with rollback.
6. Record independently verified preview results; still do not claim Genesis production runtime or ARK platform acceptance.
7. Keep VSR issue [#221](https://github.com/Esomoire-consultancy-Company/virtual-silk-road-platform/issues/221) separately blocked for real DigitalMe Recovery/Warden authorization. Nothing in this static preview touches those RPCs.

**Release decision: BUILD/TEST REVIEW ONLY. NO CLOUD DEPLOYMENT, DNS, CREDENTIAL, CUSTOMER OR BILLING CHANGE.**


## Dual-track acceptance decision — preserve both

The user has selected **both** controlled paths. A machine-readable, evidence-labelled agreement is recorded in `gateway/staging-dual-track.r01.json` and guarded by `gateway/test_staging_dual_track.py`.

**Track A / reuse:** Keep the existing `genesis-ark-gateway-staging` environment unchanged, with four currently online Railway services: `genesis-living-gateway-preview-r01`, `genesis-public-site-preview`, private `genesis-cloud-gateway-r01`, and private Postgres. A read-only external browser checked the two published preview landing pages on **7 November 2026** and observed HTTP 200, with no login. The observed public URLs were:

- `https://genesis-living-gateway-preview-r01-staging.up.railway.app/` — Living Gateway, title `Genesis ARK — The Living Gateway`.
- `https://genesis-public-site-preview-staging.up.railway.app/` — public site, title `Overview — Genesis ARK`.

This confirms reachability of the public landing pages only. It does not grant or verify private gateway, database, VSR identity or Warden permissions; HTTP header and accessibility end-to-end acceptance remains separate from this observation.

**Track B / independent static container:** Retain this PR's standalone, non-root, default-off image as an independently testable release candidate. CI building it does not mean a second Railway service exists. Before creating a provider target, the accountable operator must choose an isolated review environment, sign off its incremental billing cap, ingress restrictions and shutdown procedure, and confirm that existing staging assets cannot fulfil the same test requirement. No deployment, external domain, environment variable or paid resource was created as part of this decision.

**Reconciliation:** The public previews and independent image may coexist as **one operating reference + one separately versioned candidate**. They are not interchangeable evidence of production maturity. Both remain excluded from privileged control-plane execution; neither adds customer/merchant access. Keep the old `zoological-recreation` failed CLI deployment untouched until its actual owner approves its disposition.

**Decision:** BOTH TRACKS SELECTED FOR ENGINEERING REVIEW. TRACK A ONLINE AND PUBLIC LANDING PAGES VERIFIED. TRACK B CODE AND CONTAINER CI QUALIFIED ONLY. REAL SERVICE CREATION / RELEASE HOLD.
