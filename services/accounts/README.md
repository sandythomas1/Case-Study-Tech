# Accounts service

Owns Google credential exchange, current-student identity, the owner approval gate, owner-scoped score reads, and account deletion. No persona/model invocation, transcript, narrative feedback, or score-writing endpoint exists here.

Use Python 3.12 and `uv sync --python 3.12`. Copy `.env.example` to ignored `.env` and supply server configuration. Use Application Default Credentials for local development; Cloud Run must use its workload service account. Do not download or commit a service-account JSON key.

```powershell
uv run --python 3.12 uvicorn cst_accounts.main:app_factory --factory --port 8080 --no-access-log
```

Protected routes independently verify Firebase ID tokens and revocation. Only Google sign-in is accepted. Identity comes from that token, never a query parameter or unverified gateway metadata. All responses are `no-store`. Validation errors and provider failures do not return credentials. HTTP client logs that might include API-key query strings are suppressed; do not enable request-body or debug HTTP logging in deployment.

## Owner approval gate (#72)

The MVP is invite-only (POLICY ACC-4…ACC-9). Each account has at most one server-only record at `access/{uid}`: display name, Google email, `state` (`pending`, `approved` or `denied`), `requested_at`, `decided_at` and `version`. No record means `missing`. A revoke sets `denied`.

- `GET /v1/access` returns `{"state": ...}` for the caller only.
- `POST /v1/access/request` takes no body fields. It creates one `pending` record from the verified token's `name` and verified `email` claims, or returns the existing state. The deletion-marker read and the create share one transaction. A denied account gets 403 `access_denied`. A token without a verified email gets 403 `profile_unusable`. The name is NFC-normalized, with control and invisible direction characters removed. Anything that shows it (#73, #74, #76) must still HTML-escape the name and email, and never put either in a mail header or URL.
- Every other route except `/health`, sign-in, refresh and deletion depends on the `approved` guard, `GET /v1/me` included (owner, 2026-11-24). An unapproved account gets 403 `access_not_approved`. The guard reads the record on every request, with no cache. A failed or malformed read is a 503, never an approval. `tests/test_access.py` walks the route table and fails on a route that skips the guard. **#31 must copy that test and guard every session route.**
- `infra/firestore.rules` lets an owner read their scores only while `access/{uid}` says `approved`, and no client can read or write `access/*`.
- Deletion cleanup removes the access record with the scores. A denied student who deletes their account can request again (accepted risk, POLICY §10).
- There is no approval tool until #73. In development, the owner approves a synthetic test account by setting `access/{uid}.state` to `approved` in the console. Until #75, a pending account can't finish sign-in in the app, because sign-in calls `/v1/me`. Because `/v1/me` is gated, **every** existing synthetic dev account needs an approved record before the next deploy, or app sign-in fails for it too. The admin queue (#73) and email (#76) should show the verified email as the primary identifier and the name second: the cleaned name can still imitate another person's, for example with look-alike letters. A name longer than 256 characters after cleanup gets `profile_unusable` (accepted for the MVP).

## Logging

Log only through `cst_accounts/content_free_log.py` (POLICY DAT-1, DAT-7): `log_event("event_name", severity="INFO", **fields)` or, in an error path, `log_error("event_name", exc, code="stable_code", **fields)`. Each call writes one JSON line to stdout for Cloud Logging. Only allow-listed fields with the right type are written: `request_id` and `session_id` (a lowercase UUID or 32 lowercase hex), `scenario_id` (exactly `routine_intake`, `resistant_client` or `crisis_risk`), `scenario_version` (`MAJOR.MINOR.PATCH`), `status_code` (100 to 599), `duration_ms`, and the counts `completed`, `failed`, `overdue` (non-negative, below `2**63`). Anything else, including a Firebase UID or a key in an id field, is dropped. Errors carry only the exception class and the stable code, never the message or a traceback. Pass only ids the service minted, never request or provider data.

An unhandled exception gets the generic 500 envelope (or a 1011 close on a websocket) from `ContentFreeErrors`, a framework-free ASGI middleware in the same module that `api.py` adds innermost. It logs the error by class and code before uvicorn could print its traceback. Ruff (`T20`, `LOG015`) and `tests/test_logging_calls.py` fail on `print`, the root logger (including `logging.root`) any use of `sys.stdout`/`sys.stderr` outside the helper, and `os.write`. From an exception group, the middleware answers the errors and re-raises only the rest, such as a cancellation, under a fixed message. Importing `logging`, `traceback` or `warnings` is allowed only in the files on that test's allow-list, each with its reason; today that is `cst_accounts/firebase.py`, which quiets the HTTP client loggers. `tests/test_body_logging_off.py` checks that the gateway, Terraform, the deploy workflow and the container command keep body and access logging off.

This module is the canonical copy. Every other service keeps a byte-identical copy in its `cst_<service>` package, and `tests/test_content_free_log_copies.py` fails in each service on drift or a missing copy. Change this file, then copy it over the others in the same PR.

The API key stays server-side. `/v1/auth/google` exchanges a Google ID token using Identity Platform; `/v1/auth/refresh` rotates the session through the Secure Token API. The private development deployment is available through API Gateway with finite request/provider timeouts and bounded service scaling. Configure the actual Google provider/OAuth clients, public-auth abuse controls and operational notification destinations before enrolling students. Live Google sign-in is still pending; do not substitute a synthetic auth bypass.

Deletion acceptance writes a durable per-owner denial marker before disabling/revoking the identity. API and direct Firestore reads deny access while the marker exists. Run `uv run python -m cst_accounts.main` as a private hourly job: it disables/revokes again, removes only that owner's scores, deletes the identity, then retains the denial marker for two hours so old signed tokens cannot regain direct database access. Failed requests remain retryable. Alert on any nonzero `failed`/`overdue` result, missed job executions, and approaching deadlines; a local worker test is not evidence of a deployed 30-day guarantee.

Future #40 score writers must check the deletion marker in the same transaction as writing scores to avoid recreating records during cleanup. Future additional account-data collections need explicit deletion coverage; the current worker only owns `students/{uid}`, its direct `scores` subcollection and `access/{uid}`.

Failed cleanup attempts move to a later `next_attempt_at` so a failing first page cannot permanently starve later owners. The original request timestamp/deadline never moves. Completed requests remove their pending-attempt field and keep the two-hour denial marker; no compound Firestore index is required for the current single-field due query.
