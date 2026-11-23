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

## Security re-check — 2026-11-20 (d3991e2..401a1c9)
CLEAR. No blocking findings. `token_owner` is used only on the deletion route; provider text can't leak; the 403 adds no enumeration signal beyond what a held credential already grants; pip-audit is clean.

| # | Sev | Finding | Disposition |
|---|---|---|---|
| S11 | LOW | Every USER_DISABLED maps to "deletion pending" (firebase.py:15-29), which assumes deletion is the only path that disables users | **Accepted, documented.** Recorded on #104: any future admin-disable path must check `store.pending(uid)` before using this code. |

## Policy and security re-review — 2026-11-22 (diff origin/dev...b875bdd, 109 files)

Policy reviewer: ESCALATE (six owner items). Security reviewer: no Critical or High, three Medium, one ESCALATE.
Every escalation went to the owner. Their answers are verbatim in build-log.md (2026-11-22, late).

| # | Sev | Finding | Disposition |
|---|---|---|---|
| P1 | ESCALATE | Agent ran the Hosting deploy and runbook steps 2–4 although AG-9/AGT-6 have no exception clause; verification.md called it "the runbook run as written" | **Owner:** dated record `docs/decisions/ag9-one-off-exceptions.md` (PR #118). verification.md #18 AC3 corrected. |
| P2 | ESCALATE | Agent changed #18/#25 ACs and set Human Review to Reviewed, which AGT-4 forbids | **Owner:** AGT-4 amended to allow it only on the owner's explicit, quoted instruction (PR #118). |
| P3 | ESCALATE | Runbook and infra README present encrypted transcript storage as settled while POLICY/ARCHITECTURE forbid it | **Owner:** amend the docs first. `docs/decisions/transcript-storage.md`, DAT-1 to DAT-3 and ARCHITECTURE §6–§8 in PR #118, effective with the owner's SDD change note. |
| P4 | ESCALATE | Firebase Hosting, EAS and the Google Sign-In package have no owner record | **Owner:** approved and recorded in ARCHITECTURE §6/§9 (PR #118). |
| P5 | ESCALATE | `apps/student/AGENTS.md` (Expo template) steers agents to EAS submit and OTA deploys | **Owner:** removed, with the template LICENSE. |
| P6 | ESCALATE | Welcome lacked the ETH-1 statement and the single Continue with Google action (#25) | **Owner:** match #25. Fixed with the shared `SignInPanel` on Welcome and Sign in. |
| P7 | CONCERN | #18 AC2 "(reviewed)" cited a review that had not happened | **Fixed:** this review is the record; verification.md updated. |
| P8 | CONCERN | #18 AC3 "recreatable" ignores console-made resources | **Fixed:** verification.md names the manual steps in `docs/accounts-setup.md`. |
| P9 | CONCERN | #25 AC5 has no live log check | **Narrowed:** verification.md says the check is automated only. |
| P10 | CONCERN | verification.md had no row per criterion | **Fixed:** one row per AC. |
| P11 | CONCERN | PR body stale | **Fixed** on d3f1f6f. |
| P12 | CONCERN | `/v1/scores` drops the completion time and crisis result and does not order newest first (REP-4/REP-5) | **Deferred → #40** (comment added). Outside these ACs. |
| P13 | CONCERN | `cstAccounts` holds project-wide create/update (= S1) | **Deferred → #104**, before the release gate. |
| P14 | CONCERN | DAT-2 does not name the deletion marker | **Owner:** DAT-2 amended (PR #118). |
| P15 | CONCERN | Owner's other project names in docs/accounts-setup.md (public repo) | **Fixed** in the file. They remain in this branch's commit history; a squash merge keeps them out of dev. |
| P16 | CONCERN | Vertex invoke granted before OD-2/#65 | Same as S13. |
| P17 | CONCERN | No recorded actor for the 2026-10-22 deploys | **Open for the owner.** Not re-established in this run. |
| P18 | CONCERN | #18 AC1 proven on the placeholder image | **Accepted:** runbook requires all 11 checks again after #31. |
| S12 | MEDIUM | `cstGrading` has project-wide `datastore.entities.create`, so a grading bug could write `account_deletions/{uid}` and the worker would delete that student | **Deferred → #104** (comment added); runbook step 3 says to resolve it before a real grading image. Dormant on the placeholder. |
| S13 | MEDIUM | Session routes accept any Google account until #72; a real #31 image would break ACC-4/ACC-7 | **Owner:** block #31 on #72. Native blocker added; runbook step 3 hard precondition. |
| S14 | MEDIUM | `cstAccounts` create/update (known S1) | **Deferred → #104.** |
| S15 | LOW | The `hello` placeholder runs as the real identities, so it could read the signing key and call Vertex through the metadata server | **Accepted for development:** Google's image, pinned by digest, until #31. |
| S16 | LOW | `cstVertexInvoke` allows any Vertex model, including ones with no zero-retention record | **Deferred → OD-2/#65.** |
| S17 | LOW | Firebase Hosting sends no Content-Security-Policy; web tokens live in JS memory | **Deferred → #104** (comment added). |
| S18 | LOW | `/v1/auth/google` and `/v1/auth/refresh` have no abuse control | **Known launch gate** (infra/accounts README). Before real students. |
| S19 | LOW | `erase_scores` would leave the #72 access record and any later subcollection | **Deferred → #72** (comment added): #72 extends the erase and tests it. |
| S20 | LOW | Identity Platform provider config is not in Terraform; a Firebase web app may have an auto-created browser key | **Deferred → #104** (comment added). |
| S21 | LOW | One malformed score document makes `/v1/scores` return 500 and the traceback logs its values | **Deferred → #40** (comment added): skip and count invalid records. |
| S22 | LOW | `python:3.12-slim` base pinned by tag, not digest | **Deferred → #104** (comment added). |
| S23 | LOW | 20 moderate npm audit entries under Expo build tooling | **Tracked in #61.** |

Known items rechecked and still as recorded: S6, S7, S11.
