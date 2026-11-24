# Spec: Owner approval gate (#72)

> **Phase:** Specify · **Status:** clarified · **Owner:** sandythomas1 · **Date:** 2026-11-24
> Source of truth for the task is GitHub Issue #72. This file restates it for the build team and
> records how its open details were settled. If the two disagree, the Issue wins (POLICY AGT-1).

## Problem

The MVP is invite-only (owner, 2026-10-31; plan PA-12). Today any Google account that signs in can
read its own scores. Nothing on the server stops an account the owner never approved. The admin
queue (#73), the owner email (#74) and the access-state screens (#75) all need a server-side access
record and gate to build on, and the session service (#31) must not start sessions for unapproved
accounts.

## Goals

- An account reaches no protected data until its access record says `approved`.
- The gate is enforced by the API and by the Firestore rules, not only by the UI (ACC-7).
- A deny or revoke applies on the very next request, and a failed check fails closed.

## Non-Goals

- Listing or deciding requests (#73). Sending email (#74). Any screen (#75, #76).
- Changes to `services/session`. It has no HTTP routes yet. #31 adopts this gate for its routes.
- A tool that approves accounts. Until #73, the owner sets a synthetic test account's record by hand.

## Functional Requirements

1. FR-1. Access states are `missing`, `pending`, `approved` and `denied`. A revoked account is
   `denied`. They are modelled in `services/accounts/cst_accounts/domain.py`.
2. FR-2. `GET /v1/access` returns only the caller's own state. Identity comes from the verified
   token, never from a client-supplied UID, name, email or state.
3. FR-3. `POST /v1/access/request` creates at most one request per account, idempotently, including
   under concurrent calls. The display name and Google email come from the verified token. The body
   accepts no fields. A `denied` account's request is rejected with a stable code and creates
   nothing.
4. FR-4. The access record holds only: display name, Google email, state, request time, decision
   time and a version for optimistic concurrency. It lives in the server-only `access/{uid}`
   collection. No client can read or write it.
5. FR-5. Every protected route rejects an account that is not `approved` with the stable code
   `access_not_approved`. Reachable without approval: sign-in and refresh, access state, request
   access, and account deletion. Sign-out is client-side. `GET /v1/me` is protected (owner, T5).
6. FR-6. Approval is read from the store on every protected request, with no positive cache. A
   failed or malformed read is rejected (503), never treated as approved.
7. FR-7. Firestore rules let a student read their own scores only while `access/{uid}` has state
   `approved`. Unapproved, denied and missing accounts read nothing. Clients write nothing.
8. FR-8. Account deletion (#46) deletes the access record in the same cleanup that erases the scores.
9. FR-9. Logs never carry the name, email, token or a UID-to-email mapping (DAT-7). All logging goes
   through `content_free_log.py`.
10. FR-10. The same gate runs in every environment (ACC-9). Tests use synthetic, pre-approved accounts.
11. FR-11. The API Gateway config exposes the two new routes, with their CORS preflights.

## Acceptance Criteria (from #72, verbatim in substance)

- [ ] AC1. Unit tests: a first request creates one `pending` record; a repeated or concurrent request
  leaves exactly one record; a `denied` account's request is rejected and creates nothing.
- [ ] AC2. Unit tests: the identity guard rejects `missing`, `pending` and `denied` accounts on a
  protected route and admits an `approved` one; a store failure during the check is rejected.
- [ ] AC3. Unit test: a forged UID, name, email or state in the request body has no effect.
- [ ] AC4. Unit test: a revoke between two requests makes the second request fail.
- [ ] AC5. Firestore emulator tests: an unapproved owner cannot read their scores; an approved owner
  can; another user cannot read either; no client can write the access record.
- [ ] AC6. Deletion test: after cleanup, the access record is gone along with the scores.
- [ ] AC7. A log-capture test shows no name or email in logs on success or error paths.

## Decisions settled by the lead (L1, recorded for review)

- D1. Reversed by the owner on 2026-11-24 (T5: "Gate /v1/me (Recommended)"). `GET /v1/me` is a
  protected route. Until #75 changes sign-in to check `GET /v1/access` first, a pending account
  can't finish sign-in in the app. No real students are enabled.
- D2. One stable rejection code, `access_not_approved` (HTTP 403), for missing, pending and denied
  accounts. The client reads the exact state from `GET /v1/access`. A denied request gets
  `access_denied` (HTTP 403).
- D3. Name and email come from the verified ID token's `name` and `email` claims. The email must be
  present and verified. A missing name is stored as an empty string.

## References

- Issue #72 and its 2026-11-22 comments (deletion must cover the record; #72 blocks #31).
- `docs/POLICY.md` ACC-4…ACC-9, DAT-2, DAT-3, DAT-7, AGT-1. Plan PA-12, AG-1, AG-2, AG-6, AG-7.
- `docs/ARCHITECTURE.md` (accounts service, Firestore rules).

## Owner decisions during the build

- T4 (2026-11-24): "Accept and record (Recommended)". Deleting an account erases its denial, so the
  account can request again. Recorded in POLICY §10. #74 rate-limits its emails.
- T5 (2026-11-24): "Gate /v1/me (Recommended)". See D1.
