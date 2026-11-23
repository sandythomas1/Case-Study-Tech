# One-off exceptions to AG-9 (no agent deploys)

**Status:** Owner record, 2026-11-22. **AG-9 and POLICY AGT-6 stand unchanged.** Each exception below
covered one named action, once, in the development project `casestudy-tech-dev-2e03d0` with synthetic
data. None of them carries forward or sets a precedent. Every later deploy or apply is run by a human.

| Date | Owner's words (AskUserQuestion) | What the agent ran | Limits | Record |
|---|---|---|---|---|
| 2026-11-22 | "Authorize me for this deploy" | One Firebase Hosting deploy of the student web build, so real Google sign-in could be tested from the only origin the OAuth client and API allow | Hosting only. No infra apply and no other deploy | `specs/004-access-accounts/build-log.md`, PR #62 |
| 2026-11-22 | "Authorize me, one-off (Recommended)" | `docs/runbooks/session-grading-deploy.md` steps 2–4: identities, roles, image repository and an empty secret; the signing key; both services on the digest-pinned `hello` placeholder; the gateway's session routes | Each saved plan was applied only if it created and updated exactly what was expected and destroyed nothing; anything else stopped for the owner. The owner ran the state-lock `force-unlock` themselves | `specs/004-access-accounts/verification.md`, PR #62 |

## Why record it

Reviewers found these runs while checking PR #62 against AG-9. Recording them keeps the
guardrail's history honest. An unrecorded exception would read as a precedent, and a quietly
corrected log would hide what happened. Production is never eligible for an exception (POLICY AGT-6).
