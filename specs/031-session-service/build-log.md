# Build log: #31 session service

## Phase 0 — Intake
- 2026-11-25. Sandy: "/build cntinue working on milestone 2". #31 is the next startable M2 Issue (memory + board).
- Gates 0–5 pass: CLAUDE.md/.claude match origin/dev; Human Review Reviewed (2026-11-24, quoted on #31); Status Ready; blockers #26 #27 #63 #66 #72 closed; #18/#19 Released; no OD open (OD-1 settled as AD-1; OQ-01 only blocks voice, which is out of scope).
- Branch feature/31-session-service from origin/dev (a77af9e). Status → In Progress.
- Review Depth: Deep review → the owner reviews before merge.

## Phase 1 — Frame and route
- Owner decisions, 2026-11-25 (verbatim):
  - #31/#67/#68 split: "Seams + interim prompts (Recommended)".
  - Model client: "stop calling it vertex ai, its a new name, vertex is retired, change this throughout the whole repo", then "REST via httpx + google-auth (Recommended)".
  - Rename scope: "Everything, incl. cloud IDs". Sequencing: "Separate docs PR first (Recommended)".
- Verified: Google renamed Vertex AI to Gemini Enterprise Agent Platform (Next 2026); the API host stays aiplatform.googleapis.com.
- Change surfaces: new HTTP service, auth guard copy, signing (crypto), external model call, content handling, handoff to grader port. No UI, no infra.
- Roster:
  - architect (plan → tasks): a new service with a signed-state contract, persona and grader ports, and a time-limit model. Reduces: state format, layering, and the AC2 "further turns rejected after manual end" question under stateless AD-1/AD-2.
  - security-reviewer (threat-model, then audit): mandatory, auth/authz guard, signing key, student content. Reduces: signature/replay/key handling gaps, content leaks, guard gaps.
  - implementer: the code, in 1–2 batches.
  - qa-tester: prove AC1–AC4 + carry-overs, demo transcript GIF.
  - policy-reviewer: project-mandated for services, session data and logging.
  - Skipped: product-owner (scope settled by the owner), ux (no UI), domain-expert (no domain rules change; prompts are #67), devops (infra already provisioned).

## Phase 2 — Consult
- Dispatch architect (plan) + security-reviewer (threat-model) in parallel. Routing sentences above.

## Rename PR (owner directive, 2026-11-25)
- Opened PR #138 (`chore/agent-platform-rename` → dev): Vertex AI → Gemini Enterprise Agent Platform, including `CST_AGENT_PLATFORM_LOCATION` and `cstAgentPlatformInvoke`. Checks: pytest 34 passed, terraform test 3 passed, fmt and validate clean. It waits for the owner because it touches CLAUDE.md and needs an owner Terraform apply. The temporary worktree was removed after the push.
- #31 code reads `CST_AGENT_PLATFORM_LOCATION`. #31's PR stacks on #138's name and must not merge before it.

## Phase 2 outcome: security-reviewer (threat-model)
- Returned FINDINGS and wrote threat-model.md (152 lines). HIGH design requirements, to be folded into the plan by ID:
  - T1: state MAC over the exact bytes sent
  - T2: identity check copied unchanged, plus a route inventory
  - T3: no 422 echo, plus a canary sweep
  - T4: closed host map and typed request allow-list
  - T5: server clock, end grace, no replay across UIDs
- MEDIUM: T6 injection, T7 handoff identity, key encoding, T9 size and cost caps, T10 start input. No L3.
- L2 candidates, held for one batched question after the architect returns:
  - L2-1: AC2 statelessness. Recommended: accept as AD-2 scope.
  - L2-2: signing-key encoding. Recommended: base64url text.
  - L2-3: no per-UID rate limit. Recommended: accept it for the MVP, with caps and a billing alert.
- Sent the architect a note to fold threat-model.md into plan.md and tasks.md (SendMessage, no respawn).
- Architect hit its 40-turn limit after writing plan.md (369 lines) with no tasks.md. Continued via SendMessage to write tasks.md and return (no respawn).

## Phase 3: synthesis
- Architect returned DONE: plan.md (369 lines, over budget, trim in revise) and tasks.md (implementer 20 tasks in 2 batches, qa 5). No ADR.
- Lead decisions (L1, within the Issue and docs):
  - one client-facing `persona_unavailable` code, with the cause in logs only
  - end grace of 60 s
  - safetySettings left at the model defaults in #31, with any change left to #67 and the owner
  - a 20 s persona timeout and no retries
- Batched DECISION NEEDED to the owner: L2-1 (AC2 after end), L2-2 (key encoding), L2-3 (rate limit), and who speaks first (SDD Fig 5 conflicts with FR-2, SP-1 and the #66 fixtures).
- Owner answers (verbatim): L2-1 "Accept as AD-2 risk (Recommended)"; L2-2 "Base64url text, re-run (Recommended)"; L2-3 "Caps + billing alert (Recommended)"; first turn "Student opens (Recommended)". Recorded in spec.md, plan.md and tasks.md.

## Phase 4: implement
- Branch: feature/31-session-service (already created from dev a77af9e).
- Dispatch plan: implementer batch 1 (tasks 1–11, domain), then batch 2 (12–20, adapters, HTTP, packaging), continued via SendMessage. Then qa (21–25).
- Routing: implementer, to turn the 20 tasks into tested code. It runs at the frontier tier because the work is security-sensitive (signed state, auth guard).
- Batch 1 implementer hit its 60-turn limit midway (state, lifecycle, persona port, grading, prompts and tests on disk). Continued via SendMessage to finish and return.
- Batch 1 DONE. Tasks 1–11 ticked. Lead re-ran the checks: pytest 728 passed, ruff and mypy clean. Deviations accepted:
  - duration_ms is clamped to at least the last turn's at_ms (clock skew)
  - the opt-in must match the scenario
  - a persona_bad_reply code
- Noted for #32/#68: a UID outside [A-Za-z0-9] fails closed as not_gradable.
- Batch 2 (tasks 12–20) dispatched via SendMessage to the same implementer, which has the context. Also: re-sync the test_logging_calls.py copy into accounts, so the two copies stay identical.
- Batch 2 implementer hit its turn limit (api, identity, persona adapter, Dockerfile on disk; no ticks). Continued via SendMessage.
- Batch 2 DONE (tasks 12–20). Lead re-ran the checks: pytest 964 passed, ruff and mypy clean. The accounts suite passes 290 (18 skipped). The test_logging_calls.py copies are identical again.

## Phase 5: verify (three dispatches in parallel)
- qa-tester: independent evidence for AC1–AC4 and the carry-overs (tasks 21–25), verification.md, and a transcript demo GIF per pr-demo against the real app with fake identity and persona.
- security-reviewer (audit): the diff touches auth, the signed state, secrets, network egress and student content, all mandatory triggers. Continued via SendMessage, because it holds the threat-model context.
- policy-reviewer: the diff adds a service and changes session data, logging, access and POLICY §10. CLAUDE.md requires it before Agent Review.
- policy-reviewer: ESCALATE (persona failure doesn't strictly end the attempt; held for the batched owner question). Non-blocking items fixed by lead: ARCHITECTURE AD-2 row widened to match POLICY; README and test model set to gemini-3.8-flash. Open: #67 safetySettings/SES-8 note to post on #67.
- security-reviewer (audit): FINDINGS, nothing blocking. The audit section is appended to threat-model.md. Dispositions:
  - MEDIUM, billing alert missing: an owner runbook step was added (it needs billing access).
  - LOW, async handlers: accepted. No blocking I/O on the loop; the CPU cost of verification is bounded by the 1 MiB cap.
  - LOW, #138 ordering: noted in the PR.
  - LOW, /end strict-body test: routed to QA.
  - LOW, pip-audit: the lead ran it, and it found no known vulnerabilities.
- Owner (verbatim) on the persona-failure ESCALATE: "Accept as AD-2 risk (Recommended)". The POLICY and ARCHITECTURE AD-2 rows were widened; #32 is to drop the held state on 503.
- QA hit its turn limit and was continued via SendMessage.
- QA: PASS, 6/6 criteria. Suite 1018 passed; ruff, format and mypy clean; coverage 97%. Its observation (end after a 503) is covered by the owner's AD-2 decision.
- Lead: the demo showed an unapproved model name (gemini-2.5-flash). I fixed it to gemini-3.8-flash in the demo script, verification.md and test_qa_acceptance.py, re-recorded, and checked frames 1, 2 and 4: no secrets, UIDs or tokens. GIF 5.7 MB, 960 px at 8 fps.
- review.md written. No open blocking findings.
- Ship: commit on feature/31-session-service, PR into dev (Refs #31), merges after #138. Deep review, so the owner merges.
- Final roster: architect, security-reviewer (threat model + audit), implementer, qa-tester, policy-reviewer.
