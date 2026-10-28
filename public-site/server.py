"""Genesis ARK public-information preview, entirely separate from the private gateway.

Fixed, editorially reviewed pages only. No authentication, cookies, reverse proxy,
service discovery, DB driver, dynamic metadata or internal API access.
"""
from __future__ import annotations

import json
import os
from threading import BoundedSemaphore
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

GITHUB = "https://github.com/Esomoire-consultancy-Company/genesis-ark"
NAV = [
    ("/", "Overview"),
    ("/infrastructure", "Infrastructure"),
    ("/architecture", "Architecture"),
    ("/knowledge", "Knowledge Hub"),
    ("/evidence", "Evidence"),
    ("/status", "Status"),
]
PAGES = {
    "/": {
        "label": "PUBLIC PREVIEW · R0.1",
        "title": "Network control for the physical and digital world.",
        "lead": "Genesis provides control and provisioning for a registered network of physical and digital nodes. VSR is the network operating environment, and Quantum Room is the governed workspace. Together with lawful operators and real assets, they support digital–physical infrastructure. This is not physical-site certification.",
        "content": """<div class="feature-grid">
          <article class="feature"><div class="feature-index">01 / NETWORK</div><h2>Genesis control foundation</h2><p>Register nodes, provision machine and server connections, and maintain network lifecycle and state without assuming ownership of physical assets.</p><a class="text-link" href="/infrastructure">Explore infrastructure →</a></article>
          <article class="feature"><div class="feature-index">02 / LEARN</div><h2>Find source-backed knowledge</h2><p>Public documentation is traceable to repository revisions. Private records remain with their authorised custodians.</p><a class="text-link" href="/knowledge">Visit Knowledge Hub →</a></article>
          <article class="feature"><div class="feature-index">03 / VERIFY</div><h2>Separate claims from proof</h2><p>Implementation, test, deployment and independent evidence are different milestones—and must be labelled as such.</p><a class="text-link" href="/evidence">Inspect evidence model →</a></article>
        </div>
        <section class="statement"><div><span class="overline">FOUNDING PRINCIPLE</span><h2>Genesis provisions. VSR operates the network experience. Quantum Room hosts the work.</h2></div><p>Discoverability does not imply permission. A member or system must pass the relevant identity and Warden gates before touching protected resources.</p></section>"""
    },
    "/infrastructure": {
        "label": "DIGITAL–PHYSICAL ESTATE · CONTROL AND OPERATIONS",
        "title": "A governed network spanning physical and digital environments.",
        "lead": "Genesis is the network control foundation implemented on authorised machines and servers. VSR is the network operating environment; Quantum Room is a bounded physical, digital or hybrid workspace. Together with registered actors, assets and locations, they form the wider infrastructure.",
        "content": """<div class="architecture">
          <div class="arch-root"><span>GENESIS · NETWORK CONTROLLER</span><strong>Node registry, provisioning, network state and device/server lifecycle</strong><p>Infrastructure control plane, not a public application or a Quantum Room.</p></div>
          <div class="arch-row">
            <article><span>VSR OS / BROWSER · NETWORK OPERATING ENVIRONMENT</span><strong>Applications, navigation and Doors</strong><p>The user-facing access and service environment; not the underlying machine OS kernel.</p></article>
            <article><span>QUANTUM ROOM · GOVERNED WORKSPACE</span><strong>Physical, digital or hybrid runtime</strong><p>A location- and permission-bound context for participants, devices, workflows and approvals inside an ARK.</p></article>
          </div>
          <div class="arch-foot">Warden governs authority, Synnergyze coordinates operations, Sentinel observes and RiverOS preserves event evidence.</div>
        </div>
        <div class="feature-grid">
          <article class="feature"><div class="feature-index">01 / PHYSICAL</div><h2>Places and machines</h2><p>Factories, warehouses, utilities, vehicles and devices remain with their lawful owners and custodians.</p></article>
          <article class="feature"><div class="feature-index">02 / DIGITAL</div><h2>Network and application</h2><p>Genesis provisions nodes; VSR exposes authorised Doors; Quantum Rooms host bounded workflows.</p></article>
          <article class="feature"><div class="feature-index">03 / GOVERNANCE</div><h2>Safety, consent and evidence</h2><p>Registering an asset does not grant permission to operate it or transfer its legal control.</p></article>
        </div>
        <section class="statement"><div><span class="overline">PHYSICAL AUTHORITY</span><h2>Registration is not operational permission.</h2></div><p>Real equipment requires independent safety, legal, custodial and task-level authority checks before execution.</p></section>
        <div class="link-panel"><div><span class="overline">NETWORK AND INTERVENTION</span><h2>ARK participation ≠ ARC intervention</h2><p>An ARK is a governed private-network workspace without takeover. An ARC requires a separate, evidenced legal and contractual mandate.</p></div><a class="outline-link" href="/architecture">See responsibilities →</a></div>
        <section class="note"><strong>Current implementation boundary</strong><p>All physical node passport and Quantum Room examples remain synthetic. No factory, vehicle, machine or physical node is certified operational by this preview.</p></section>"""
    },
    "/architecture": {
        "label": "PLATFORM · BOUNDARIES",
        "title": "One platform. Distinct responsibilities.",
        "lead": "Genesis governs the network control foundation; VSR provides the network operating environment; Quantum Rooms provide bounded operational workspaces. Warden, Synnergyze, BNR, DigitalMe and RiverOS keep distinct contracts.",
        "content": """<div class="architecture">
          <div class="arch-root"><span>GENESIS · NETWORK CONTROL FOUNDATION</span><strong>Node identity, provisioning, service state and device/server lifecycle</strong></div>
          <div class="arch-row">
            <article><span>VSR OS / BROWSER · NETWORK OPERATING ENVIRONMENT</span><strong>Doors, navigation and applications</strong><p>Authorised access surface, separate from Genesis and the host machine kernel.</p></article>
            <article><span>QUANTUM ROOM · GOVERNED RUNTIME</span><strong>Physical, digital or hybrid workspaces</strong><p>People, devices, sessions and workflows inside an authorised ARK or operating location.</p></article>
          </div>
          <div class="arch-row">
            <article><span>SYNNERGYZE / WARDEN</span><strong>Operations and authority</strong><p>Synnergyze routes work; Warden enforces permission, consent, safety and revocation.</p></article>
            <article><span>BNR / DIGITALME / RIVEROS</span><strong>Registry, identity and evidence</strong><p>Representation, accountable actor identity and event preservation remain separate responsibilities.</p></article>
          </div><div class="arch-foot">Node registration is not physical ownership, possession or a machine command.</div>
        </div>
        <section class="note"><strong>Current implementation boundary</strong><p>The cloud gateway R0.1 is a separate deny-only HTTP service in staging. It is not a public execution endpoint and does not replace Warden or the canonical RiverOS ledger.</p></section>"""
    },
    "/knowledge": {
        "label": "KNOWLEDGE HUB · PUBLIC INDEX",
        "title": "Know what exists—and what is verified.",
        "lead": "The Knowledge Hub is a proposed federated index for Genesis nodes, VSR network operating environments, Quantum Rooms and physical/digital asset passports. It references source-controlled knowledge without assuming ownership of private documents, assets, facilities or institutional records.",
        "content": """<div class="steps">
            <div><span>01</span><div><h2>Register</h2><p>Assign a stable passport to each public knowledge item: origin, revision, owner, classification and review date.</p></div></div>
            <div><span>02</span><div><h2>Validate</h2><p>Check sources, approval status and whether the claim refers to a proposal, an implementation, a passing test or an operational deployment.</p></div></div>
            <div><span>03</span><div><h2>Publish responsibly</h2><p>Expose only approved metadata. Protected content, member workspaces and credentials require separate authenticated channels.</p></div></div>
            <div><span>04</span><div><h2>Maintain continuity</h2><p>Recheck evidence, mark superseded records, and preserve revision history without silently replacing the source of truth.</p></div></div>
        </div><div class="link-panel"><div><span class="overline">SOURCE DOCUMENT</span><h2>Knowledge Hub Proxy blueprint</h2><p>Reference architecture in the genesis-ark repository; not a claim of live federation.</p></div><a class="outline-link" href="https://github.com/Esomoire-consultancy-Company/genesis-ark/blob/9060824c202f8a020d2565db5db0b256602617b4/docs/knowledge-hub-proxy.md" rel="noopener noreferrer">Read source document ↗</a></div>"""
    },
    "/evidence": {
        "label": "TRACEABILITY · RECEIPTS",
        "title": "Evidence is a sequence, not a badge.",
        "lead": "Every meaningful claim should be associated with a source and a maturity level. A successful staging test is not an independent attestation or a production authorization.",
        "content": """<div class="evidence-table" role="table" aria-label="Maturity meanings">
        <div class="table-row header" role="row"><span role="columnheader">Level</span><span role="columnheader">What it establishes</span></div>
        <div class="table-row" role="row"><span role="cell">Proposed</span><span role="cell">A documented idea awaiting implementation or review</span></div>
        <div class="table-row" role="row"><span role="cell">Implemented</span><span role="cell">Source code exists at a traceable revision</span></div>
        <div class="table-row" role="row"><span role="cell">Tested</span><span role="cell">Defined checks passed in a specified environment</span></div>
        <div class="table-row" role="row"><span role="cell">Deployed</span><span role="cell">A specific service revision was deployed</span></div>
        <div class="table-row" role="row"><span role="cell">Independently witnessed</span><span role="cell">A distinct authorised custodian validated evidence outside the source system</span></div></div>
        <div class="link-panel"><div><span class="overline">PUBLIC EVIDENCE · PENDING</span><h2>Cloud Gateway staging evidence</h2><p>A stable, approved public evidence record is not yet published. Any internal staging acceptance is distinct from a production release, Warden PERMIT, or independent RiverOS certification.</p></div></div>"""
    },
    "/status": {
        "label": "STATUS · PUBLISHED SNAPSHOT",
        "title": "Status with a timestamp.",
        "lead": "This page is a manually published evidence snapshot dated 28 October 2026. It is not live monitoring and must not be used for operational decision-making.",
        "content": """<div class="status-grid">
          <article><div class="status-tag">STAGING / REPORTED 28 OCT 2026</div><h2>Genesis Cloud Gateway R0.1</h2><p>Restricted staging acceptance recorded. Deny-only execution mode; no public API domain.</p></article>
          <article><div class="status-tag">STAGING / REPORTED 28 OCT 2026</div><h2>PostgreSQL evidence spool</h2><p>Storage and restricted-role migration passed the recorded acceptance checks. This is not the canonical RiverOS ledger.</p></article>
          <article><div class="status-tag neutral">NOT CERTIFIED</div><h2>Production / Federation</h2><p>No production promotion, independent RiverOS witnessing or Warden permit integration is asserted by this preview.</p></article>
        </div>
        <section class="note"><strong>For current operational state</strong><p>Authorised operators should consult the source deployment platform and private evidence registry. Historical snapshots may become stale.</p></section>"""
    },
}


def render_page(path: str) -> str:
    page = PAGES[path]
    nav = "".join(
        '<a href="' + href + '"' + (' aria-current="page"' if href == path else '') + '>' + escape(text) + '</a>'
        for href, text in NAV
    )
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<meta name="description" content="Public preview of Genesis network control, VSR environments, Quantum Rooms and evidence.">
<title>%%TITLE%% — Genesis ARK</title>
<link rel="stylesheet" href="/assets/site.css"></head>
<body><a class="skip" href="#main">Skip to content</a>
<header class="site-header"><div class="header-inner">
<a class="wordmark" href="/" aria-label="Genesis ARK home"><span class="brand-symbol">G<span class="dot">.</span></span><span>GENESIS <b>ARK</b></span></a>
<nav aria-label="Primary navigation">%%NAV%%</nav>
<span class="preview-label">PUBLIC PREVIEW</span></div></header>
<main id="main"><section class="hero"><div class="hero-inner">
<div class="eyebrow"><span class="eyebrow-rule"></span>%%LABEL%%</div>
<h1>%%HEADING%%</h1><p class="hero-lead">%%LEAD%%</p>
<div class="hero-actions"><a class="primary-link" href="/knowledge">Explore the Knowledge Hub <span aria-hidden="true">↗</span></a><a class="secondary-link" href="%%GITHUB%%" rel="noopener noreferrer">View source on GitHub <span aria-hidden="true">↗</span></a></div>
</div></section><section class="content-shell">%%CONTENT%%</section></main>
<footer><div class="footer-inner"><div><strong>GENESIS ARK</strong><p>Public information only. Authority, records and execution remain privately governed.</p></div><div><span>Navigation</span><a href="/infrastructure">Infrastructure</a><a href="/architecture">Architecture</a><a href="/evidence">Evidence</a><a href="/status">Status</a></div><div><span>Source</span><a href="%%GITHUB%%" rel="noopener noreferrer">GitHub repository ↗</a><small>Preview release R0.1 · No member enrollment · No public API</small></div></div>
<div class="footer-bottom">Reference information, not a representation of production availability or institutional authority.</div></footer></body></html>""".replace("%%TITLE%%", escape("Overview" if path == "/" else page["title"])) .replace("%%NAV%%", nav).replace("%%LABEL%%", escape(page["label"])).replace("%%HEADING%%", escape(page["title"])).replace("%%LEAD%%", escape(page["lead"])).replace("%%CONTENT%%", page["content"]).replace("%%GITHUB%%", GITHUB)


def route(path: str) -> tuple[int, str, bytes]:
    try:
        path = urlsplit(path).path
    except ValueError:
        return 400, "text/plain; charset=utf-8", b"Bad request"
    if path == "/healthz":
        return 200, "application/json; charset=utf-8", json.dumps({"status": "ok", "site": "genesis-ark-public-preview", "api_enabled": False}).encode("utf-8")
    if path == "/robots.txt":
        return 200, "text/plain; charset=utf-8", b"User-agent: *\nDisallow: /\n"
    if path == "/assets/site.css":
        with open(os.path.join(os.path.dirname(__file__), "assets", "site.css"), "rb") as f:
            return 200, "text/css; charset=utf-8", f.read()
    if path in PAGES:
        return 200, "text/html; charset=utf-8", render_page(path).encode("utf-8")
    return 404, "text/plain; charset=utf-8", b"Page not found"


class Handler(BaseHTTPRequestHandler):
    # Do not let a stalled connection hold a worker indefinitely.
    timeout = 10
    server_version = "GenesisARKPublic/0.1"
    sys_version = ""

    def do_GET(self):
        self.respond(send_body=True)

    def do_HEAD(self):
        self.respond(send_body=False)

    def respond(self, *, send_body: bool):
        status, mime, data = route(self.path)
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Robots-Tag", "noindex, nofollow, noarchive")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'self'; img-src 'self'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'; connect-src 'none'")
        self.end_headers()
        if send_body:
            self.wfile.write(data)


class BoundedHTTPServer(ThreadingHTTPServer):
    """Limit concurrent HTTP connection handlers, including idle clients."""

    daemon_threads = True
    request_queue_size = 32
    max_connections = 32

    def __init__(self, server_address, RequestHandlerClass):
        self._slots = BoundedSemaphore(self.max_connections)
        super().__init__(server_address, RequestHandlerClass)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            # Drop excess clients without allocating more request threads.
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._slots.release()
            self.shutdown_request(request)
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    BoundedHTTPServer(("0.0.0.0", port), Handler).serve_forever()
