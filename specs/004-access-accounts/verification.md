# Verification: 004-access-accounts (#25, #26, #46)

Date: 2026-11-19. Worktree `C:/Users/sandy/Desktop/dev/Case-Study-Tech-issue4`, branch `feature/4-access-accounts`, HEAD d3991e2 (local, unpushed) plus QA's uncommitted test files. Windows, Node 24.11.1. Install used npm 11.19.1.

## Automated checks

| Check | Command (from) | Result |
| --- | --- | --- |
| Clean install | `npx -y npm@11.19.1 ci` (apps/student) | PASS. `npm audit` reported 22 moderate, 0 high or critical (the implementer reported 20). Two packages had install scripts skipped by `allowScripts`: `@parcel/watcher`, `unrs-resolver`. |
| Lint | `npm run lint` | PASS |
| Typecheck | `npm run typecheck` | PASS |
| Jest | `npx jest --runInBand --coverage` | PASS. 74/74 tests in 6 suites: the 46 existing plus 28 added by QA. Line coverage 87.1% overall: `transport.ts` 100%, `session.ts` 97.4%, `GoogleButton.tsx` 100%, `account.tsx` 96.4%. `GoogleButton.web.tsx` is 21% in Jest. Its configured path is covered by the browser harness instead. |
| Web export | `npm run export:web` | PASS (fresh `dist/web`) |
| Android export | `npm run export:android` | PASS (Hermes bundle, 2.5 MB) |
| Accounts service | `uv run --frozen --python 3.12 python -m pytest -q` (services/accounts) | PASS. 30 passed and 5 skipped, because the emulator tests need Firestore. |
| Accounts service with the Firestore emulator | `firebase emulators:exec --only firestore --project demo-casestudy-tech "uv run --directory services/accounts --frozen --python 3.12 python -m pytest -q"` (repo root) | PASS. 35/35 with 0 skipped. |
| Firestore rules | `npm test` (infra), against the local emulator on 127.0.0.1:8085 | PASS, 4/4 |
| Browser harness | `python specs/004-access-accounts/browser-verification.py` with `QA_STUB_ORIGIN=http://localhost:8092` | PASS, 6/6. Playwright 1.58.0 with bundled Chromium and a fresh profile. |

The browser harness has two layers:
- **Signed out (production export, no client ID):** `apps/student/dist/web` built with `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` unset. The harness asserts there are no JavaScript errors and no external requests.
- **Signed in (stubbed):** real Google sign-in can't run because the owner's OAuth clients aren't registered yet. These tests run against `npx expo start --web --port 8092` with placeholder public values (`EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=qa-stub-web-client-id`, `EXPO_PUBLIC_API_URL=http://127.0.0.1:8899`). Those values were set as process environment variables, and no .env file was written. The stand-ins are:
  - a local fake accounts API, which records request paths only and never tokens;
  - a stand-in for the Google Identity Services script, served through Playwright `page.route`, which returns a fake credential.

  No production code was changed. These tests prove the real web guards, session, transport, Account screen and deletion flow. They do **not** prove Google sign-in.

`expo export --dev` was tried first and failed at runtime with "Requiring unknown module 834", so the stubbed layer uses the dev server. This affects only a development export, not the shipped production export.

## Acceptance criteria

| AC | Test(s) or screenshot that prove it | Command | Result | Evidence |
| --- | --- | --- | --- | --- |
| #25: real Google sign-in reaches the protected Library on web and Android (iOS moved to #103) | None with real Google. Supporting evidence: Jest `navigation.test.tsx` covers sign-in from Welcome to Library with the native module mocked. Browser `StubbedSignIn.test_signed_in_library_and_account` covers the web GIS callback, `/v1/auth/google`, `/v1/me` with a bearer token, and Library, all against stand-ins. | `npm test`; browser harness | **PENDING-MANUAL** | The owner must register the web and Android OAuth clients. Then sign in for real on web and on an Android device or emulator, and capture Library on each. Stubbed capture: [web-library-signed-in-stub.png](screenshots/web-library-signed-in-stub.png). |
| #25: sign-out makes protected screens unreachable; unauthenticated deep links redirect to Sign-in | Jest `access.test.tsx`: "sends a deep link to %s to Sign in" for all 6 protected routes, including `/history` and `/account`; "signs out, clears the saved sign-in, and closes every protected route"; "opens Sign in when the saved sign-in is no longer valid". QA added `access-edges.test.tsx`, which covers revocation during a token refresh, a successful refresh that keeps the screen, and a session ending outside Account. Browser tests: `test_signed_out_deep_links_redirect_to_sign_in` (6 routes, production export) and `test_sign_out_closes_protected_routes` (stub; browser Back after sign-out stays on Sign in, and GIS auto-select is disabled). | `npm test`; browser harness | **PASS** | [web-deep-link-session-redirects-to-sign-in.png](screenshots/web-deep-link-session-redirects-to-sign-in.png): `/library/session` lands on `/sign-in` (URL asserted). [web-welcome-signed-out.png](screenshots/web-welcome-signed-out.png): Welcome stays public. |
| #25: no other sign-in method appears; tokens are never logged | Jest `access.test.tsx`: "offers Google as the only way to sign in" and "never writes credentials or tokens to the console". QA added `transport.test.ts`, which covers HTTPS-only API addresses, rejection of embedded credentials, query strings and fragments, `credentials: 'omit'`, `no-store`, a bearer token only when one is given, generic error messages that leak neither the response nor the token, and memory-only web token storage. Browser `test_sign_in_without_client_id_offers_no_other_method`: 0 buttons, 0 text boxes, no password text, and no GIS script load. Other tests: `public-config.test.ts`, plus `test_invalid_request_never_echoes_credentials` and `test_rest_errors_do_not_leak_provider_payloads` in the accounts service. | `npm test`; browser harness; pytest | **PASS** for the automated scope. The Google-only check on a real GIS button is PENDING-MANUAL. | [web-sign-in-no-client-id.png](screenshots/web-sign-in-no-client-id.png) shows "Google sign-in is not available yet. Please try again later." and no other method. |
| #46: after a deletion request the student is signed out, and deleted scores can't be retrieved | Jest `access.test.tsx`: confirmation and cancel, "requests deletion after confirmation, then signs the student out", and "keeps the student signed in … when deletion fails". QA added these to `access-edges.test.tsx`: one request while pending with both buttons disabled, `accepted:false` treated as a failure, retry after a failure, an expired session during deletion signs out without claiming deletion, and the notice clears after signing in again. Browser `test_deletion_confirmation_then_signed_out_with_notice`. Server: `test_deletion_requires_confirmation_and_denies_access_immediately`, `test_pending_deletion_blocks_refresh_and_new_exchange`, `test_deletion_worker_is_idempotent_and_removes_only_owner_scores`, and emulator `test_erasing_scores_does_not_touch_another_student`. Rules: "queued deletion denies direct reads even with an old valid token". | `npm test`; browser harness; emulator pytest; rules tests | **PASS** (client and server automated scope) | [web-account-signed-in-stub.png](screenshots/web-account-signed-in-stub.png), [web-delete-confirmation-stub.png](screenshots/web-delete-confirmation-stub.png), [web-sign-in-after-deletion-stub.png](screenshots/web-sign-in-after-deletion-stub.png). An end-to-end deletion against the deployed service with a real account is part of the manual Google proof. |
| #26: criteria re-run after the merge | `services/accounts` suite: token verification, owner derived from the verified token, no identity override, fail-closed verification, per-student scoping, and cross-owner denial with real Firestore. Firestore rules: own scores only, Google provider only, no client writes. | pytest with and without the emulator; infra `npm test` | **PASS** | 35/35 with the emulator (30 passed and 5 skipped without it). Rules 4/4. |

Requirements cross-check:
- R1: the scaffold tests in `navigation.test.tsx` and `public-config.test.ts` still pass.
- R2 and R4: covered above.
- R3: native and web GoogleButton paths are tested. Real native and GIS behaviour is pending manual proof.
- R6: covered above.
- R7: Jest only, and `npm ci` passes with npm 11.19.1. Hosted CI is not re-run locally.

## Screenshots

All are under `specs/004-access-accounts/screenshots/`. QA opened each one.

| File | Build | Shows |
| --- | --- | --- |
| `web-welcome-signed-out.png` | production export | Welcome, the preview notice, and "Sign in to explore". |
| `web-sign-in-no-client-id.png` | production export | Sign in with the unconfigured-Google message and no button. The message renders in small unstyled text; see the UX notes. |
| `web-deep-link-session-redirects-to-sign-in.png` | production export | A deep link to `/library/session` showing Sign in. |
| `web-library-signed-in-stub.png` | dev server + stand-ins | Library, with the Library tab selected. |
| `web-account-signed-in-stub.png` | dev server + stand-ins | Account with Sign out and Delete account. |
| `web-delete-confirmation-stub.png` | dev server + stand-ins | The "Delete your account?" modal with Confirm deletion and Cancel. The harness waits for the fade-in before capturing. |
| `web-sign-in-after-deletion-stub.png` | dev server + stand-ins | Sign in with the deletion notice. The Google button is the QA stand-in. |

Not captured: Android screens. No emulator run was in scope, and real sign-in can't run there yet.

## Defects and observations

- No functional defects were found. All 28 new Jest tests and all 6 browser tests passed against unchanged production code.
- UX: the deletion success notice ("Deletion requested…") uses `AlertText`, the danger-red error style, on Sign in. A confirmation is styled as an error. Location: `apps/student/src/app/sign-in.tsx:17`.
- UX: the web "Google sign-in is not available yet" message is a bare `<Text>` with no page style, so it renders small and black. Use `AlertText` or `BodyText` instead. Location: `apps/student/src/auth/GoogleButton.web.tsx:65-70`.
- UX: when deletion is confirmed after the session has expired and the refresh fails, the student lands on Sign in with no explanation. This is safe, because deletion isn't claimed and no request is sent. Reproduce with the `access-edges.test.tsx` test "signs out without claiming deletion when the session cannot be refreshed for the request".
- Harness note: the deletion modal fades in. Playwright's `to_be_visible` passes while opacity is 0, so the first capture was blank. The harness now waits for full opacity. This is not an app defect: after 2 s the probe saw opacity 1.

## Reproduce

1. From apps/student: `npx -y npm@11.19.1 ci`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run export:web`, `npm run export:android`.
2. From services/accounts: `uv run --frozen --python 3.12 python -m pytest -q`. For the emulator tests, wrap the command in `firebase emulators:exec --only firestore --project demo-casestudy-tech` from the repo root.
3. Start the stubbed dev server described in the `browser-verification.py` docstring. Then, from the repo root, run `QA_STUB_ORIGIN=http://localhost:8092 python specs/004-access-accounts/browser-verification.py`. Without `QA_STUB_ORIGIN` the stubbed tests are skipped and only the signed-out tests run.
