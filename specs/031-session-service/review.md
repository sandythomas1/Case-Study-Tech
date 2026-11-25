# Review: #31 session service

> Review depth: Deep (the owner merges). Reviewers: policy-reviewer, security-reviewer (audit) and
> qa-tester. Date: 2026-11-25. Open blocking findings: **none**.

## Escalations (decided by the owner)

| # | Source | Finding | Disposition |
|---|---|---|---|
| E1 | policy-reviewer, ESCALATE | After a 503 `persona_unavailable`, a client could keep its last good signed state and carry on, or end and hand off a completed attempt. POLICY said a failure ends the attempt, which the stateless server can't enforce. | **Accepted** as AD-2 risk. Owner, 2026-11-25: "Accept as AD-2 risk (Recommended)". The AD-2 rows in POLICY §10 and ARCHITECTURE now include a persona-model failure. #32 drops the held state on that 503, and #68 grades each session id at most once. |
| E2 | threat model (L2-1) | A kept pre-end state still works until the time limit. | **Accepted** as AD-2 risk. Owner: "Accept as AD-2 risk (Recommended)". `test_l2_1_…` pins the bound. |

## Findings

| # | Severity | Source | Finding | Disposition |
|---|---|---|---|---|
| 1 | MEDIUM | security | There is no billing alert behind the caps the owner accepted ("Caps + billing alert (Recommended)"). | **Fixed (docs).** `docs/runbooks/session-grading-deploy.md` step 2 has an owner task to create the budget alert. It needs billing-account access, so agents can't do it. |
| 2 | LOW | security | Async handlers do HMAC and JSON verification on the event loop. | **Accepted.** Nothing blocking runs on the loop, the 1 MiB body cap bounds the cost, and the model call is fully async. Revisit if p95 latency shows contention. |
| 3 | LOW | security | #31 depends on the rename in #138 (`CST_AGENT_PLATFORM_LOCATION`, the `agent_platform_invoke` role). | **Noted in the PR.** Merge #138 first. |
| 4 | LOW | security | No test sent `/end` a body with extra fields. | **Fixed.** `test_session_api.py::test_t7_end_body_strict` has 6 cases, each giving 400 with no grader call. |
| 5 | LOW | security | Dependency audit. | **Fixed.** pip-audit found no known vulnerabilities. |
| 6 | Non-blocking | policy | The ARCHITECTURE AD-2 row didn't match POLICY. | **Fixed.** Both rows match. |
| 7 | Non-blocking | policy | The README named the wrong model. | **Fixed.** It now says `gemini-3.8-flash` (OD-2). The tests and demo use the same name. |
| 8 | Non-blocking | policy | The real prompts in #67 must carry the safety-settings and SES-8 handoff guidance. | **Deferred to #67.** I commented on #67. |
| 9 | Observation | qa | After a 503, `end(S)` with the last good state reaches the grader port. | **Covered by E1.** Harmless now because `UnavailableGrader` scores nothing. #32 must not call end after a 503, and #68 weighs it. |

## Follow-ups (not #31 scope)

- The persona `httpx.AsyncClient` is never closed (there's no lifespan hook). The process holds it for its
  lifetime, which is harmless on Cloud Run. Tidy it up with #68's grader client.
- `deploy.yml` doesn't build the session image yet. That's a `.github/` change, so it needs owner review.
- A UID outside `[A-Za-z0-9]` fails `validate_handoff` closed as not_gradable. Flagged for #32 and #68.
- The Lucid architecture diagram and the decks in `output/` still say "Vertex". The owner updates those.
