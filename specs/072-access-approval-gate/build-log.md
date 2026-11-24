# Build log: #72 owner approval gate

## Phase 0 — Intake
- 2026-11-24. Sandy asked for "the next logical issue within milestone 2", completed end to end and merged into dev.
- No M2 Issue was startable: every open one was Backlog with Human Review Pending, or blocked. #72 is upstream of #31 (owner decision 2026-11-22) and of #75 → #28.
- Owner, verbatim: "Yes, mark #72 and build (Recommended)". Owner, verbatim: "everthing for milestone 2 should be reviewed".
  - Human Review → Reviewed on #72 and on M2 #28, #29, #31, #32, #39, #43, #67, quoted on each (AGT-4). Upstream non-M2 blockers (#24, #57, #58, #75, #102) were left Pending because they weren't named.
- Owner, verbatim, on merging (Deep review): "One-time merge exception". The lead may merge #72's PR into dev once every reviewer passes with no blocking finding. This applies to this run only.
- Bookkeeping: #27 → Done in Dev (PR #132 merged, f287046).
- Gates 0–5 pass: config matches origin/dev; HR Reviewed (on instruction); Status Ready; blockers #26 and #46 closed; no OD applies.
- Branch feature/72-access-approval-gate from origin/dev (f287046).

## Phase 1 — Frame and route
- spec.md written. D1–D3 settled by the lead (L1).
- Change surfaces: auth/authz guard, Firestore rules, new server-only collection holding name and email, deletion cleanup, gateway config. No UI.
- Roster:
  - lead implements, because the service is small and the change is cohesive (same pattern as #66).
  - security-reviewer (threat-model, in parallel with the implementation, then audit): mandatory, because Firestore rules and auth change. What it should reduce: rule or guard gaps, such as a missing doc read as approved, TOCTOU in request, or a leak of name or email.
  - qa-tester: to prove AC1–AC7 independently and record the demo.
  - policy-reviewer: the diff touches a service, access and logging, and it holds name and email (DAT-2, DAT-7, ACC-4…9).
  - Skipped: architect (no new service or contract beyond the Issue's fixed design), product-owner (the Issue is fully specified), ux (no UI).

## Phase 2 — Consult
- Dispatch security-reviewer (threat-model) in the background, in parallel with the lead's implementation. Routing: the Firestore rules, the guard and a new name/email record change. It should find design gaps before the audit.
- Outcome security-reviewer (threat-model): FINDINGS, blocking. Full list in threat-model.md.
  - Fixed by the lead (L1):
    - HIGH route-inventory test.
    - HIGH rules `exists()` and a full rules matrix.
    - MED deletion-marker read inside the request transaction.
    - MED name normalization and a distinct 403 for an unusable profile.
    - LOW AlreadyExists re-read.
    - Extra tests: 405, zero writes, logs.
  - L2 for the owner:
    - T4: deletion clears a denial.
    - T5: D1 `/v1/me` conflicts with the Issue and ACC-4 (AGT-1).
    - Asked as one batched DECISION NEEDED.
- Owner decisions, 2026-11-24 (verbatim):
  - T4: "Accept and record (Recommended)". Add a POLICY §10 row, revisit before real students; #74 rate-limits its emails.
  - T5: "Gate /v1/me (Recommended)". D1 is reversed: /v1/me now depends on `approved`, and #75 changes sign-in to check /v1/access first.

## Phase 3 — Synthesize
- No architect, so the lead wrote tasks.md. No critic: specialists don't disagree, and the owner settled both L2s.

## Phase 4 — Implement (lead)
- T1–T9 done.
- Checks:
  - accounts: 291 passed against a fresh emulator, 0 skipped. Ruff and mypy clean.
  - infra rules: 9/9.
  - scripts/ci tests: 196 passed.
- Mutation check: removing `approved(uid)` from the rules fails AC5.
- Found during the build:
  - Under contention, a Firestore transaction that exhausts its retries raises ValueError. That was a 500, and is now a 503.
  - `firebase emulators:exec` on Windows runs its script through cmd and leaves the Java emulator orphaned.

## Phase 5 — Verify (parallel)
- Dispatch qa-tester. Routing: give independent evidence for AC1–AC7 against the real router, emulator and rules, which the lead's own tests can't provide, and record the transcript demo GIF.
- Dispatch security-reviewer (audit), continued via SendMessage. Routing: rules and auth changed (mandatory), and it checks that its threat-model findings were closed in code.
- Dispatch policy-reviewer. Routing: the diff touches a service, access, logging and a name/email record (DAT-2, DAT-7, ACC-4…9), and changes POLICY §10.
- Dispatched at the same time: qa-tester (T10), policy-reviewer, and security-reviewer (audit, via SendMessage).
- Security audit: CLEAR with 4 LOWs. I fixed 2: the route test now matches the guard by identity and also covers websocket routes, and a race that finds a denial now returns 403. The other 2 are accepted and noted in the README.
- Policy review: no blocking findings, no ESCALATE. AGT-3: the PR and comment quote T4/T5. The README tells the owner to seed approved records for the dev accounts.
- Lead fix: the #46 emulator test now uses a fresh UID, so it no longer fails when rerun on a long-lived emulator.
- Accounts: 292 passed, ruff and mypy clean. review.md written.
- QA hit its 40-turn cap (PARTIAL) and was continued via SendMessage. Result: 7/7 ACs proven, 10 of 10 mutations caught, coverage 93%. D1 (MED): a flaky concurrency test from a transaction deadlock on the emulator. D2 (LOW).
- Lead fixed D1: the transaction no longer reads access/{uid}. Stress run: 15 of 15 passed. D2 had already been fixed. Final: 299 passed, rules 9/9, ci 196 OK. Demo re-recorded on the final code and its frames checked.

## Phase 6 — Ship
