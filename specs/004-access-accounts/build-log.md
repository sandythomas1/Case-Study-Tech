# Build log — 004-access-accounts

## 2026-11-20 — Lead resume (/build work on milestone 1 → "start #62")
- Sandy: "I merged #71, update the board and start #62".
- Sandy's choices (AskUserQuestion, verbatim):
  - "Approve; you set Reviewed (Recommended)": #25/#26/#46 Human Review set to Reviewed. #26 moved from Agent Review to In Progress.
  - "You register clients; I prove it (Recommended)": HUMAN ACTION REQUIRED sent with the web and Android client steps. Real-Google proof is a merge gate.
  - "Fold into #103 (Recommended)": #25 AC1 narrowed to web and Android; #103 gained iOS sign-in proof and is blocked by #25.
- Started `git merge --no-ff --no-commit origin/dev`: 12 add/add conflicts (apps/student, README).
- Roster: implementer, then qa-tester, then security-reviewer (audit) and ux-language-advocate (review) in parallel.

### Dispatch 1: implementer (frontier). Reconcile the branch with the #71 scaffold
Routing: merging auth onto a scaffold with a different structure and test runner is cross-cutting, security-sensitive code work. The implementer reduces the risk of losing either side's behavior or tests.
- Outcome, dispatch 1: DONE. 12 conflicts resolved; App.tsx split into the sign-in and account route screens; Jest-only, 46/46 tests; lint, typecheck, and web/android/ios exports pass; lockfile from npm 11.19.1 (real `npm ci` passes); audit 0 high/critical (20 moderate in runtime deps); accounts pytest 30 passed / 5 skipped. Copy changes: Welcome's call to action is now "Sign in to explore", plus a new preview notice. Name/slug come from dev's app.json; `orientation` was dropped. Local merge commit d3991e2; the 017 plan was archived.

### Dispatch 2: qa-tester. Verification and screenshots
Routing: the implementer's checks prove unit behavior. QA reduces the risk that the running web app's guards, sign-in screen, and Account/deletion flow differ from the tests, and it produces the screenshots the UX review needs.

### Dispatch 3: security-reviewer (audit), in parallel with dispatch 2
Routing: mandatory. The diff changes auth guards, token storage wiring, and account deletion; the reviewer reduces the risk of a protected-route bypass, token leakage, or a deletion path that leaves the session alive.
- Outcome, dispatch 3 (security): no blocking findings. 1 MEDIUM, 9 LOW; dispositions in review.md. Fix in this PR: S2, S5, S9, S10. S1/S4/S6/S7 go to a new infra-hardening Issue (L1: they need a live apply). S3 is accepted for the MVP. S8 is noted for grading.
- Created #104 (infra hardening, Backlog, Pending, Deep review, seq 10.6, blocked by #26) for S1/S4/S6/S7.
- Outcome, dispatch 2 (QA): PASS. Jest 74/74 (+28 tests); accounts 35/35 with the emulator; rules 4/4; browser 6/6 (3 against the production export, 3 against stand-ins). Real Google sign-in is PENDING-MANUAL. UX notes: the deletion notice uses error styling; the "not available yet" message is unstyled; an expired session during deletion lands on Sign-in with no explanation. QA's Firestore emulator (PID 38988) was orphaned and QA was not allowed to stop it, so the owner has been told rather than the Lead killing it.

### Dispatch 4: ux-language-advocate (review), on the screenshots
Routing: the new Welcome, Sign-in, Account and deletion copy is user-visible. QA flagged three presentation issues; the reviewer reduces the risk of confusing or alarming wording for counseling students.

### Dispatch 5: implementer (SendMessage continuation). Security fixes S2, S5, S9, S10, in parallel with dispatch 4
Routing: four LOW security fixes in backend, infra tests and dependencies, separate from the UI files the UX review covers.
- Outcome, dispatch 4 (UX): CHANGES_NEEDED, with 2 BLOCKING and 6 SHOULD-FIX findings. Lead answered the domain question from the code. Dispositions are in review.md; they go to implementer fix round 2 after round 1 returns.
- Outcome, dispatch 5 (implementer round 1): S2, S5, S9 and S10 fixed. Accounts 33 passed / 5 skipped; pip-audit clean; web route check 8/8; Jest 74/74. Gap found: after a lost 202, a retry fails verification (the user was disabled and revoked) with 401, so the client can't tell "sent" from "not sent".
- Lead decision (L1): the copy must stay truthful about what is known. A refresh failure before the request is sent → "not deleted". A 401 from the deletion POST → "couldn't confirm" plus guidance. A disabled or pending account at sign-in → a dedicated "being deleted" message; deletion is the only thing that disables a user here.

### Dispatch 6: implementer (round 2). UX fixes U1–U11, U15, U16 plus the S2 client gap
Routing: user-visible copy, accessibility and the session error mapping across the client and the exchange path. The implementer owns the code; QA re-checks afterwards.
- Outcome, dispatch 6 (implementer round 2, continued once after hitting its turn limit): U1–U11, U15, U16 and the S2 client gap fixed. Jest 97/97; accounts 40 passed / 5 skipped; ruff and mypy clean; web routes 8/8. Follow-up noted: a disabled user retrying deletion with a still-valid token gets the "couldn't confirm" notice. That is honest; accepted.

### Dispatch 7: qa-tester (continued). Re-verify, with fresh screenshots
Routing: the copy and focus behavior changed after the first screenshots; QA reduces the risk that verification.md and the screenshots describe the old UI.
### Dispatch 8: security-reviewer (continued). Scoped re-check of rounds 1–2
Routing: the error mapping now reads provider error codes and response bodies on 403. The reviewer reduces the risk of leaking provider detail or opening an account-enumeration signal.
- Outcome, dispatch 8 (security re-check): CLEAR. S11 LOW accepted and noted on #104.
- Outcome, dispatch 7 (QA re-verify): PASS. Jest 97/97; accounts 45/45 with the emulator; browser checks 9/9; web routes 8/8; 9 screenshots re-captured. Keyboard check passes: opening the dialog focuses Cancel, and a stray Enter or Escape does not delete. 4/5 acceptance criteria are proven; #25's real Google sign-in is still PENDING-MANUAL (it needs the owner's OAuth clients). The Firestore emulator (PID 38988) is still running; QA was denied permission to stop it, so the owner has been told.
- Phase 5 closed except the merge gate. Committing locally; the push and the ready-for-review PR wait for the real sign-in proof (standing rule: only a complete feature is PR'd without asking).

## Run 2026-11-22 (evening): #25 + #26 + #18 ship together in PR #62
- Input (Sandy, verbatim): "these issues and work  #25, #26, #18: these ship in the same PR #62"
- Gates: #25 and #26 are In Progress with Human Review Reviewed (this run resumes them). #18 is In Progress with **Human Review Pending**, so its live work waits for the owner (issue-workflow Start check 2). Check 0 passed: CLAUDE.md and .claude match origin/dev.
- Merged origin/dev (6 commits) as aa33233. One add/add conflict on docs/student-toolchain-audit.md; took dev's copy from #114, a strict superset (+54 lines, no removals). Local commit, not pushed yet.
- Checks on aa33233: Jest 97/97, lint and tsc clean, npm audit 0 high/critical (22 moderate); accounts 45/45 with the Firestore emulator; session 44/44; ruff and mypy clean in both services; rules 4/4; anchor-spec check valid.
- Remaining gates, all owner-side:
  - #25 AC1: real Google sign-in on web and Android needs the owner's OAuth clients.
  - #18: Human Review; AC1 rewording (grading has no gateway route by design, AD-3); owner-run apply of infra/session-grading with digest-pinned placeholder images (runbook), then the agent runs the 11 read-only checks.
  - #26: all ACs ticked; nothing left.
- Roster: none spawned yet. No code is left that an agent can usefully change before the owner's actions; QA runs again after the real sign-in and apply.
- Sandy's choices (AskUserQuestion, verbatim): "Reword; you set Reviewed (Recommended)" for #18 and "Push now (Recommended)" for the merge-forward.
- Coordination: session applied-ai-behavioral-sciences-28 (on #46, same PR) is creating the OAuth clients in Chrome. The web client exists. Agreed split: that session finishes the console setup (Android client, Identity Platform provider) and hands over the client IDs. This run owns the branch, apps/student/.env and the real sign-in run for #25 and #46. The deployed API allows only the https://casestudy-tech-dev-2e03d0.web.app origin, so web sign-in runs from Firebase Hosting.
- Pushed a8d750a. #18 body reworded (AC1 plus a "Scope change, 2026-11-22" note) and Human Review set to Reviewed per Sandy's choice. Progress comments posted on #18 and #25.
- Handoff from session -28: web client ID 613104664964-mjjggl0hnre0cam58dr84908b93foob6.apps.googleusercontent.com, JS origin https://casestudy-tech-dev-2e03d0.web.app, consent screen External/Testing with the owner as test user. The Android client and the Identity Platform provider wait for the owner's clicks (Create; secret + Save).
- Writing apps/student/.env was denied by the permission system. Not retried; HUMAN ACTION sent to Sandy.
- Waiting on: the owner's .env, the Android client ID, the saved provider and the infra/session-grading apply. Resume with `/build 004-access-accounts`.
- The owner created apps/student/.env (confirmed only indirectly: reading .env is deny-ruled; the web export contains the real web client ID and the gateway URL).
- Android OAuth client created (from session -28): 613104664964-ci0rtn577piacihoaul37julbgsc6fiv.apps.googleusercontent.com. It's registration only; the native app keeps using the web client ID as the server audience. The Identity Platform provider is not saved yet.
- Gate found: firebase.json has no Hosting config, and the API and OAuth client allow only https://casestudy-tech-dev-2e03d0.web.app.
- Sandy's choice (AskUserQuestion, verbatim): "Authorize me for this deploy". This is a one-off owner exception to AGT-6, covering this dev-project Firebase Hosting deploy of the student web build only. It covers nothing else (no infra apply, no other deploy).
- Added a `hosting` block to firebase.json: serves apps/student/dist/web as a SPA, with nosniff, Referrer-Policy, X-Frame-Options DENY and COOP same-origin-allow-popups (for the GIS popup); no-cache on routes and immutable on hashed /_expo/static assets. One deploy was rejected (Hosting header regex is RE2, no lookahead) and left the live site unchanged; fixed with an extension glob.
- Deployed Hosting (Sandy's one-off authorization). Checks: / and /library/session return 200 with no-cache; hashed JS is immutable; the gateway preflight from the Hosting origin returns 200 with access-control-allow-origin set to that origin.
- Headless Playwright on /sign-in: the real GIS "Continue with Google" button renders, with 0 console errors or warnings. A Google popup opened for client_id …mjjggl0hnre0cam58dr84908b93foob6 with origin=https://casestudy-tech-dev-2e03d0.web.app and reached the account picker, with no origin-mismatch error. Screenshot: screenshots/web-sign-in-real-google-button-hosting.png. Real sign-in itself waits for the provider save and the owner's Google login.
- Session -28 reported the Identity Platform Google provider saved and enabled (web client ID, a new secret the owner entered; no agent saw it). Console side closed.
- Sandy's choice (AskUserQuestion, verbatim): "A second test account (Recommended)". The main account proves sign-in and sign-out only; live deletion uses a spare Google account added as a consent-screen test user.
- Real web sign-in on Hosting (Claude in Chrome, disclosed fallback: needs the owner's real Google session. The owner made every account choice; the agent never touched the Google popup or credentials). Landed on Library. Browser resource timing (paths and status only, no tokens): `POST /v1/auth/google` 200, `GET /v1/me` 200 through https://accounts-7tnmor5w.uc.gateway.dev. Screenshots: screenshots/web-library-real-google-sign-in-hosting.jpg, screenshots/web-account-real-google-sign-in-hosting.jpg. A screenshot showing the owner's email address was deleted, not kept.
- Reload on web returns to Sign in. That's by design (ARCHITECTURE line 71: web tokens live only in memory).
- Real sign-out: Account → Sign out lands on Sign in. Browser Back stays on Sign in, and a deep link to /library/session redirects to /sign-in. #25 AC1 (web) proven live.
- Android: session -28 confirmed (from its record, read-only) that the Android client is package com.casestudytech.student with SHA-1 5E:8F:16:06:2E:A3:CD:2C:4A:0D:54:78:76:BA:A6:F3:8C:AB:F6:25, the Expo template debug key.
- Built a fresh x86_64 release APK at C:/c5: npm ci, `expo prebuild --platform android`, `gradlew assembleRelease --init-script C:\c5\scripts\windows-cmake.gradle`. Public EXPO_PUBLIC_* values were set as process env; .env was not copied. Ninja 1.13.2 is no longer on the machine; the SDK's Ninja 1.10.2 at the short C:/c5 path worked (BUILD SUCCESSFUL in 5m 31s). The first attempt failed in 1s because Gradle resolves `--init-script` relative to `-p android`; an absolute path fixed it.
- APK checks: signer SHA-1 5e8f16…cabf625 matches the Android client; package com.casestudytech.student; the bundle contains the web client ID and the gateway URL.
- Installed on the Pixel_7 emulator (API 36, x86_64, Play services present). `casestudytech://sign-in` shows Sign in with the native "Continue with Google" button. Screenshot: screenshots/android-sign-in-real-config.png. Real sign-in waits for the owner's Google login on the emulator.
- Real Android sign-in: the owner tapped "Continue with Google" on the emulator and chose their account; the agent never touched the Google sheet. Landed on Library. A cold restart (force-stop, relaunch) restored Library from the saved native sign-in. Account → Sign out landed on Sign in; Back left the app (launcher, no protected screen); a `casestudytech://library/session` deep link showed Sign in; a cold start after sign-out showed Welcome. #25 AC1 (Android) proven live. Screenshots: screenshots/android-library-real-google-sign-in.png, screenshots/android-account-real-google-sign-in.png (no personal data on screen).
