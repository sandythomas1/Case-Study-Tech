# Review: Owner approval gate (#72)

Review depth: Deep (Issue field). Reviewers: security-reviewer (threat model and audit), policy-reviewer and qa-tester (verification.md).
Blocking findings open: **none**. No ESCALATE.

## Threat model (before code): BLOCKING, then resolved
The threat model and the audit are in threat-model.md.

| ID | Sev | Finding | Disposition |
|---|---|---|---|
| T1 | HIGH | A route could skip the guard | Fixed. test_access.py walks the route table and fails on an unguarded route. |
| T2 | HIGH | The rules could admit a missing or malformed record | Fixed. `exists()` plus `state == 'approved'`, and a deny-all `access/{uid}` match. The rules matrix covers 8 bad states. A mutation check removed `approved(uid)` and AC5 failed. |
| T3 | MED | A request could outlive a deletion (TOCTOU) | Fixed. The deletion marker is read inside the create transaction. |
| T4 | MED | Deletion clears a denial | Accepted by the owner: "Accept and record (Recommended)". Recorded in POLICY §10. #74 rate-limits the emails. |
| T5 | MED | `/v1/me` leaked identity before approval | Owner: "Gate /v1/me (Recommended)". `/v1/me` is now guarded. |
| T6 | MED | Display name injection or spoofing | Fixed. NFC, controls folded to spaces, Cf stripped (except ZWJ/ZWNJ), 256-character cap. Email must be verified and printable, otherwise 403 `profile_unusable`. |
| T7–T9 | LOW | Create race, other HTTP methods, log content | Fixed. AlreadyExists is re-read, other methods return 405, and a log-capture test checks every path. |

## Audit (after code): CLEAR
| Sev | Finding | Disposition |
|---|---|---|
| LOW | The route test matched the guard by name and walked HTTP routes only | Fixed. Matches by identity through `app.state.approval_guard`, checks websocket routes, and fails on any mount or raw route. |
| LOW | A racing request that finds a denial returned 200 `denied` | Fixed. It now raises `AccessDenied` (403). Unit test added. |
| LOW | A name can imitate another person's with look-alike letters | Accepted for the MVP. README tells #73 and #76 to show the verified email first. |
| LOW | A name over 256 characters makes the profile unusable | Accepted. It fails closed. Noted in the README. |

## Policy review: no blocking findings, no ESCALATE
| Finding | Disposition |
|---|---|
| AGT-3: the Issue lacks a record of T4 and T5 | The progress comment and the PR body quote both. |
| Gating `/v1/me` breaks app sign-in for every unapproved dev account | README and PR tell the owner to seed approved records for the synthetic dev accounts before the next deploy. |
| DAT-2 and ARCH §7 don't name `version` | Deferred to the next docs pass. It isn't personal data, and the Issue requires it. |
| ACC-6 text doesn't point to the §10 exception | Optional, left as is. The §10 row is the record. |

## Found by the lead during the build
- A transaction that exhausted its retries under contention returned 500. It now returns 503 (`storage_operation`), with a test.
- An emulator test (#46) used a fixed UID, so it failed when rerun against a long-lived emulator. It now uses a fresh UID.

## QA findings
| Sev | Finding | Disposition |
|---|---|---|
| MED | D1: concurrent requests could return 503, and the AC1 concurrency test was flaky (about 45% of runs) | Fixed. Racing transactions deadlocked on the missing document. The transaction now reads only the deletion marker before the create. A racer that loses reports what the winner wrote. 16-way test with a fresh UID: 15 of 15 runs passed. |
| LOW | D2: the #46 emulator test used a fixed UID | Fixed. It uses a fresh UID. |
