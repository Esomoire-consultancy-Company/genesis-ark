# Dubai QR / VSR Door R0.2 — threat model and acceptance gates

User-supplied proposed QR:
`https://bmp.market/estate/belgaum/A-1204?entry=vsr-door&buyer=Dubai&geo=dubai-pack&disclosure=qualified&state=FINISHED&anchor=FLOOR_01&river=river://a-1204/door/vsr%23entry`

**Status:** claimed external QR; neither archive contains QR images or source code. Host and QR payload have not been independently verified as a functioning service.

## Trust and role boundary
- `entry`: public navigation intent only.
- `buyer=Dubai`: marketing/location hint, not buyer identity.
- `geo=dubai-pack`: suggested UI localization, not legal jurisdiction or license.
- `disclosure=qualified`: **untrusted; never upgrades privileges**.
- `state=FINISHED`: aspirational visualization, never as-built proof.
- `anchor=FLOOR_01`: safe whitelisted focus hint.
- `river=river://...`: untrusted string; does not authenticate evidence or create an entry receipt.

## Public versus invited QR
**General QR:** HTTPS URL to a verified domain with public resource identifier, no buyer rights, no evidence claim. Resolve in browser; optionally open registered VSR universal/app link.

**Buyer-specific QR:** HTTPS URL to an entry-redemption page with opaque, server-issued, short-lived invitation code. Redeem against server policy and Warden; bind permitted asset/role/audience/session server-side, enforce revocation and replay/expiry limits, then establish authenticated session (prefer secure HttpOnly cookie over bearer token preserved in URL). Avoid PII and bearer credentials in printed QRs.

If origin is not operator verified or DNS/HTTPS inaccessible, do **not print** buyer handover sheets with that destination.

## Required acceptance tests
1. Tampering `disclosure=qualified` or `role=owner` does not change admitted permissions.
2. Forged `river` values never appear as verified receipts.
3. Invalid/mismatched estate, asset or anchor fails closed.
4. Expired/revoked invitation cannot be redeemed; repeat redemption adheres to policy.
5. Guest sees only public data, regardless of URL parameters.
6. FINISHED projection prominently distinguishes TODAY evidence and not-as-built state.
7. Live viewing action returns actual confirmed session ID or explicit pending status.
8. Verify action queries a real evidence backend, not a static hash label.
9. Make Offer requires explicit commercial terms, authenticated intent and a controlled workflow. A GitHub issue is an internal work item, **not** a legally binding offer.
10. QR points to HTTPS fallback from a registered, approved origin; app-specific `vsr://` is only an optional installed-app deep link.

## Implementation note
`market/a-1204/door-link.mjs` demonstrates *untrusted hint parsing only*, with local Node assertions in `scripts/validate-door-entry.mjs`. It does not issue invitation tokens, create QRs, authorize anyone, schedule sessions, or persist evidence.
