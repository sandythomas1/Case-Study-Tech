# Spec: Completed-session handoff contract (#66)

Source of truth: GitHub Issue #66. Satisfies RC-09, RC-10, DD-02. Constrained by AG-2, AG-4, AG-7,
ARCHITECTURE AD-1, AD-3, §5, §7 and §8, and POLICY SCO-1, SCO-3, SES-2, SAF-1/2 and DAT-1/6/7.

## Outcome
The session service hands the grader one versioned, in-memory payload for a completed session.
Grading work (#35, #68) builds against the committed JSON Schema and synthetic fixtures, without
running the session service.

## Requirements
- R1. A versioned pydantic schema. Fields:
  - session ID
  - **owner UID** (owner decision, 2026-11-23: "UID field in payload (Recommended)")
  - scenario ID and version
  - modality
  - completion status
  - ordered turns: speaker, text, 1-based index, relative time
  - per-turn transcript reliability flags, matching #21's `uncertain_recognition_rule`
  - conduct and crisis flags
  - contract version
- R2. Only `completed` is accepted. Rejection reasons:
  - `incomplete`
  - `content_lost`
  - `ended_for_conduct`
  - `version_mismatch`
  - `malformed`, for structurally invalid input. The Issue doesn't list it, but validation needs it.
- R3. The JSON Schema is exported to `handoff/` and committed. A test regenerates it and compares.
- R4. AG-7: the payload carries no credential. Service identity lives in the transport: Cloud Run IAM allows only the session service account to invoke the grader. The call itself belongs to #68.
- R5. The payload lives only in memory. Validation logs only through `content_free_log`, and never logs turn text or the owner UID.
- R6. Synthetic fixtures for each scenario and each rejection reason.

## Acceptance criteria (from the Issue)
- AC1. Validation tests accept the completed fixtures. They reject the incomplete, content-lost, conduct-ended and wrong-version fixtures.
- AC2. A logging test shows that validating a payload emits no turn text.
- AC3. A test generates the JSON Schema, and it matches the committed copy.

## Interpretations (flag for review)
- Synthetic fixtures under `handoff/fixtures/` are allowed. AG-2 and ARCH §7 forbid *session content* in fixtures, and these are invented lines, the same DAT-6 reading the policy-reviewer agreed for #59.
- Version policy: a consumer accepts only the exact contract versions it knows. Producer and consumer deploy from one repo, so the grader ships a new version first.

## Non-goals
The session lifecycle (#31), sending to the grader (#68) and the report contract (#59).
