# Local and GitHub Pages deployment

1. Validate `node arks/bmp/scripts/validate.mjs` from repository root (Node 20+; no packages).
2. Serve repository root over HTTP: `python3 -m http.server 5173`.
3. View `http://localhost:5173/arks/bmp/market/a-1204/`.
4. For GitHub Pages, publish the repository root or copy `arks/bmp/market/a-1204/` plus the sibling `docs/LISTING_TEMPLATE.md` to a static site. Test whether Markdown is returned as raw text; app falls back to checked-in `listing.json` if not.
5. Re-run validation after every fixture change. Do not promote to real listing until backend Warden admission, signed operator records, storage, River ingestion and approved commercial terms exist.

No image uploads, recording, leads database, payments, reservation infrastructure, DigitalMe principal issuance, title verification or provider execution is implemented here.

## R0.5 Property Experience checks
Run `node arks/bmp/scripts/validate-experience.mjs`. On local preview, click all five stage buttons, open each of six anchor dialogs using keyboard navigation, and confirm ESC/Close returns focus. The Door link displayed is intentionally `https://example.invalid`: **do not print, share with buyers, or treat it as live**. Sample prices remain solely for depiction.
