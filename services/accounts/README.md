# Accounts service

Owns Google credential exchange, current-student identity, owner-scoped score reads, and account deletion. No persona/model invocation, transcript, narrative feedback, or score-writing endpoint exists here.

Use Python 3.12 and `uv sync --python 3.12`. Copy `.env.example` to ignored `.env` and supply server configuration. Use Application Default Credentials for local development; Cloud Run must use its workload service account. Do not download or commit a service-account JSON key.

```powershell
uv run --python 3.12 uvicorn cst_accounts.main:app_factory --factory --port 8080 --no-access-log
```

Protected routes independently verify Firebase ID tokens and revocation. Only Google sign-in is accepted. Identity comes from that token, never a query parameter or unverified gateway metadata. All responses are `no-store`. Validation errors and provider failures do not return credentials. HTTP client logs that might include API-key query strings are suppressed; do not enable request-body or debug HTTP logging in deployment.

The API key stays server-side. `/v1/auth/google` exchanges a Google ID token using Identity Platform; `/v1/auth/refresh` rotates the session through the Secure Token API. These routes require public gateway access, finite timeouts, quotas/rate limits and monitoring before deployment. Configure the Google provider and approved OAuth clients first.

Deletion acceptance writes a durable per-owner denial marker before disabling/revoking the identity. API and direct Firestore reads deny access while the marker exists. Run `uv run python -m cst_accounts.main` as a private hourly job: it disables/revokes again, removes only that owner's scores, deletes the identity, then retains the denial marker for two hours so old signed tokens cannot regain direct database access. Failed requests remain retryable. Alert on any nonzero `failed`/`overdue` result, missed job executions, and approaching deadlines; a local worker test is not evidence of a deployed 30-day guarantee.

Future #40 score writers must check the deletion marker in the same transaction as writing scores to avoid recreating records during cleanup. Future additional account-data collections need explicit deletion coverage; the current worker only owns `students/{uid}` and its direct `scores` subcollection.

Failed cleanup attempts move to a later `next_attempt_at` so a failing first page cannot permanently starve later owners. The original request timestamp/deadline never moves. Completed requests remove their pending-attempt field and keep the two-hour denial marker; no compound Firestore index is required for the current single-field due query.
