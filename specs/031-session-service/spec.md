# Spec: Session service for lifecycle, persona turns and time limits (#31)

> **Phase:** Specify · **Status:** clarified · **Owner:** sandythomas1 · **Date:** 2026-11-25
> Source of truth for the task is GitHub Issue #31. This file restates it for the build team and
> records how its open details were settled. If the two disagree, the Issue wins (POLICY AGT-1).

## Problem

The practice session has its contracts (scenario configs #27, handoff #66, content-free logging #63,
approval gate #72) but no running service. A student can't hold a timed conversation with a
simulated client, and nothing hands a completed session toward grading.

## Goals

- An approved student starts one of the three vetted scenarios, exchanges text turns with the
  simulated client, and the session ends on End session or at the 10-minute limit.
- The service is stateless (AD-1): the app holds a server-signed state, and every turn verifies it.
- Nothing from the conversation is stored or logged (RC-03, POLICY DAT-1, DAT-7).
- A failure ends the attempt with no score (RC-09).

## Non-goals

- Voice and speech wiring (#43; the vendor and transport are OPEN as OQ-01). Text turns only.
- The real persona prompts and the scripted runner (#67). #31 ships one short synthetic interim
  prompt per scenario behind the loader (owner decision 2026-11-25).
- The HTTP grader client, the report in the #59 shape and the grading-failed state (#68). #31 hands
  a validated complete handoff to a grader port (owner decision 2026-11-25).
- The conduct safeguard (#33) and in-session crisis handling (#34). The state carries the
  conduct-warning count, fixed at 0 here.
- Any screen (#32). Infra and gateway changes: the routes and env vars already exist in
  `infra/gateway.yaml.template` and `infra/session-grading/main.tf`.

## Functional requirements

1. FR-1. Routes, matching the gateway: `POST /v1/sessions` (start), `POST /v1/sessions/turns`,
   `POST /v1/sessions/end`, `GET /v1/sessions/health`. Every route but health depends on the
   accounts `approved` guard, copied from `services/accounts` (flow 2), failing closed with 403
   `access_not_approved`. A route-inventory test, copied from `services/accounts/tests/test_access.py`
   and extended to websocket routes, matches the guard by identity.
2. FR-2. Start takes a scenario id, the crisis opt-in and the save-transcript choice. It refuses on
   `Catalogue.startable()` raising `ScenarioUnavailable`, and refuses a `requires_opt_in` scenario
   without the opt-in (SES-2). It returns a signed state with no turns.
3. FR-3. The signed state (AD-1) covers the owner UID, scenario id, session id, start time, every
   turn, the conduct-warning count and the save choice. It is signed with the key in
   `CST_STATE_SIGNING_KEY` (Secret Manager). A missing or weak key stops startup.
4. FR-4. Every turn and end first verifies the signature, that the state belongs to the verified UID,
   and that the time limit (from scenario config, SES-5) has not passed. An invalid, expired or
   foreign state is rejected with a stable code, and the app takes the lost-content path.
5. FR-5. A turn appends the student's text, calls the persona model on Gemini Enterprise Agent
   Platform (`CST_PERSONA_MODEL`, the regional endpoint for the configured location, never `global`),
   appends the reply and returns it with a new signed state. The request carries no grounding
   tools, no `store=true` and no session resumption (`docs/decisions` governance settings 4–7).
6. FR-6. End (manual, or the time limit) verifies the final state, builds the #66 handoff, checks it
   with `validate_handoff`, and gives only a `completed` handoff to the grader port. The session
   service never grades. Until #68, the port reports grading unavailable and end returns an unscored
   ending.
7. FR-7. A persona model failure, timeout or connectivity failure ends the attempt with no score
   and no partial result (RC-09).
8. FR-8. No conversation content reaches Firestore, any store, a file or a log. Logging goes only
   through `content_free_log.py`.

## Acceptance criteria (from the Issue)

- AC1. The simulated client responds within the selected scenario.
- AC2. The session ends at the time limit and on manual end; further turns are rejected.
- AC3. A log and storage audit after test sessions finds no conversation content.
- AC4. A model failure produces an unscored ending, not a partial score.

Carry-over ACs from Issue comments: the approved guard on every session route with the extended
route-inventory test (#72); speech wiring, when added, fails closed (#64, recorded for #43).

## Settled details

- 2026-11-25, owner: "Seams + interim prompts (Recommended)". Persona call over REST with httpx and
  google-auth, no new SDK: "REST via httpx + google-auth (Recommended)".
- 2026-11-25, owner: the product formerly called Vertex AI is now Gemini Enterprise Agent Platform. The repo-wide rename lands
  first in its own PR; #31's new code uses the new name.
- 2026-11-25, owner (L2, from the threat model and the plan):
  - AC2 after end: "Accept as AD-2 risk (Recommended)". A stale pre-end state can send turns until
    the limit. #68 records grading once per session_id. The POLICY §10 AD-2 row is widened.
  - Key format: "Base64url text, re-run (Recommended)". The owner re-runs the bootstrap before
    turning on key injection.
  - Rate limit: "Caps + billing alert (Recommended)". The T9 caps, 2 instances × 20 concurrency, and
    an owner-set billing alert.
  - First turn: "Student opens (Recommended)". Figure 5 in the SDD is a mock-up discrepancy.
- 2026-11-25, owner (from the policy review): a persona failure is also within AD-2 scope: "Accept as AD-2 risk (Recommended)". #32 drops the held state on 503 `persona_unavailable`.
