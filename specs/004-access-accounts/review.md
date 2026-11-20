# Review — 004-access-accounts (PR #62)

## Security audit — 2026-11-20 (diff origin/dev...d3991e2)
Blocking: **none** (0 CRITICAL / 0 HIGH). Runtime npm audit: 0 high / 20 moderate, identical to dev, all in build and test tooling.

| # | Sev | Finding | Disposition |
|---|---|---|---|
| S1 | MEDIUM | The `cst-accounts` runtime role holds `firebaseauth.users.update` and project-wide `datastore.entities.create/update` (infra/accounts/main.tf:41-65) | **Deferred → #104.** Fixing it means changing IAM and moving revocation to the deletion worker, then a live apply and test against the deployed dev environment. A Terraform edit without the apply would leave the live environment out of step with the code. There are no real students yet; this must land before launch. |
| S2 | LOW | Retrying a deletion request after a lost 202 returns 403 and the student stays signed in (api.py:84-129) | **Fixed** (round 1), because it directly affects R5. |
| S3 | LOW | Sign-out clears only the device; refresh tokens aren't revoked on the server | **Accepted for the MVP, documented.** Server-side revocation would sign the student out on every device, and deletion already disables and revokes. Revisit with the abuse-controls launch gate. |
| S4 | LOW | No nonce on the Google credential exchange | **Deferred → #104.** Needs nonce support on GIS, native, and signInWithIdp; low odds (audience pinned, TLS). |
| S5 | LOW | The API key is sent as the `?key=` query parameter (firebase.py:56) | **Fixed** (round 1) by sending it in the `X-Goog-Api-Key` header. |
| S6 | LOW | The deletion job receives the identity API-key secret it doesn't use | **Deferred → #104** (IAM and secret binding, needs an apply). |
| S7 | LOW | `key_string` is stored in Terraform state and in local plan files | **Deferred → #104.** Delete local `*.tfplan` files after apply. |
| S8 | LOW | Direct Firestore score reads bypass the API's field allowlist | **Deferred → noted on the grading Issue.** Score documents must keep to allowlisted fields. |
| S9 | LOW | The heading assertion in infra/accounts/test_web_routes.py is stale after the #71 merge | **Fix in this PR.** |
| S10 | LOW | pyasn1 0.6.4 and opentelemetry-api 1.45.1 CVEs (not reachable) | **Fixed** (round 1) by bumping and regenerating the hashes. |

## UX and language review — 2026-11-20 (screenshots in screenshots/)
Answer to the domain question, from the code: while deletion is pending, sign-in is **blocked** (the exchange, refresh, `/me` and `/scores` calls return 403 `account_deletion_pending`; a disabled user at sign-in or refresh gets the same code). There is no cancellation path, so "This can't be undone" is true. There is no restriction on which Google accounts may sign in beyond the google.com provider check.

| # | Level | Finding | Disposition |
|---|---|---|---|
| U1 | BLOCKING | An expired sign-in during deletion lands on Sign-in with no message; a 401 from the deletion call keeps an unwinnable retry | **Fixed** (round 2). sign out with the notice "Your sign-in expired, so your account was not deleted. Sign in again to request deletion." Other expiries show "Your sign-in expired. Please sign in again." A 401 from the deletion call itself gets: "We couldn't confirm your deletion request because your sign-in ended. If you can still sign in, please request deletion again." |
| U2 | BLOCKING | The post-deletion confirmation uses the red alert style | **Fixed** (round 2). Fix: a neutral NoticeText (polite live region, announced on mount) with the reviewer's text |
| U3 | SHOULD-FIX | The preview notice calls Account and deletion "planned" | **Fixed** (round 2). Fix with the reviewer's text |
| U4 | SHOULD-FIX | The dialog doesn't say the deletion can't be undone; generic button verb | **Fixed** (round 2). Fix: "This can't be undone. You'll be signed out right away." / "Delete my account" |
| U5 | SHOULD-FIX | The "not available yet" message is unstyled | **Fixed** (round 2). Fix: AlertText, "isn't available right now" |
| U6 | SHOULD-FIX | Dialog focus may land on the destructive button | **Fixed** (round 2). Fix: focus Cancel on open, return focus on close, give the dialog an accessible name |
| U7 | SHOULD-FIX | The native Google button is about 36dp | **Fixed** (round 2). Fix: ActionButton labeled "Continue with Google" |
| U8 | SHOULD-FIX | The deletion failure message is vague and in the wrong order | **Fixed** (round 2). Fix with the reviewer's text, placed below the body |
| U9–U11, U15 | NIT | Sign-in and Welcome copy; busy-state announcement | **Fixed** (round 2). Fix (cheap) |
| U12 | NIT | "Checking your sign-in…" | No change |
| U13 | NIT | No context after a deep-link redirect | Deferred; needs redirect-origin tracking. Low value for the preview. |
| U14 | NIT | The GIS button is 40px and Google-controlled | Accepted deviation: Google's branded control, meets WCAG 2.1 AA |
| U16 (Lead) | SHOULD-FIX | A sign-in attempt on an account with pending deletion shows the generic failure | **Fixed** (round 2). Fix: map the 403 pending to "This account is being deleted, so you can't sign in to it." |
| U17 | NIT | There is no domain glossary (docs/domain.md) | Deferred; outside this feature |
