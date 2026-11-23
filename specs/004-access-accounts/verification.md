# Verification: 004-access-accounts (#25, #26, #46)

Re-verified 2026-11-19 after fix rounds 1 and 2 (`review.md` S1–S10, U1–U17). Worktree `C:/Users/sandy/Desktop/dev/Case-Study-Tech-issue4`, branch `feature/4-access-accounts`, HEAD 401a1c9 (local, unpushed). Windows, Node 24.11.1. Install used npm 11.19.1.

Re-verified 2026-11-22 after the owner's Welcome decision ("Match #25"): Welcome now offers only "Continue with Google" and states the full POLICY ETH-1 boundary, the same panel Sign in uses. Jest, lint, typecheck and the browser harness were re-run; the counts below are from that run. The coverage figure, the installs and the Android export are from 2026-11-19 and were not re-run.

## Automated checks

| Check | Command (from) | Result |
| --- | --- | --- |
| Clean install | `npx -y npm@11.19.1 ci` (apps/student) | PASS. 1159 packages. `npm audit`: 22 moderate, 0 high or critical. |
| Lint | `npm run lint` | PASS |
| Typecheck | `npm run typecheck` | PASS |
| Jest | `npm test` (2026-11-22) | PASS. 101/101 tests in 6 suites. Coverage on 2026-11-19 (`npx jest --runInBand --coverage`, 97 tests): all-files lines 89.34%. `GoogleButton.web.tsx`'s configured path is covered by the browser harness, not Jest. |
| Web export | `EXPO_NO_DOTENV=1 npm run export:web` | PASS (fresh `dist/web`). Ignoring env files keeps a local `.env` from a dev deploy out of the no-client-ID build. |
| Android export | `npm run export:android` | PASS |
| Accounts service | `uv run --frozen --python 3.12 python -m pytest -q` (services/accounts) | PASS. 40 passed, 5 skipped (the emulator tests need Firestore). |
| Accounts service with the Firestore emulator | same command with `FIRESTORE_EMULATOR_HOST=127.0.0.1:8085` | PASS, 45/45 after the emulator data was reset (see observations). |
| Firestore rules | `npm test` (infra), against the emulator on 127.0.0.1:8085 | PASS, 4/4 |
| Web route tests (S9) | `uv run --no-project --python 3.12 --with pytest --with playwright==1.58.0 python -m pytest -q -p no:cacheprovider infra/accounts/test_web_routes.py` (repo root) | PASS, 8/8 |
| Browser harness | `python specs/004-access-accounts/browser-verification.py` with `QA_STUB_ORIGIN=http://localhost:8092` | PASS, 10/10 on 2026-11-22 (Playwright 1.58.0, bundled Chromium, fresh profile). New: `test_welcome_offers_one_google_action_that_signs_in`. |

The browser harness has two layers:
- **Signed out (production export, no client ID):** `apps/student/dist/web` built with `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` unset. It asserts no JavaScript errors and no external requests.
- **Signed in (stubbed):** real Google sign-in can't run because the owner's OAuth clients aren't registered yet. These tests run against `npx expo start --web --port 8092` with placeholder public values (`EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=qa-stub-web-client-id`, `EXPO_PUBLIC_API_URL=http://127.0.0.1:8899`), set as process environment variables. No .env file was written. The stand-ins are a local fake accounts API (records request paths only, never tokens; per-test modes for a 403 `account_deletion_pending` exchange and a rejected refresh) and a Google Identity Services stand-in served through Playwright `page.route`. No production code was changed. These tests prove the real web guards, session, transport, Account screen and deletion flow. They do **not** prove Google sign-in.

Harness changes in this round, copy only where it changed on purpose: the deletion notice, "Google sign-in isn't available right now…", "Delete my account", and the "Preview" notice title. Added three tests: keyboard focus on the deletion dialog, expiry during deletion, and sign-in refused for an account being deleted.

## Acceptance criteria

| AC | Test(s) or screenshot that prove it | Command | Result | Evidence |
| --- | --- | --- | --- | --- |
| #25 AC1: a valid Google sign-in opens the protected Library on web and Android (iOS moved to #103) | None with real Google. Supporting: Jest `navigation.test.tsx` (native module mocked); browser `test_signed_in_library_and_account` (GIS callback, `/v1/auth/google`, `/v1/me` with a bearer token, Library), against stand-ins. | `npm test`; browser harness | **PASS (live, 2026-11-22), web and Android.** | Web: the owner signed in with their real Google account on https://casestudy-tech-dev-2e03d0.web.app and landed on Library. Browser resource timing, paths and status only: `POST /v1/auth/google` 200 and `GET /v1/me` 200 through the deployed gateway. [web-sign-in-real-google-button-hosting.png](screenshots/web-sign-in-real-google-button-hosting.png), [web-library-real-google-sign-in-hosting.jpg](screenshots/web-library-real-google-sign-in-hosting.jpg), [web-account-real-google-sign-in-hosting.jpg](screenshots/web-account-real-google-sign-in-hosting.jpg). Android: a fresh x86_64 release APK (package `com.casestudytech.student`, signer SHA-1 matching the registered Android client) on the Pixel_7 emulator, API 36. The owner signed in with real Google and landed on Library; a cold restart kept the sign-in. [android-sign-in-real-config.png](screenshots/android-sign-in-real-config.png), [android-library-real-google-sign-in.png](screenshots/android-library-real-google-sign-in.png), [android-account-real-google-sign-in.png](screenshots/android-account-real-google-sign-in.png). Stubbed: [web-library-signed-in-stub.png](screenshots/web-library-signed-in-stub.png). |
| #25 AC2: after sign-out, protected screens are unreachable | Jest `access.test.tsx` (sign-out closes every route), `access-edges.test.tsx` (revocation during refresh). Browser `test_sign_out_closes_protected_routes` (Back after sign-out stays on Sign in; GIS auto-select disabled). | `npm test`; browser harness | **PASS** | [web-deep-link-session-redirects-to-sign-in.png](screenshots/web-deep-link-session-redirects-to-sign-in.png), [web-welcome-signed-out.png](screenshots/web-welcome-signed-out.png), [web-sign-in-expired-notice-stub.png](screenshots/web-sign-in-expired-notice-stub.png). Live on Hosting (2026-11-22), after a real sign-in: Sign out landed on Sign in, browser Back stayed on Sign in, and a deep link to `/library/session` redirected to `/sign-in`. A reload also returns to Sign in, by design (web tokens live only in memory, ARCHITECTURE line 71). Live on Android (2026-11-22): Sign out landed on Sign in, Back left the app with no protected screen, a `casestudytech://library/session` deep link showed Sign in, and a cold start after sign-out showed Welcome (the saved sign-in was cleared). |
| #25 AC3: an unauthenticated user cannot reach any protected screen | Jest `access.test.tsx` (deep links to all 6 protected routes, invalid saved sign-in, no protected screen while a saved sign-in is checked). Browser `test_signed_out_deep_links_redirect_to_sign_in` (6 routes, production export). | `npm test`; browser harness | **PASS** | [web-deep-link-session-redirects-to-sign-in.png](screenshots/web-deep-link-session-redirects-to-sign-in.png). Live on Hosting and Android (2026-11-22): a deep link to `/library/session` showed Sign in. |
| #25 AC4: no other sign-in method appears anywhere in the UI | Jest `access.test.tsx` ("offers Google as the only way to sign in", "offers only Continue with Google and states the educational boundary" on `/` and `/sign-in`). Browser `test_sign_in_without_client_id_offers_no_other_method`, `test_welcome_is_public`, `test_welcome_offers_one_google_action_that_signs_in`. | `npm test`; browser harness | **PASS.** Live (2026-11-22): the deployed Sign in page shows only the real Google button. | [web-sign-in-no-client-id.png](screenshots/web-sign-in-no-client-id.png), [web-welcome-google-stub.png](screenshots/web-welcome-google-stub.png). |
| #25 AC5: tokens never appear in logs | Jest "never writes credentials or tokens to the console", `transport.test.ts` (generic errors, memory-only web storage), accounts service `test_invalid_request_never_echoes_credentials`. Browser `test_sign_in_to_account_being_deleted_is_refused_with_reason` (no `/v1/me` call after the 403). | `npm test`; pytest | **PASS** (automated). Not checked live: no search of the deployed services' logs for token values was run. | [web-sign-in-deletion-pending-stub.png](screenshots/web-sign-in-deletion-pending-stub.png). |
| #25 requirement: Welcome offers a single "Continue with Google" action and states the educational boundary (RC-21, POLICY ETH-1) | Jest `access.test.tsx` ("offers only Continue with Google and states the educational boundary on /", "states every ETH-1 limit", "signs in from Welcome straight to Library"). Browser `test_welcome_offers_one_google_action_that_signs_in`, `test_welcome_is_public`. | `npm test`; browser harness | **PASS** (2026-11-22, stubbed Google) | [web-welcome-google-stub.png](screenshots/web-welcome-google-stub.png), [web-welcome-signed-out.png](screenshots/web-welcome-signed-out.png). Not yet redeployed to Hosting. |
| #46 AC1: deletion requires explicit confirmation | Jest `access.test.tsx` and `access-edges.test.tsx` (confirm and cancel, single request while pending). Browser `test_deletion_confirmation_then_signed_out_with_notice`, `test_keyboard_deletion_dialog_focus` (Enter and Escape cancel; no request sent). Server `test_deletion_requires_confirmation_and_denies_access_immediately`. | `npm test`; browser harness; pytest | **PASS (live, 2026-11-22)** | [web-delete-confirmation-real-hosting.jpg](screenshots/web-delete-confirmation-real-hosting.jpg), [web-delete-confirmation-stub.png](screenshots/web-delete-confirmation-stub.png). |
| #46 AC2: the account and scores are removed within 30 days (scheduled job plus test) | Server `test_deletion_worker_is_idempotent_and_removes_only_owner_scores`, `test_deletion_worker_retries_failed_storage_without_deleting_identity`, `test_request_is_idempotent_and_keeps_original_deadline` (S2); emulator `test_erasing_scores_does_not_touch_another_student`. | pytest with and without the emulator | **PASS (live, 2026-11-22)** | Live: the scheduled `account-deletion` job removed the account 42 s after the request; see "#46: account deletion" below. |
| #46 AC3: after the request, the student is signed out and the deleted scores are no longer retrievable | Jest `access.test.tsx` and `access-edges.test.tsx` (confirm/cancel, single request while pending, `accepted:false` as failure, retry, expiry during deletion, notice cleared after sign-in). Browser `test_deletion_confirmation_then_signed_out_with_notice`, `test_keyboard_deletion_dialog_focus`, `test_expired_sign_in_during_deletion_explains_nothing_was_deleted`. Server: deletion confirmation and immediate denial, pending deletion blocks refresh and exchange, idempotent request keeps the original deadline (S2), idempotent worker removes only the owner's scores, emulator cross-student isolation. Rules: queued deletion denies direct reads with an old valid token. | `npm test`; browser harness; emulator pytest; rules tests | **PASS (live, 2026-11-22)** plus the automated scope | Live: see "#46: account deletion (live, 2026-11-22)" below and [web-delete-confirmation-real-hosting.jpg](screenshots/web-delete-confirmation-real-hosting.jpg). Stubbed: [web-account-signed-in-stub.png](screenshots/web-account-signed-in-stub.png), [web-delete-confirmation-stub.png](screenshots/web-delete-confirmation-stub.png), [web-sign-in-after-deletion-stub.png](screenshots/web-sign-in-after-deletion-stub.png). |
| #26 AC1: requests without a valid token are rejected with 401 | `test_invalid_auth_is_401_without_data_access`, token-verification and fail-closed tests. | pytest | **PASS** | 45/45 with the emulator. Live (2026-11-22): gateway `/v1/me` and session routes return 401 with no token or an invalid one (#18 checks 4 and +). |
| #26 AC2: a test proves student A cannot read student B's scores through the API or direct Firestore access | `test_http_authorization_with_real_firestore_store_blocks_cross_owner_access` (emulator), `test_another_owner_cannot_touch_a_pending_deletion`; Firestore rules tests. | emulator pytest; infra `npm test` | **PASS** | Rules 4/4. |
| #26 AC3: unauthenticated users see only sign-in and informational screens | The #25 AC3 tests above; Jest "keeps Welcome public" and the signed-in redirects from `/` and `/sign-in`. | `npm test`; browser harness | **PASS** | [web-welcome-signed-out.png](screenshots/web-welcome-signed-out.png). |

Keyboard check (U6), in Chromium via `test_keyboard_deletion_dialog_focus`: focus "Delete account" and press Enter. The dialog opens and focus is on Cancel. A stray Enter activates Cancel, the dialog closes, no `/v1/account/deletion` request is sent, and focus returns to "Delete account". The same holds for Escape. PASS.

## #46: account deletion (live, 2026-11-22)

This ran on https://casestudy-tech-dev-2e03d0.web.app in the owner's Chrome through Claude in Chrome, the disclosed fallback, because it needs a real Google sign-in. The owner made every Google account choice and used a spare test account. The agent confirmed the account was not the owner's main one before it opened the dialog, and the owner approved the deletion in chat. Only paths, status codes and timestamps are recorded here: no tokens, IDs or email addresses.

| Time (local) | Step | Evidence | Result |
| --- | --- | --- | --- |
| 17:59:41 | Spare account signs in | `POST /v1/auth/google` 200, `GET /v1/me` 200 (accounts request logs) | Library |
| 18:00:36 | Account, then Delete account, then "Delete my account" | The dialog says the account and saved scores are permanently deleted within 30 days and this can't be undone ([web-delete-confirmation-real-hosting.jpg](screenshots/web-delete-confirmation-real-hosting.jpg)). `POST /v1/account/deletion` 202. | **Signed out immediately**, landing on Sign in with "We received your request to delete your account…" |
| 18:00:37 | Server state after the request | Identity Platform user `disabled: true`, refresh tokens revoked (`validSince` 18:00:37). `account_deletions` record `state=pending`, with a deadline 30 days out and only timestamps (no session content). | Denied right away |
| 18:01:18 | Scheduled `account-deletion` job | The job exited 0, the record became `state=completed`, and the Identity Platform user was removed | Deleted 42 s after the request |
| 18:03:19 | The owner signs in again with the same Google account | `POST /v1/auth/google` 200. Identity Platform created a **new** user with a different ID. | The new account has 0 scores; the deleted account's data is not reachable from it |

Scores: the spare account never had a score, since no score-writing path exists yet. A collection-group query found 0 `scores` documents anywhere in the database, before and after. The removal of existing scores and the rules denial while a deletion is pending are proven by the emulator worker test and the rules tests in the table above.

**#46 AC3: PASS.** The student was signed out immediately, the account was denied and then deleted, and nothing from it can be retrieved. Observation: the "This account is being deleted" refusal could not be shown live, because the job finished before the owner retried. It holds only during the pending window, and the browser test `test_sign_in_to_account_being_deleted_is_refused_with_reason` proves it. After deletion, the same Google account can sign up again as a new, empty account. That is expected behavior, not a defect.

## #18: Google Cloud baseline (live, 2026-11-22)

Applied by the agent under the owner's one-off AG-9 exception (build log, "finish and merge PR #62"), following `docs/runbooks/session-grading-deploy.md` steps 2–4 in `casestudy-tech-dev-2e03d0`. Both services run the Cloud Run `hello` placeholder pinned at `sha256:04e460afdf4c4c8e615b809d3b41249f89af11ef5358a81fc62b3f09a70c6169`, and `inject_state_signing_key` is false.

| Step | Plan | Result |
| --- | --- | --- |
| 2. Bootstrap (targeted) | 19 to add, 0 to change, 0 to destroy | Applied. Signing key version 1 was added to Secret Manager; no value was printed. |
| 3. Services | 4 to add (2 services, 2 invoker bindings), 0 to destroy | Applied. `https://session-447ob3nwoa-uc.a.run.app`, `https://grading-447ob3nwoa-uc.a.run.app`, both with deletion protection on. |
| 4. Gateway routes | 1 to add, 1 to change, 1 to destroy: the immutable API config was replaced (`create_before_destroy`), superseding config `accounts-20261022171434854700000001` | Applied after the owner approved the replacement. The accounts service, its job and its IAM were not in the plan. |
| Drift | Full `plan` in both modules | "No changes" in both |

| # | Check | Expect | Result |
| --- | --- | --- | --- |
| 1 | Session `/health` unauthenticated | 403 | 403 |
| 2 | Grading `/health` unauthenticated | 403 | 403 |
| 3 | Gateway `/v1/sessions/health` | 200 | 200 (placeholder image) |
| 4 | `POST /v1/sessions/end` with no JWT; `POST /v1/sessions/turns` with an invalid JWT | 401, 401 | 401, 401. The first run sent no body and got 411 from Google's front end; the runbook command now sends `{}`. |
| 5 | Gateway `/v1/grading/health` | 404 | 404 |
| 6 | Grading invokers | `cst-session` only | `roles/run.invoker`: `cst-session` only |
| 7 | Session invokers | `cst-gateway` only | `roles/run.invoker`: `cst-gateway` only |
| 8 | `cst-gateway` project roles | none | none |
| 9 | Grading `/health` with the owner's identity token | 200 | 200 |
| 10 | Runtime roles | custom roles only | `cstGrading` (grading), `cstSessionIdentity` (session), `cstVertexInvoke` (both). No Owner, Editor or Viewer. |
| 11 | Signing key accessors | `cst-session` only | `secretAccessor`: `cst-session` only |
| + | Accounts `/v1/me` with no token, after the gateway change | 401 | 401 |

#18 acceptance criteria:
- **AC1 (deploy, session health through the gateway, grading health only for an authorized identity): PASS** on the placeholder, from checks 2, 3, 5 and 9. The runbook requires all eleven checks to be rerun after the first real image deploy (#31, Phase 5).
- **AC2 (least privilege, reviewed): PASS**, from checks 6, 7, 8, 10 and 11. The security reviewer reviewed PR #62 on 2026-11-22 with no blocking findings: each #18 identity holds only its custom roles. Two broader findings are deferred, not fixed here: grading's project-wide create permission could reach deletion markers once a real grading image runs (S12, tracked in #104; runbook step 3 also gates real images on #72), and `cstVertexInvoke` is not scoped to one model (S16, revisit with OD-2/#65). Full dispositions: review.md, 2026-11-22.
- **AC3 (recreatable from the repo): PASS.** Both modules plan "No changes" against the repo. The runbook as now written covers every step. Not in Terraform: the Firestore database, the Identity Platform Google-only provider, the OAuth clients and the Firebase apps and Hosting site were created by hand; `docs/accounts-setup.md` records those steps (moving the provider config into Terraform is S20, #104). The first run did not follow it unchanged: three runbook bugs were found and fixed on the way (PowerShell 5.1 splitting unquoted `-out=` arguments, the targeted plan prompting for image variables while holding the state lock, and check 4's bodiless POST returning 411), and the owner cleared the stale lock with `terraform force-unlock` by hand. Steps 2–4 were run by the agent under the owner's one-off AG-9 exception (build-log, 2026-11-22); AG-9 still stands for every later apply.

Requirements cross-check: R1 (scaffold tests still pass), R2, R4 and R6 as above; R3 native and web GoogleButton paths tested, real native and GIS behaviour pending manual proof; R7 Jest only and `npm ci` passes with npm 11.19.1, hosted CI not re-run locally.

## Screenshots

All are under `specs/004-access-accounts/screenshots/`, re-captured at 401a1c9. QA opened each one.

| File | Build | Shows |
| --- | --- | --- |
| `web-welcome-signed-out.png` | production export, no client ID (2026-11-22) | Welcome, the "Preview" notice, the full educational boundary, and "Google sign-in isn't available right now…" with no button or link. |
| `web-welcome-google-stub.png` | dev server + stand-ins (2026-11-22) | Welcome with the single "Continue with Google (QA stand-in)" button and the full educational boundary. |
| `web-sign-in-no-client-id.png` | production export | Sign in with the red "Google sign-in isn't available right now. Please try again later." and no button. |
| `web-deep-link-session-redirects-to-sign-in.png` | production export | A deep link to `/library/session` showing Sign in. |
| `web-library-signed-in-stub.png` | dev server + stand-ins | Library with the Preview notice; Library tab selected. |
| `web-account-signed-in-stub.png` | dev server + stand-ins | Account with Sign out and Delete account. |
| `web-delete-confirmation-stub.png` | dev server + stand-ins | "Delete your account?" with "Delete my account" and Cancel, Cancel showing the focus ring. |
| `web-sign-in-after-deletion-stub.png` | dev server + stand-ins | Sign in with the neutral blue deletion-received notice. |
| `web-sign-in-expired-notice-stub.png` | dev server + stand-ins | Sign in with the neutral notice "Your sign-in expired, so your account was not deleted. Sign in again to request deletion." |
| `web-sign-in-deletion-pending-stub.png` | dev server + stand-ins | Sign in with the red alert "This account is being deleted, so you can't sign in to it." below the button. |
| `web-sign-in-real-google-button-hosting.png` | Firebase Hosting, real config (2026-11-22) | Sign in with the real Google Identity Services "Continue with Google" button. |
| `web-library-real-google-sign-in-hosting.jpg` | Firebase Hosting, real Google sign-in (2026-11-22) | Library after the owner's real Google sign-in. |
| `web-account-real-google-sign-in-hosting.jpg` | Firebase Hosting, real Google sign-in (2026-11-22) | Account with Sign out and Delete account, signed in for real. |
| `web-delete-confirmation-real-hosting.jpg` | Firebase Hosting, the spare test account (2026-11-22) | The real "Delete your account?" dialog, with "Delete my account" and Cancel. |

Screenshots that show the owner's email address (the GIS "Continue as …" button) are deliberately not kept.

| `android-sign-in-real-config.png` | Android release APK, real config, Pixel_7 API 36 (2026-11-22) | Sign in with the native "Continue with Google" button. |
| `android-library-real-google-sign-in.png` | same, after the owner's real Google sign-in | Library with the Preview notice. |
| `android-account-real-google-sign-in.png` | same | Account with Sign out and Delete account. |

## Defects and observations

- No functional defects. All 101 Jest tests and all 10 browser tests pass (2026-11-22).
- The round-1 UX notes are fixed and visually confirmed: the deletion notice is neutral (U2), the no-client message is styled (U5), and expiry during deletion now explains itself (U1).
- Test isolation: the emulator test `test_request_is_idempotent_and_keeps_original_deadline` failed once against a reused emulator holding data from an earlier run. It passed after resetting the data with `curl -X DELETE "http://127.0.0.1:8085/emulator/v1/projects/demo-casestudy-tech/databases/(default)/documents"`. The emulator tests assume a clean database; `firebase emulators:exec` gives one, a long-running emulator does not.
- Harness note: the deletion modal fades in, and Playwright's `to_be_visible` passes at opacity 0, so the harness waits for full opacity before capturing.
- Environment: a Firestore emulator (java, PID 38988, port 8085) left over from the first QA round is still running; stopping it was denied by the permission system.

## Reproduce

1. From apps/student: `npx -y npm@11.19.1 ci`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run export:web`, `npm run export:android`.
2. From services/accounts: `uv run --frozen --python 3.12 python -m pytest -q`. For the emulator tests, wrap it in `firebase emulators:exec --only firestore --project demo-casestudy-tech` from the repo root, or reset a reused emulator first.
3. Build the no-client-ID export with `EXPO_NO_DOTENV=1 npm run export:web`. Start the stubbed dev server described in the `browser-verification.py` docstring, then from the repo root run `QA_STUB_ORIGIN=http://localhost:8092 python specs/004-access-accounts/browser-verification.py`. Without `QA_STUB_ORIGIN` only the signed-out tests run.
