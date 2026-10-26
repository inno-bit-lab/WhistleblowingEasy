# Separate frontend runtime (phase 1 ADR)

Use Node 24 built-in HTTP and filesystem modules: no framework, npm dependency or backend source mount. Start `node /frontend/server.mjs` with `CLIENT_ROOT=/client/build`, `BACKEND_URL=http://backend:8080`, `PORT=8080` (defaults shown).

The backend remains authoritative for tenant resolution, language and every security header. Requests first reach it with their original Host. Its static handler emits `X-WBE-Frontend: 1` and a small JSON representation containing filename, language, direction and nonce. This internal representation is consumed only here and never returned to the browser. The frontend opens the named file inside the real build directory; only public asset extensions are allowed, dot paths and symlink escapes are rejected. The index is rendered with the backend nonce/language/direction. Asset and document responses currently use `no-store`, deliberately avoiding stale builds during source-mounted development.

API targets, including original query encoding and DPoP headers, are forwarded unchanged. Bodies and unmarked responses stream with backpressure; response status, cookies and security headers are preserved. Hop-by-hop headers and untrusted forwarded/client-IP overrides are removed. This phase therefore does not propagate visitor IP through the frontend: backend IP-based policies observe the frontend address. Trusted external proxy identity propagation requires a separate explicit trust configuration before production, not a client-provided forwarded header.

Channel document aliases use the existing slug grammar and technical-prefix exclusions, with viewer, tenant and readiness routes additionally excluded. Short slugs redirect to `/slug/report`; `/slug/report`, login and admin documents are internally requested as `/` so the backend supplies the entrypoint CSP. Tenant prefixes and query bytes survive rewriting. `/healthz` checks local index availability and backend health and returns only OK or service unavailable.

Run `node --test tests/phase1/frontend.test.mjs`. Tests use a mock backend and synthetic temporary files; application end-to-end tests remain required for the complete phase gate. This runtime is for the isolated development stack and does not configure production TLS or trusted reverse proxies.

## Opt-in Chromium end-to-end checks

`tests/phase1/frontend-browser.test.mjs` uses an explicitly supplied Puppeteer Core module and Chromium binary (neither becomes an application dependency). Set `WBE_E2E_URL=http://127.0.0.1:18090`, `PUPPETEER_MODULE=/absolute/path/to/puppeteer-core.js`, and `CHROMIUM_PATH=/absolute/path/to/chromium` then run `node --test tests/phase1/frontend-browser.test.mjs`. The test refuses other origins. The read-only smoke expects English and Italian enabled and verifies Angular boot, CSP violations, script assets, crypto worker and viewer policies.

For a fresh isolated lab, add `WBE_E2E_SETUP=1`: setup runs first, creates synthetic administrator/recipient accounts, logs in from a new browser context, and enables Italian through the admin UI. Credentials are generated locally under `.local/secrets/browser-fixture.json` with mode 0600 and never printed. An already-initialized lab must have the corresponding fixture credentials; the test does not reset it.

Add `WBE_E2E_REPORT=1` to submit a synthetic report, reopen it using its receipt in a new browser session, upload a synthetic text attachment, and verify the recipient's downloaded plaintext bytes. Each run creates a new synthetic report. Receipt and generated/downloaded fixtures remain under `.local` and must not be committed. Missing browser shared libraries can be extracted to a temporary directory and supplied through `LD_LIBRARY_PATH`; no host package installation is required by these tests.

After a restart or restore, set `WBE_E2E_SETUP=1 WBE_E2E_DOWNLOAD=1` with `WBE_E2E_REPORT` unset to verify existing fixture login, EN/IT shell and existing recipient attachment decryption without submitting another report. When the fixture is already initialized with Italian enabled, setup only logs in/out; normal access timestamps may still be updated by the application.
