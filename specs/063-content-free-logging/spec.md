# Spec: Content-free logging helper (Issue #63)

> **Phase:** Specify · **Status:** clarified · **Owner:** Sandy · **Date:** 2026-11-23
> Source of scope: GitHub Issue #63 (Ready, Reviewed 2026-11-23, Deep review). This spec restates it
> for the build and records the owner's placement decision. The Issue wins on any conflict.

## Problem
Every service will log, and the likely leak paths for session content are request-body logging,
error messages that echo a turn, and tracebacks (plan IR-5). POLICY DAT-1/DAT-7 and ARCHITECTURE §7
forbid session content, names, emails and tokens in logs. Today `services/accounts` logs with a bare
`print`, has no catch-all error handler, and nothing stops a future handler from logging a body.

## Goals
- One logging path per service that cannot emit a field outside a fixed allow-list.
- Error paths log only the exception class and a stable code, never its message or traceback.
- Body logging provably off at the gateway and Cloud Run.
- A repository check that fails CI on `print` or root-logger calls in service code.

## Non-Goals
- The end-to-end no-persistence proof (storage, client logs, crash reports): #39.
- Analytics or crash reporting (AG-3). None are added.
- Session or grading endpoints themselves (#31, #66). They adopt the helper when built.

## Functional Requirements
1. FR-1: A stdlib-only module emits one JSON object per line for Cloud Logging (`severity`,
   `message` = event name, plus allowed fields).
2. FR-2: Allowed fields only: event name, request ID, opaque session ID, scenario ID and version,
   status code, duration, error class, stable error code, plus named integer counts that existing
   log-based metrics depend on (`completed`, `failed`, `overdue`; `infra/accounts/main.tf`
   metrics filter on `jsonPayload.event/failed/overdue`). Any other field is dropped and its value
   never emitted. Values of the wrong type are dropped too.
3. FR-3: Exceptions are logged by class name and stable code. Never `str(exc)`, `repr(exc)`, request
   bodies or tracebacks.
4. FR-4: FastAPI services return the generic error envelope for every error, including unhandled
   exceptions, and never echo input. An unhandled exception must not reach uvicorn's traceback
   logger.
5. FR-5: Request/response body logging stays off at API Gateway and Cloud Run; a test checks
   `infra/` and the container command (`--no-access-log`).
6. FR-6: `services/accounts` adopts the helper everywhere it logs today (the deletion sweep).
7. FR-7 (owner decision 2026-11-23, "Canonical copy"): the canonical module lives in
   `services/accounts`. Each other service holds a byte-identical copy (`services/session` now;
   grading when it exists). A test fails if any copy drifts.

## Acceptance Criteria (Issue #63, verbatim intent)
- [ ] AC1: A unit test shows a log call carrying a non-allow-listed field (e.g. `transcript`,
  `text`) does not emit that field's value.
- [ ] AC2: An error-path test shows an exception whose message contains a synthetic turn produces a
  log line without the turn text.
- [ ] AC3: A test or plan check confirms request and response body logging is disabled for the
  gateway and the Cloud Run services.
- [ ] AC4: A repository check flags `print` calls or root-logger calls in service request handlers.

## References
- Issue #63; POLICY DAT-1, DAT-7; ARCHITECTURE §3 (Cloud Logging row), §5, §7; plan IR-5, AG-2/3/7.
