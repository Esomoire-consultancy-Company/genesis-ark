# Genesis ARK Public Site — Preview R0.1

Separate public-information surface. **No gateway access, database access,
credentials, user accounts, analytics, API proxy, cookies or submission forms.**

## Pages

- `/` — public overview
- `/architecture` — explanatory roles and boundaries
- `/knowledge` — knowledge registry principles and source blueprint
- `/evidence` — evidence maturity levels and accepted staging record
- `/status` — dated, manually published snapshot (NOT live status)
- `/healthz` — HTTP health only, no API access

The preview sends `X-Robots-Tag: noindex` and blocks search indexing via
`robots.txt`. Remove these restrictions only after content, brand and legal
review for a verified production hostname.

## Run locally

```bash
cd public-site
python3 -m unittest discover -s tests -v
PORT=8080 python3 server.py
```

## Railway staging

Create a **new independent service** from the existing `genesis-ark` repository.
Set root directory to `/public-site`, start command `python server.py`,
health check `/healthz`, and port determined by Railway's `PORT` variable.
Do **not** attach PostgreSQL, Warden, SILK, API secrets or the existing gateway
container. Only the public site gets an `*.up.railway.app` domain.

## Custom DNS plan — pending verified domain ownership

Do not assume the project owns a particular name. Once the authorised domain
owner confirms a real domain and specific labels, propose:

- `genesis.<verified-owned-domain>` → public Genesis ARK pages
- `knowledge.<verified-owned-domain>` → public Knowledge Hub index
- No public `api.` subdomain for the deny-only private Gateway R0.1.

The two custom hostnames may point to the same public-information service
initially, with `knowledge` redirected to `/knowledge` in a later release.
Custom domains need Railway-provided DNS records and ownership/certificate
checks. Do not invent DNS targets.

## Promotion gates

Brand and content owner approval, DNS proof, privacy/legal review, published
versioned sources, uptime checks, content-review workflow, and independent
public-access verification. Never imply that staging status is live monitoring.
