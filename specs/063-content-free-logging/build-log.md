# Build log: 063-content-free-logging

## 2026-11-23 Phase 0 — Intake
- Request (Sandy): "start 1 feature for milestone 2, see it be completed from end to end".
- Milestone 2 = "Update #2 · Live practice session" (12 open). No Issue passed the Start gate:
  Ready ones (#63, #27, #59) had Human Review Pending; #20 Reviewed but blocked by #102/#101.
- Sandy's choice, verbatim: "63, but can you give me the command to set it to reviewed in this
  terminal and run it for me because I can't load GitHub on my browser?"
- Set #63 Human Review → Reviewed on that instruction; quoted in #63 comment 7122023263 (AGT-4).
- Start gates 0–5: pass (config clean vs origin/dev; Ready; Reviewed; #18 closed; no OD).
- Base: origin/dev db68e91. Branch `feature/63-content-free-logging`.

## Phase 1 — Frame and route
- Surfaces: security/data (logging of user data), architecture (shared module placement).
- L2 asked: helper placement. Sandy chose "Canonical copy (Recommended)": canonical in
  services/accounts, byte-identical copies, drift test; no deploy/.github change.
- Risk found by lead: Starlette's ServerErrorMiddleware re-raises unhandled exceptions, so uvicorn
  logs the traceback even with a catch-all handler (T2). Sweep metrics filter on
  jsonPayload.event/failed/overdue, so the helper allows named int counts (T3, FR-2).
- Roster:
  - implementer — reduces: building T1–T7 test-first across two services.
  - qa-tester — reduces: independent proof of AC1–AC4 and the demo transcript.
  - security-reviewer (audit) — reduces: an independent check that no leak path (traceback,
    exception text, uvicorn/httpx loggers) remains; mandatory trigger "sensitive logs".
  - policy-reviewer (project) — reduces: CLAUDE.md requires it when the diff touches a service and logging.
  - Skipped: architect (placement settled by owner + §5 precedent), ux/domain (no user-visible or
    domain change), critic (no disagreement), devops (no infra change; AC3 is a read-only test).

## Dispatches
- Board: #63 In Progress, comment 7122177256.
- D1 PENDING implementer (mode implement, T1–T7, one batch). Routing: builds the helper test-first across two services.
- D1 DONE implementer: T1–T7. accounts 103 pass/5 skip, session 156 pass; ruff/mypy clean. Deviation (accepted, L1): run_sweep catches unexpected errors → `account_deletion_sweep_crashed` ERROR, exit 1. Sweep severity now INFO/ERROR (was DEFAULT). Catch-all is innermost ASGI middleware. Known limit: named-logger `.info(text)` not flagged statically.
- D2 PENDING qa-tester (verify). Routing: independent proof of AC1–AC4 + demo transcript GIF.
- D3 PENDING security-reviewer (audit). Routing: independent search for remaining leak paths (tracebacks, exception text, third-party loggers, id-field smuggling).
- D4 PENDING policy-reviewer. Routing: CLAUDE.md-mandated check of diff vs POLICY DAT-1/DAT-7 and ARCHITECTURE §5/§7 and #63 ACs.
- D4 DONE policy-reviewer: ESCALATE (non-blocking): IR2 says "only" listed fields; build adds int counts completed/failed/overdue for the sweep alerts. Owner options: accept as built (rec) / amend IR2 (HR→Pending) / drop counts + change infra alerts. Held to batch with security findings. Other non-blocking: named-logger calls not flagged (follow-up); ContentFreeErrors not in the copied module (#31 must rewrite it, no drift check); one-word id residual (documented, no callers).
- Sandy's decision on the D4 ESCALATE, verbatim: "Accept as built (Recommended)". Counts stay; record in PR body + #63 comment; HR stays Reviewed.
- D3 DONE security-reviewer: no blocking. MEDIUM: loose id shape (slugged text/UID pass); AST check misses named-logger warning/exception→lastResort, logging.root, traceback/warnings, `from sys import stderr`; catch-all skips websocket scope and isn't in the copied module. LOW: started-branch logs status 500 vs wire 200; json.dumps outside try (huge int); middleware order (no change); multi-line CMD in AC3 test; Settings() outside sweep try (accepted, content-free).
- D2 DONE qa-tester: PASS 4/4, mutation-proven; added test_a_failing_request_never_logs_or_echoes_its_body; demo GIF at specs/063-content-free-logging/demo/.
- D1b PENDING implementer fix round 1 (SendMessage): security M1–M3, L1, L2, L4. Routing: closes the cheap leak-path gaps before #31 copies the module.
- D1b DONE implementer: fix items 1–6. Lead re-ran: accounts 175 pass/5 skip, session 180 pass; ruff/format/mypy clean; copies identical.
- D3b PENDING security-reviewer scoped re-check (SendMessage) of its findings 1–7. Routing: the catch-all moved modules and gained a websocket path, so the finder confirms its own fixes on a Deep review Issue.
- Lead re-recording the demo: the GIF predates the fix round.
- D3b DONE security-reviewer re-check: M1–M3 and L4/L5/L7 closed; no new leak path; not blocking. Leftover LOWs: hyphen-slug scenario_id, filename-only helper exemption, run-time evasions, nested `sh -c` parse; new pre-existing LOW: BaseExceptionGroup escapes the catch-all.
- D1c PENDING implementer fix round 2 (final): exception groups, exact-path exemption + sys stream attribute/os.write, nested shlex. Routing: #31's websocket handler inherits the middleware and will likely use task groups.
- Accepted without fix: hyphen-slug scenario_id (catalogue-sourced), importlib/__import__/os-level evasions (deliberate, documented residual).
- D1c DONE implementer round 2: groups rebuilt under a fixed message (deviation: split() copies the message, so a plain re-raise leaked; caught by its test), exact-path exemption, sys stream refs + os.write, nested shlex. Lead re-ran: accounts 202/5 skip, session 199; clean; copies identical. Demo re-recorded on the final tree.

## Phase 6 — Ship
- Commit 913cfaa on `feature/63-content-free-logging`, pushed. Demo on pr-media 3df0847.
- PR #131 into dev (Deep review: owner merges). #63 → Agent Review; progress comment 7122932279.

## Phase 7 — Learn and close
- Lessons appended: "A FastAPI exception handler does not stop uvicorn logging the traceback"; "ExceptionGroup.split() copies the group's message onto both halves"; "An independent security re-check after a fix round paid for itself".
- Final roster: implementer (3 dispatches: build + 2 fix rounds), qa-tester (1), security-reviewer (2: audit + re-check), policy-reviewer (1). 7 dispatches total. Owner decisions: 3 (Reviewed on #63, placement, allow-list counts).
- After merge: delete docs/current_feature_plans/063-content-free-logging.md and set #63 Done in Dev.
