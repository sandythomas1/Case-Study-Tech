# Verification: 004-access-accounts (#25, #26, #46)

Re-verified 2026-11-19 after fix rounds 1 and 2 (`review.md` S1–S10, U1–U17). Worktree `C:/Users/sandy/Desktop/dev/Case-Study-Tech-issue4`, branch `feature/4-access-accounts`, HEAD 401a1c9 (local, unpushed). Windows, Node 24.11.1. Install used npm 11.19.1.

## Automated checks

| Check | Command (from) | Result |
| --- | --- | --- |
| Clean install | `npx -y npm@11.19.1 ci` (apps/student) | PASS. 1159 packages. `npm audit`: 22 moderate, 0 high or critical. |
| Lint | `npm run lint` | PASS |
| Typecheck | `npm run typecheck` | PASS |
| Jest | `npx jest --runInBand --coverage` | PASS. 97/97 tests in 6 suites. All-files line coverage 89.34%. `GoogleButton.web.tsx`'s configured path is covered by the browser harness, not Jest. |
| Web export | `npm run export:web` | PASS (fresh `dist/web`) |
| Android export | `npm run export:android` | PASS |
| Accounts service | `uv run --frozen --python 3.12 python -m pytest -q` (services/accounts) | PASS. 40 passed, 5 skipped (the emulator tests need Firestore). |
| Accounts service with the Firestore emulator | same command with `FIRESTORE_EMULATOR_HOST=127.0.0.1:8085` | PASS, 45/45 after the emulator data was reset (see observations). |
| Firestore rules | `npm test` (infra), against the emulator on 127.0.0.1:8085 | PASS, 4/4 |
| Web route tests (S9) | `uv run --no-project --python 3.12 --with pytest --with playwright==1.58.0 python -m pytest -q -p no:cacheprovider infra/accounts/test_web_routes.py` (repo root) | PASS, 8/8 |
| Browser harness | `python specs/004-access-accounts/browser-verification.py` with `QA_STUB_ORIGIN=http://localhost:8092` | PASS, 9/9 (Playwright 1.58.0, bundled Chromium, fresh profile). |

The browser harness has two layers:
- **Signed out (production export, no client ID):** `apps/student/dist/web` built with `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` unset. It asserts no JavaScript errors and no external requests.
- **Signed in (stubbed):** real Google sign-in can't run because the owner's OAuth clients aren't registered yet. These tests run against `npx expo start --web --port 8092` with placeholder public values (`EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=qa-stub-web-client-id`, `EXPO_PUBLIC_API_URL=http://127.0.0.1:8899`), set as process environment variables. No .env file was written. The stand-ins are a local fake accounts API (records request paths only, never tokens; per-test modes for a 403 `account_deletion_pending` exchange and a rejected refresh) and a Google Identity Services stand-in served through Playwright `page.route`. No production code was changed. These tests prove the real web guards, session, transport, Account screen and deletion flow. They do **not** prove Google sign-in.

Harness changes in this round, copy only where it changed on purpose: the deletion notice, "Google sign-in isn't available right now…", "Delete my account", and the "Preview" notice title. Added three tests: keyboard focus on the deletion dialog, expiry during deletion, and sign-in refused for an account being deleted.

## Acceptance criteria

| AC | Test(s) or screenshot that prove it | Command | Result | Evidence |
| --- | --- | --- | --- | --- |
| #25: real Google sign-in reaches the protected Library on web and Android (iOS moved to #103) | None with real Google. Supporting: Jest `navigation.test.tsx` (native module mocked); browser `test_signed_in_library_and_account` (GIS callback, `/v1/auth/google`, `/v1/me` with a bearer token, Library), against stand-ins. | `npm test`; browser harness | **PENDING-MANUAL** | Owner registers the web and Android OAuth clients, signs in for real on web and Android, and captures Library on each. Stubbed: [web-library-signed-in-stub.png](screenshots/web-library-signed-in-stub.png). |
| #25: sign-out makes protected screens unreachable; unauthenticated deep links redirect to Sign-in | Jest `access.test.tsx` (deep links to all 6 protected routes, sign-out closes every route, invalid saved sign-in), `access-edges.test.tsx` (revocation during refresh, successful refresh keeps the screen, expiry notices). Browser `test_signed_out_deep_links_redirect_to_sign_in` (6 routes, production export) and `test_sign_out_closes_protected_routes` (Back after sign-out stays on Sign in; GIS auto-select disabled). | `npm test`; browser harness | **PASS** | [web-deep-link-session-redirects-to-sign-in.png](screenshots/web-deep-link-session-redirects-to-sign-in.png), [web-welcome-signed-out.png](screenshots/web-welcome-signed-out.png), [web-sign-in-expired-notice-stub.png](screenshots/web-sign-in-expired-notice-stub.png). |
| #25: no other sign-in method appears; tokens are never logged | Jest `access.test.tsx` ("offers Google as the only way to sign in", "never writes credentials or tokens to the console"), `transport.test.ts` (HTTPS-only, no embedded credentials, `credentials: 'omit'`, `no-store`, generic errors, 403 deletion-pending detection, memory-only web storage), `public-config.test.ts`. Browser `test_sign_in_without_client_id_offers_no_other_method` and `test_sign_in_to_account_being_deleted_is_refused_with_reason` (no `/v1/me` call after the 403). Accounts service credential-leak tests. | `npm test`; browser harness; pytest | **PASS** for the automated scope. Google-only on a real GIS button is PENDING-MANUAL. | [web-sign-in-no-client-id.png](screenshots/web-sign-in-no-client-id.png), [web-sign-in-deletion-pending-stub.png](screenshots/web-sign-in-deletion-pending-stub.png). |
| #46: after a deletion request the student is signed out, and deleted scores can't be retrieved | Jest `access.test.tsx` and `access-edges.test.tsx` (confirm/cancel, single request while pending, `accepted:false` as failure, retry, expiry during deletion, notice cleared after sign-in). Browser `test_deletion_confirmation_then_signed_out_with_notice`, `test_keyboard_deletion_dialog_focus`, `test_expired_sign_in_during_deletion_explains_nothing_was_deleted`. Server: deletion confirmation and immediate denial, pending deletion blocks refresh and exchange, idempotent request keeps the original deadline (S2), idempotent worker removes only the owner's scores, emulator cross-student isolation. Rules: queued deletion denies direct reads with an old valid token. | `npm test`; browser harness; emulator pytest; rules tests | **PASS** (client and server automated scope) | [web-account-signed-in-stub.png](screenshots/web-account-signed-in-stub.png), [web-delete-confirmation-stub.png](screenshots/web-delete-confirmation-stub.png), [web-sign-in-after-deletion-stub.png](screenshots/web-sign-in-after-deletion-stub.png). End-to-end deletion against the deployed service is part of the manual Google proof. |
| #26: criteria re-run after the merge | `services/accounts` suite (token verification, owner from the verified token, no identity override, fail-closed, per-student scoping, cross-owner denial with real Firestore); Firestore rules. | pytest with and without the emulator; infra `npm test` | **PASS** | 45/45 with the emulator (40 passed, 5 skipped without). Rules 4/4. |

Keyboard check (U6), in Chromium via `test_keyboard_deletion_dialog_focus`: focus "Delete account" and press Enter. The dialog opens and focus is on Cancel. A stray Enter activates Cancel, the dialog closes, no `/v1/account/deletion` request is sent, and focus returns to "Delete account". The same holds for Escape. PASS.

Requirements cross-check: R1 (scaffold tests still pass), R2, R4 and R6 as above; R3 native and web GoogleButton paths tested, real native and GIS behaviour pending manual proof; R7 Jest only and `npm ci` passes with npm 11.19.1, hosted CI not re-run locally.

## Screenshots

All are under `specs/004-access-accounts/screenshots/`, re-captured at 401a1c9. QA opened each one.

| File | Build | Shows |
| --- | --- | --- |
| `web-welcome-signed-out.png` | production export | Welcome, the "Preview" notice, "Explore the planned counseling practice screens.", and "Sign in to explore". |
| `web-sign-in-no-client-id.png` | production export | Sign in with the red "Google sign-in isn't available right now. Please try again later." and no button. |
| `web-deep-link-session-redirects-to-sign-in.png` | production export | A deep link to `/library/session` showing Sign in. |
| `web-library-signed-in-stub.png` | dev server + stand-ins | Library with the Preview notice; Library tab selected. |
| `web-account-signed-in-stub.png` | dev server + stand-ins | Account with Sign out and Delete account. |
| `web-delete-confirmation-stub.png` | dev server + stand-ins | "Delete your account?" with "Delete my account" and Cancel, Cancel showing the focus ring. |
| `web-sign-in-after-deletion-stub.png` | dev server + stand-ins | Sign in with the neutral blue deletion-received notice. |
| `web-sign-in-expired-notice-stub.png` | dev server + stand-ins | Sign in with the neutral notice "Your sign-in expired, so your account was not deleted. Sign in again to request deletion." |
| `web-sign-in-deletion-pending-stub.png` | dev server + stand-ins | Sign in with the red alert "This account is being deleted, so you can't sign in to it." below the button. |

Not captured: Android screens. No emulator run was in scope, and real sign-in can't run there yet.

## Defects and observations

- No functional defects. All 97 Jest tests and all 9 browser tests pass against unchanged production code.
- The round-1 UX notes are fixed and visually confirmed: the deletion notice is neutral (U2), the no-client message is styled (U5), and expiry during deletion now explains itself (U1).
- Test isolation: the emulator test `test_request_is_idempotent_and_keeps_original_deadline` failed once against a reused emulator holding data from an earlier run. It passed after resetting the data with `curl -X DELETE "http://127.0.0.1:8085/emulator/v1/projects/demo-casestudy-tech/databases/(default)/documents"`. The emulator tests assume a clean database; `firebase emulators:exec` gives one, a long-running emulator does not.
- Harness note: the deletion modal fades in, and Playwright's `to_be_visible` passes at opacity 0, so the harness waits for full opacity before capturing.
- Environment: a Firestore emulator (java, PID 38988, port 8085) left over from the first QA round is still running; stopping it was denied by the permission system.

## Reproduce

1. From apps/student: `npx -y npm@11.19.1 ci`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run export:web`, `npm run export:android`.
2. From services/accounts: `uv run --frozen --python 3.12 python -m pytest -q`. For the emulator tests, wrap it in `firebase emulators:exec --only firestore --project demo-casestudy-tech` from the repo root, or reset a reused emulator first.
3. Start the stubbed dev server described in the `browser-verification.py` docstring, then from the repo root run `QA_STUB_ORIGIN=http://localhost:8092 python specs/004-access-accounts/browser-verification.py`. Without `QA_STUB_ORIGIN` only the signed-out tests run.
