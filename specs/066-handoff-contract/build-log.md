# Build log: #66 handoff contract

## Phase 0 — Intake
- 2026-11-23. Owner, verbatim: "#66 handoff contract (Recommended)". Human Review → Reviewed, quoted on #66 (AGT-4).
- Gates 0–5 pass. The only blocker, #63, is closed. No open decision applies (ARCH §10 has none for the handoff).
- Branch feature/66-handoff-contract from origin/dev (165ee3e).

## Phase 1 — Frame and route
- L2 found at intake: the Issue's fields have no owner UID, but the grader writes scores and the saved transcript under it (ARCH flow 4, DAT-1). Owner, verbatim: "UID field in payload (Recommended)".
- Roster: lead implements, because the contract is cohesive and small. qa-tester, policy-reviewer and security-reviewer review.
  - qa-tester: to prove AC1–AC3 independently and to try to break the validator.
  - policy-reviewer: the diff touches a contract, session data and logging.
  - security-reviewer: transcript text and the UID cross a service trust boundary (AG-7). Input validation is the grader's first line.

## Phase 4 — Implement (lead)
- T1–T6 done. `cst_session/handoff/{contract,validation,export}.py`, schema `handoff/completed-session.v1.schema.json`, 3 accepted and 8 rejected fixtures, and 3 test modules. pydantic>=2.12 was added to the session service, as the Issue names it.
- L0 caught by the lead's own test: pydantic `hide_input_in_errors` hides input from `str()` only. `.errors()` still returns raw input, so the validator discards `ValidationError`, and a test pins that behavior.
- Defence in depth: `text` and `owner_uid` are `repr=False`.
- Checks: pytest 333 passed, ruff clean, ruff format clean, mypy clean, synthetic-fixture check passed.

## Phase 5 — Verify and review (dispatching, in parallel)
- qa-tester (verify): prove AC1–AC3 independently, try to break the validator, write verification.md, record the transcript demo GIF.
- policy-reviewer: the diff adds a contract and a dependency, and handles session data and logging (CLAUDE.md agents table).
- security-reviewer (audit): transcript text and the student UID cross the session→grader trust boundary. The validator is the grader's first line of input validation (AG-7, DAT-1).
- policy-reviewer → ESCALATE.
  - E1: the contract can't carry the per-session "don't save" choice (DAT-1, transcript-storage D4). Lead verified D4 against the source.
  - E2: pydantic is a new dependency (ARCH §8).
  - Blocking fix for the lead: the time-limit fixtures show 900000 ms, but SES-5 sets 10 min, so they become ≤600000.
  - Non-blocking: the "text session has no speech turns" rule is a contract choice, not REC-1. The version policy covers only major versions.
  - E1 and E2 go to the owner (CLAUDE.md: an ESCALATE is never settled by the lead).
- Owner, 2026-11-23, verbatim: "Add save_transcript now (Recommended)". A required bool, no default, set by the session service from the student's per-session choice. The grader never stores the transcript when it is false (DAT-1, transcript-storage D4).
- Owner, 2026-11-23, verbatim: "Approve (Recommended)". Approves the pydantic dependency in services/session (ARCH §8).
- security-reviewer → FINDINGS, none blocking.
  - MEDIUM: the 2 MiB cap is below the worst-case legal payload. Fix: 5 MiB, plus a producer encoder that writes raw UTF-8.
  - MEDIUM: consent field (= E1, owner decided).
  - LOW: traceback locals; regex `$` in Python consumers; invisible and bidi text; UTF-16/BOM bodies; model_copy skips validation; grader-boundary list for #68.
  - Lead fixes all of them in code or the README.
- QA → stopped at its turn limit after writing verification.md (AC1–AC3 PASS, F1–F4 Low/Info, 39 tests added) and the demo. F1–F3 match the security findings. F4 (a completed session with no student turn) is a product question deferred to #35.
- Lead fix round 1:
  - save_transcript (required bool, plus a fixture for a missing choice)
  - the time-limit fixtures set to 600000
  - MAX_BODY_BYTES 5 MiB, plus encode_handoff (raw UTF-8) and a worst-case round-trip test
  - strict UTF-8 with no BOM
  - forbid bidi controls and the BOM; invisible-only text doesn't count as visible
  - SessionId length 36
  - README: time limit, the SES-6/REC-1 contract rule, the version policy (AG-9), encoding, a grader-edge list for #68
  Result: 428 pass, ruff, format and mypy clean, the fixture check passes.
- Dispatch: SendMessage policy-reviewer a373b81bdd31169fa (scoped re-check of E1, the duration and the wording) and security-reviewer a4f91c37f6ae06146 (scoped re-check of the MEDIUM and LOW items). Routing: confirm the fixes close their own findings without new gaps.
- policy-reviewer re-check → CLEAR. All 4 findings closed, no new conflict. Took its optional clause: README says save_transcript true is a necessary condition; storage starts only once transcript-storage.md takes effect.
- security-reviewer re-check → FINDINGS, not blocking. All 7 earlier findings closed, worst case 4,065,746 B < 5 MiB cap. One new LOW: more invisible characters count as visible, and tag characters (ASCII smuggling) are allowed beside text.
- Lead fix round 2: _INVISIBLE extended (U+00AD, 034F, 061C, 180E, FE00-FE0F, FFF9-FFFC, 1D173-1D17A, E0000-E007F, E0100-E01EF, written as literal astral characters). Tags stay allowed beside text for the subdivision flags. README: the grader strips tag and format characters before prompting, and ECMA consumers use the `u` flag. 432 pass, all checks clean. No further re-check: the fix is exactly the reviewer's recommendation, pinned by the schema-agreement tests.
