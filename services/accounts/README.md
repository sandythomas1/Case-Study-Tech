# Accounts service

Owns Google credential exchange, current-student identity, owner-scoped score reads, and account deletion. No persona/model invocation, transcript, narrative feedback, or score-writing endpoint exists here.

Use Python 3.12 and `uv sync --python 3.12`. Copy `.env.example` to ignored `.env` and supply server configuration. Use Application Default Credentials for local development; Cloud Run must use its workload service account. Do not download or commit a service-account JSON key.

```powershell
uv run --python 3.12 uvicorn cst_accounts.main:app_factory --factory --port 8080 --no-access-log
```

Protected routes independently verify Firebase ID tokens and revocation. Only Google sign-in is accepted. Identity comes from that token, never a query parameter or unverified gateway metadata. All responses are `no-store`. Validation errors and provider failures do not return credentials. HTTP client logs that might include API-key query strings are suppressed; do not enable request-body or debug HTTP logging in deployment.

## Logging

Log only through `cst_accounts/content_free_log.py` (POLICY DAT-1, DAT-7): `log_event("event_name", severity="INFO", **fields)` or, in an error path, `log_error("event_name", exc, code="stable_code", **fields)`. Each call writes one JSON line to stdout for Cloud Logging. Only allow-listed fields with the right type are written: `request_id` and `session_id` (a lowercase UUID or 32 lowercase hex), `scenario_id` (exactly `routine_intake`, `resistant_client` or `crisis_risk`), `scenario_version` (`MAJOR.MINOR.PATCH`), `status_code` (100 to 599), `duration_ms`, and the counts `completed`, `failed`, `overdue` (non-negative, below `2**63`). Anything else, including a Firebase UID or a key in an id field, is dropped. Errors carry only the exception class and the stable code, never the message or a traceback. Pass only ids the service minted, never request or provider data.

An unhandled exception gets the generic 500 envelope (or a 1011 close on a websocket) from `ContentFreeErrors`, a framework-free ASGI middleware in the same module that `api.py` adds innermost. It logs the error by class and code before uvicorn could print its traceback. Ruff (`T20`, `LOG015`) and `tests/test_logging_calls.py` fail on `print`, the root logger (including `logging.root`) any use of `sys.stdout`/`sys.stderr` outside the helper, and `os.write`. From an exception group, the middleware answers the errors and re-raises only the rest, such as a cancellation, under a fixed message. Importing `logging`, `traceback` or `warnings` is allowed only in the files on that test's allow-list, each with its reason; today that is `cst_accounts/firebase.py`, which quiets the HTTP client loggers. `tests/test_body_logging_off.py` checks that the gateway, Terraform, the deploy workflow and the container command keep body and access logging off.

This module is the canonical copy. Every other service keeps a byte-identical copy in its `cst_<service>` package, and `tests/test_content_free_log_copies.py` fails in each service on drift or a missing copy. Change this file, then copy it over the others in the same PR.

The API key stays server-side. `/v1/auth/google` exchanges a Google ID token using Identity Platform; `/v1/auth/refresh` rotates the session through the Secure Token API. The private development deployment is available through API Gateway with finite request/provider timeouts and bounded service scaling. Configure the actual Google provider/OAuth clients, public-auth abuse controls and operational notification destinations before enrolling students. Live Google sign-in is still pending; do not substitute a synthetic auth bypass.

Deletion acceptance writes a durable per-owner denial marker before disabling/revoking the identity. API and direct Firestore reads deny access while the marker exists. Run `uv run python -m cst_accounts.main` as a private hourly job: it disables/revokes again, removes only that owner's scores, deletes the identity, then retains the denial marker for two hours so old signed tokens cannot regain direct database access. Failed requests remain retryable. Alert on any nonzero `failed`/`overdue` result, missed job executions, and approaching deadlines; a local worker test is not evidence of a deployed 30-day guarantee.

Future #40 score writers must check the deletion marker in the same transaction as writing scores to avoid recreating records during cleanup. Future additional account-data collections need explicit deletion coverage; the current worker only owns `students/{uid}` and its direct `scores` subcollection.

Failed cleanup attempts move to a later `next_attempt_at` so a failing first page cannot permanently starve later owners. The original request timestamp/deadline never moves. Completed requests remove their pending-attempt field and keep the two-hour denial marker; no compound Firestore index is required for the current single-field due query.
