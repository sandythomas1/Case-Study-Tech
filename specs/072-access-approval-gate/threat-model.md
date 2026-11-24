# Threat model: owner approval gate (#72)

> Security agent, threat-model mode, 2026-11-24. Base `origin/dev` (f287046). I read the lead's
> in-progress working tree, so a few rows note what it already does. Issue #72 is authoritative.

## Assets
- **A1 Protected student data.** Scores now; library, sessions, reports and history later (#31).
- **A2 Access record `access/{uid}`.** Google display name and email (PII under DAT-2, DAT-7), plus
  state, times and version. State is the authorization decision.
- **A3 Owner attention.** The admin queue (#73) and the owner email (#74) consume what A2 stores.
- **A4 Deletion guarantees.** DAT-3 says the access record is gone within 30 days.

## Trust boundaries and entry points
- Client to API Gateway (JWT checked) to private accounts service (re-verifies the forwarded token,
  `check_revoked=True`, `google.com` only).
- Service to Firestore (service account). Client to Firestore is governed only by `infra/firestore.rules`.
  The app has no Firebase SDK, so the rules are the second line of defence.
- Entry points: `GET /v1/access`, `POST /v1/access/request`, the `approved` guard on `/v1/scores`
  (and every future protected route), the scores read rule, the deletion sweep (`erase_student_data`).
- Untrusted input: the whole request body, query and headers, and the **contents** of the token's
  `name` claim. The `name` is verified as issued by Google, but the user picks it freely.

## Threats (STRIDE, ranked by likelihood x impact)

**T1 HIGH: Elevation of privilege when a protected route skips the guard.** The gate is opt-in per
route (`Depends(approved)`). A route added later, here or in #31, that uses `signed_in` instead
silently admits pending and denied accounts. That breaks ACC-4 and ACC-7.
- Mitigation: a **route-inventory test** walks `app.routes`. Every route outside an explicit
  allow-list (`/health`, `/v1/auth/google`, `/v1/auth/refresh`, `/v1/access`, `/v1/access/request`,
  `/v1/account/deletion`, plus `/v1/me` if T5 keeps it) must have `approved` in its dependant tree.
  The test fails on any new unlisted route. #31 copies the same test.
- Also test that no setting or env var turns the gate off (ACC-9 / FR-10). The guard is unconditional in `create_app`.

**T2 HIGH: The Firestore rules gate fails open, or the access record becomes readable.**
- `get(access/uid).data.state == 'approved'` on a missing doc returns null, and `.data` then errors.
  An error is a deny, so it fails closed, but only implicitly. Write it explicitly:
  `exists(/databases/$(database)/documents/access/$(uid)) && get(...).data.state == 'approved'`,
  inside `activeOwner` so the deletion-marker check stays.
- Rules are additive (OR). A later `match /access/{uid} { allow read: if request.auth.uid == uid }`
  would expose the email to the client. AC5 as written only tests **writes** to the access record.
- Required emulator tests (beyond AC5): owner score read denied when the access doc is **missing**,
  has **no `state`**, has `state: "Approved"`, `"revoked"` or a non-string, or is `pending` or `denied`.
  Allowed only for exact `approved`. Denied when approved but a deletion marker exists. **Owner,
  other user and unauthenticated users cannot read or list `access/*`**, and nobody can create, update or delete it.

**T3 MEDIUM: TOCTOU between the deletion check and the request create (Tampering, DAT-3).**
`request_access` checks `eligible()` (the marker) **outside** the create transaction. Suppose a
request passes `verify` and the marker check, the user confirms deletion in parallel, and the sweep
runs `disable` then `erase_student_data`. The create then commits and recreates `access/{uid}` with
the name and email after the erase. That PII outlives the account and breaks DAT-3. The window is
small but real, because `request_deletion` suppresses a failed `disable`.
- Mitigation: read `account_deletions/{uid}` **inside the same transaction** as the access read and
  create. Raise `DeletionPending` if it exists. The marker outlives the auth user by design, so this closes the window.
- Test: a fake store where the marker appears between `eligible()` and the create, and no record is written.
- The guard's two reads (marker, then access) are not atomic either. The impact is one extra
  owner-only read during a deletion confirmation, which is acceptable (see LOW L1).

**T4 MEDIUM: Deletion clears a denial (Repudiation / abuse of ACC-6). Owner decision (L2).**
A denied user requests deletion. The sweep erases `access/{uid}` (as DAT-3 requires) and deletes the
auth user. The next Google sign-in gets a **new UID** in state `missing`, so the user can request
again and, once #74 lands, trigger another owner email. ACC-6 ("a denied account cannot re-request")
and DAT-3 conflict here.
- Options for the owner: (a) accept and record the risk in POLICY §10 (the owner can deny again;
  the cost is one email per deletion cycle of 30 days or less); (b) keep a non-reversible denial
  tombstone (an HMAC of the Google `sub` under a Secret Manager key) after deletion. That is new
  retained data and needs a DAT-2 amendment. Recommendation: (a) for the MVP. Don't build (b) without a decision.

**T5 MEDIUM: Spec D1 conflicts with the Issue and the policy (AGT-1).** Issue #72 says *"Only access
state, request access, sign-out and account deletion are reachable without approval."* POLICY ACC-4
and the §1 roles table, and ARCHITECTURE §4 step 2, say the same. D1 adds `GET /v1/me` as an L1 call,
but a rule beats a lead decision. The security impact today is nil, because it returns only the
caller's own UID, which is already in the token. The risk is drift: any field added to `/v1/me` later
reaches unapproved accounts without review.
- Mitigation, pick one: (a) **recommended**: gate `/v1/me` with `approved`, and have the app use
  `GET /v1/access` as its sign-in check. That call already proves the token and gives #75 the state.
  (b) Escalate to the owner to amend ACC-4 and the Issue. If (b), the T1 allow-list test pins
  `/v1/me`'s response to exactly `{"uid"}`.
- Sign-in and refresh are reachable by necessity (tokens are a precondition for "see access state").
  The Issue implies them, but say so in the PR.

**T6 MEDIUM: The display name is attacker-chosen text that reaches the admin UI and the owner email
(stored XSS, phishing, spoofing).** A Google display name can be any Unicode up to its length cap,
for example `"Approve me: https://evil.example"`, CR/LF, bidi overrides (U+202A–202E, U+2066–2069)
or zero-width characters that make one requester look like another. It is stored now and rendered
by #73, #74 and #76.
- Mitigation now: NFC-normalize. Reject or strip C0/C1 controls (including CR/LF), bidi overrides
  and zero-width characters. Keep the 256 cap. Document in the record's docstring that consumers
  must HTML-escape the name and the email, and never put them in a mail header or a URL. Tests
  cover each character class.
- Rejecting a name or email (over-long, unverified, missing) currently raises `Rejected`, a 401 that
  says "Sign in again". The client will loop on sign-in. Use a distinct stable 403 code (for example
  `access_profile_unusable`) with no echo.

**T7 MEDIUM: Name and email leak into logs, error bodies or responses (Information disclosure, DAT-7).**
- Already good: the error envelopes are fixed strings, `content_free_log` logs by class only, the
  `Profile` repr hides the name and email, and `AccessStatus` returns `state` only.
- Required: keep `Student` UID-only (never add the email to it). Never return the name, email or
  times in `/v1/access*` bodies. No `print`/`logging` outside `content_free_log`. Grep test or ruff
  rule: no `logging.getLogger(...).info|warning|error` in `cst_accounts`.
- AC7 log-capture test covers **every** path: create, idempotent repeat, denied (`AccessDenied`
  raised inside the transaction), malformed doc (`Unavailable` inside the transaction), store
  failure, unverified email, over-long name, and a 500 from an unexpected exception. Assert the
  synthetic name and email appear in **neither** captured stdout/stderr/logging **nor** any response body.

**T8 MEDIUM: Claim or body spoofing of identity, name, email or state (Spoofing).**
- Already good: name and email come only from the re-verified token (never from
  `X-Apigateway-Api-Userinfo` or the body), `email_verified is True` (strict bool), `google.com`
  only, and an `extra="forbid"` empty body.
- Required tests: `email_verified` as `"true"` (string), `1` or missing is rejected. A missing
  `email` is rejected. A non-string `name` is rejected. A body with `uid`, `email`, `name` or
  `state` returns 400 and writes nothing. A query string returns 400. A token for user B can never
  create or read `access/A` (the store keys only by `profile.uid`). There is no `PUT/PATCH` on
  `/v1/access*` (405).
- The `name` claim is user-mutable through Identity Toolkit `accounts:update`. That needs the API
  key, which stays server-only (ACC-3). Treat it as untrusted anyway (T6).

**T9 MEDIUM: Fail-open on a malformed state or a store error.**
- Already good: `_stored_state` raises `Unavailable` for unknown or non-string states, and the guard
  checks `is not APPROVED`.
- Required tests: the guard returns 503 (not 200, not 403) for a malformed doc and for a store
  exception. `GET /v1/access` returns 503 for a malformed doc. A `denied` re-request returns 403
  `access_denied` and makes no write (assert the write count on the fake transaction). A `pending`
  or `approved` re-request makes no write and never changes state or version. A revoke between two
  requests fails the second (AC4).

## LOW (accepted or noted)
- L1. The guard reads the marker and the access record separately (non-atomic). The window is about
  milliseconds and owner-only. Optionally use one `get_all([marker, access])` for a consistent snapshot and one round trip.
- L2. Concurrent `transaction.create` may surface `AlreadyExists` (409) and map to 503. Catch it
  and re-read, so AC1's concurrent case returns `pending`.
- L3. Any Google account can create a pending record with PII, so the queue can be flooded. DAT-2
  accepts this. #74 must send email only on the create branch and rate-limit (ACC-5).
- L4. Gateway: the new GET/POST must keep the global `firebase` security. Only the `options`
  preflights get `security: []`. The service re-verifies the token anyway.
- L5. #31 has no routes yet, so the gate is absent there. It must reuse the guard and the T1 test before any session route ships.
- L6. Each protected request costs two Firestore reads, plus one rules `get()` per client read. That is within limits. Watch the cost.
- L7. A deletion-pending account gets 403 `account_deletion_pending` on `/v1/access*`. That is consistent and fine.

## Audit (2026-11-24, uncommitted diff against `origin/dev` plus `tests/test_access.py`)

Verdict: **CLEAR, with no blocking findings.** `uv run pytest`: 274 passed, 17 skipped. The skipped
tests are the Firestore emulator tests, and I did not run `infra/rules.test.mjs`, so the lead must
attach that output as evidence. No dependency changes. No secrets or real emails in the diff.

| ID | Status |
|---|---|
| T1 | Closed. The route-inventory test in `tests/test_access.py` uses a closed allow-list, `/v1/me` is gated, and a test proves the gate has no env or setting switch. |
| T2 | Closed. `exists()` plus `get('state','') == 'approved'` inside `activeOwner`. An explicit deny-all `match /access/{uid}`. Rules tests cover missing, malformed, list and other-user reads, owner reads and unauthenticated reads (not run by me). |
| T3 | Closed. The marker is read inside the create transaction (`store.py`), and there is a fake-store race test and an emulator test. |
| T4 | Accepted by the owner and recorded in POLICY §10. |
| T5 | Closed. D1 is reversed and `/v1/me` depends on `approved`. |
| T6 | Mitigated. NFC, controls become spaces, Cf is stripped except ZWJ/ZWNJ, 256 cap, 403 `profile_unusable`. The README carries the escaping contract for #73, #74 and #76. |
| T7 | Closed. A log-capture test covers success, repeat, forged body, denied, not-approved, outage and crash paths, checking logs and bodies. `Profile` has `repr=False` and responses are state-only. |
| T8 | Closed. Strict `email_verified is True`, body/query/forged-header tests and 405 on writes. |
| T9 | Closed. Malformed records and outages give 503. A transaction that exhausts its retries gives 503. Denied requests make no write. |
| L2 | Closed. `AlreadyExists` triggers a re-read. |

Residual findings (all LOW):
- A1 `tests/test_access.py:224,230`: the inventory walks only `APIRoute` and matches the guard by
  `__name__ == "approved"`. A websocket route or mount, or any function named `approved`, would
  slip past. #31's copy should include `APIWebSocketRoute` and compare by identity.
- A2 `store.py:104-106`: after `AlreadyExists`, the re-read returns 200 `{"state":"denied"}` instead
  of 403 `access_denied` if a denial raced in. It writes nothing and still fails closed.
- A3 `firebase.py:29`: the kept ZWJ/ZWNJ characters (and Cyrillic look-alikes) let two names look
  identical in the admin queue. #73 and #76 should show the email as the primary identifier.
- A4 `firebase.py:128`: a name over 256 characters after normalization is permanently
  `profile_unusable`, so that account can never request access. This is fail-closed and a UX issue, not a security one.
