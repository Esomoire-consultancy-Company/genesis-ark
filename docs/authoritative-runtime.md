# Authoritative Warden and CloudBrowser Runtime

Status: **implementation slice v1 — repository and isolated Chromium adapters**

This slice replaces development-only persistence and execution seams with:

- PostgreSQL/Supabase repository adapters for Warden and CloudBrowser;
- transactional, per-Box and per-session evidence-chain writes;
- durable storage for denials against unknown Boxes;
- a non-persistent Playwright Chromium context per governed session;
- action idempotency and pre-execution authorization evidence;
- durable DigitalMe approval before consequential execution;
- non-root container definitions for both services.

## Migration order

Apply the SQL contracts in this order:

1. `db/actor-box/v1/001_actor_box_foundation.sql`
2. `db/cloudbrowser/v1/002_cloud_browser_foundation.sql`
3. `db/authoritative/v1/003_authoritative_runtime_hardening.sql`

The third migration enables RLS on all control-plane tables, revokes Data API access from `anon` and `authenticated`, creates security-invoker active-state views, and creates the `genesis_control_plane` NOLOGIN role with explicit table policies.

Create a dedicated database LOGIN outside the committed migration, then grant it the private role:

```sql
create role genesis_runtime login password '<secret-from-your-secret-manager>';
grant genesis_control_plane to genesis_runtime;
```

Do not place that password, a Supabase secret key, or the `postgres` credential in an application image or public client.

## Supabase connection mode

These services are persistent backends. Prefer, in order:

1. a direct database connection when IPv6 and network controls permit it;
2. Supavisor session mode for persistent IPv4 service connections;
3. Supavisor transaction mode only when required.

Both adapters default `prepare_threshold` to `None`, which disables client-side prepared statements and remains compatible with transaction pooling. Connection pool sizes must remain below the project and pooler limits.

Required Warden settings:

```text
WARDEN_REPOSITORY_BACKEND=postgres
WARDEN_DATABASE_URL=<protected postgres connection string>
WARDEN_API_TOKEN=<secret>
WARDEN_DATABASE_POOL_MIN_SIZE=1
WARDEN_DATABASE_POOL_MAX_SIZE=8
WARDEN_DATABASE_PREPARE_THRESHOLD=none
```

Required CloudBrowser settings:

```text
CLOUDBROWSER_REPOSITORY_BACKEND=postgres
CLOUDBROWSER_DATABASE_URL=<protected postgres connection string>
CLOUDBROWSER_EXECUTOR_MODE=PLAYWRIGHT
CLOUDBROWSER_API_TOKEN=<secret>
CLOUDBROWSER_WARDEN_API_TOKEN=<secret>
CLOUDBROWSER_WARDEN_BASE_URL=https://warden.internal
CLOUDBROWSER_DATABASE_PREPARE_THRESHOLD=none
```

## Transactional guarantees

Warden uses one database transaction for each material combination:

- decision plus RiverOS evidence;
- capability issuance plus evidence;
- revocation plus capability-state update plus evidence;
- emergency Box lock plus active-capability suspension plus evidence.

CloudBrowser uses one database transaction for:

- session plus initial usage meter plus evidence;
- action state plus evidence plus usage;
- DigitalMe approval grant plus action transition plus evidence plus usage;
- session pause, expiry or termination plus evidence and final usage.

PostgreSQL advisory transaction locks serialize evidence continuation per Box or browser session.

## Chromium isolation boundary

Each browser session receives a new non-persistent `BrowserContext` with:

- no shared cookies or local storage with another session;
- service workers blocked;
- no browser permissions granted by default;
- context-wide request interception and hostname allowlisting;
- downloads disabled unless the policy permits them;
- owner-only quarantine and session directories;
- no `--no-sandbox` launch flag;
- runtime shutdown on pause, expiry or termination.

Run the CloudBrowser container as the supplied `pwuser`, with an appropriate seccomp profile and network egress policy. The application allowlist is not a substitute for cluster/firewall egress controls or DNS-rebinding protection.

## Execution recovery boundary

Before a non-consequential browser action executes, CloudBrowser records an `ALLOW` action state and `BROWSER_ACTION_AUTHORIZED` evidence event. Before a consequential action executes, it records the DigitalMe approval and moves the action to `APPROVED`.

This prevents silent execution and duplicate execution on client retries. A process interruption may leave an action in `ALLOW` or `APPROVED`; a future recovery worker must reconcile those states before any retry. It must never blindly replay an externally consequential action.

## Deliberately not claimed

- No live Supabase project migration has been applied by this repository change.
- No production secret-vault credential provider is included; credential use fails closed without one.
- No malware-scanning provider is included for transferred files.
- No production orchestration, autoscaling or recovery worker is included.
- No unrestricted internet browsing is enabled.
