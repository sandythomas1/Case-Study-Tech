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
