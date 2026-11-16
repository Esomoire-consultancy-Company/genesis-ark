# Genesis Lobby — Sprint-0 private Postman mock CI

**Status: REVIEW ONLY / NOT ACTIVATED.** This automation is engineering verification of a **synthetic mock**, not production Warden authority, Genesis Lobby identity, live RiverOS evidence, SILK payment, or commercial billing.

## Repository placement
Owned by **Genesis / ARK**, which maintains cross-system engineering and verification. The Believers Commons/Creators Common membership and data registers are not copied here. Nothing in this directory stores personal data, private API keys, raw request payloads, or individual usage records.

## Pre-activation checks
1. In the existing Postman 'believers lobby' collection, create a folder **Sprint-0 Regression** with exactly R1-R7 in their required order. Confirm all seven URLs correspond to endpoints implemented by the *deployed cloud mock*, not just the cart handler.
2. Confirm the collection-level pre-request script reads ${mock_session_id} from \`pm.environment.get("mock_session_id")\` or \`pm.variables.get("mock_session_id")\`, and adds exactly one \`x-mock-session\` header; ensure requests use the mock-only API key for \`x-api-key\`.
3. In GitHub repository Settings > Secrets and variables > Actions, set:
   - Secret: \`POSTMAN_API_KEY\` (Postman API key capable of reading the collection and authenticating the private mock; never commit it).
   - Variable: \`POSTMAN_COLLECTION_ID\` (the approved cloud collection UUID).
   - Variable: \`POSTMAN_SPRINT0_FOLDER_UID\` (the folder UID, not the display name).
   - Variable: \`POSTMAN_MOCK_URL\` (approved private HTTPS Postman mock, e.g. \`https://<slug>.mock.<team>.postman.dev\`).
   - **Enable switch: \`GENESIS_LOBBY_CI_ENABLED\` must stay unset or \`false\` until all above checks pass.** Then deliberately set to \`true\`.
4. Merge the reviewed PR only when ready. Do not enable the switch on a feature branch. Authenticated jobs run only on the repository default branch (\`main\`) and only when explicitly enabled.
5. Run the workflow manually on \`main\`; inspect the HTTP responses, JUnit report and actual assertions, and retain historical Sprint-0 401 evidence as a separate diagnostic baseline.
6. After a successful authenticated run, schedule is every 6 hours at minute 17 UTC. The workflow can also run when the CI script/workflow is pushed to \`main\`, or when manually dispatched. PRs run only a shell syntax check without secrets.

## Fail-closed and confidentiality boundaries
- Synthetic mock endpoint only; the runner rejects non-Postman mock URLs.
- One ephemeral CI environment with a fresh session identifier per run; temp file removed after execution. For the mock-only run, \`auth_token\` aliases the mock key only to satisfy older request configuration. **Never use this technique for a live Warden environment.**
- Any missing secret, collection ID, folder UID, mock URL or Postman CLI stops the run.
- JUnit evidence only; no environment exports or raw request and response bodies in GitHub artifacts. Protect runner logs appropriately.
- This is a *consumer of a pre-existing mock*, not a process that deploys, edits, or automatically grants Postman service permissions.
- Historical aggregate assertions were stated as 38 and itemized as 6+6+5+5+5+7+7 = **41**. Use actual CLI test output for the acceptance count; do not assume either.
- An HTTP 401 response proves an auth gate was encountered, not successful Warden proposal processing.
- Do not enable external production provider integrations or recurring cloud traffic without the approved test scope.

## Locally validate
\`\`\`bash
bash -n scripts/run-genesis-lobby.sh
\`\`\`

The regression action intentionally does not run on a pull-request branch with secrets. It becomes eligible only after authorised merge, provisioned repository variables and explicit enablement.
