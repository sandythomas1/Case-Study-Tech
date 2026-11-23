# Development session and grading infrastructure

This module owns the private `session` and `grading` Cloud Run services (#18), their dedicated
identities, the `practice` image repository, and the empty `session-state-signing-key` secret. It
adds no transcript, audio or session store. Encrypted transcript storage with Cloud KMS (owner
decision 2026-11-18; POLICY DAT-1 and ARCHITECTURE §7–§8 as amended in
`docs/decisions/transcript-storage.md`) is a separate follow-up Issue. No real image runs here until
the #72 approval check is deployed (runbook step 3). The shared API
Gateway stays in `infra/accounts` (AD-4) and renders the session routes from this module's
`session_service_url` output.

Deploy, verify and roll back with [the runbook](../../docs/runbooks/session-grading-deploy.md).

## IAM

| Identity | Holds | Scope |
|---|---|---|
| `cst-gateway` (from `infra/accounts`) | `roles/run.invoker` | `session` service only |
| `cst-session` | `roles/run.invoker` | `grading` service only (authoritative binding) |
| `cst-session` | `roles/secretmanager.secretAccessor` | `session-state-signing-key` secret only |
| `cst-session` | `cstSessionIdentity`: `firebaseauth.users.get`, `datastore.databases.get`, `datastore.entities.get` | Project |
| `cst-grading` | `cstGrading`: `datastore.databases.get`, `datastore.entities.get`, `datastore.entities.create` | Project |
| `cst-session`, `cst-grading` | `cstVertexInvoke`: `aiplatform.endpoints.predict` | Project |
| `cst-build` (from `infra/accounts`) | `roles/artifactregistry.writer` | `practice` repository only |

No primitive role, no `allUsers` invoker, no downloaded key. The session's read-only identity role
exists because every service repeats the accounts identity check (ARCHITECTURE flow 2): revocation,
deletion marker and access record.

**Firestore IAM cannot be scoped to a collection or document path.** `datastore.*` permissions apply
to the whole database. `cst-grading` can create a document anywhere, and both identities can
point-read any document whose path it knows. Neither can list, update or delete. Grading has `get`
so #40 can read the deletion marker inside the score-write transaction and avoid writing a score
for a deleted account. The path limits
(`students/{uid}/scores/{scoreId}` for grading; `account_deletions/{uid}` and the access record for
session) are enforced in service code and tests, not IAM. Server SDK calls bypass
`infra/firestore.rules`. Grading must use `create()`, which also keeps a retried write from
overwriting a score.

`cstVertexInvoke` replaces `roles/aiplatform.user`, which also manages datasets, models, endpoints
and training jobs. If OD-2 picks a feature that needs more (for example context caching), add
exactly that permission.

## Timeouts (AD-3)

The end-session request waits for grading, so the timeouts nest and the innermost fires first:
grading Cloud Run 120 s < session's call to grading 130 s (`CST_GRADING_TIMEOUT_SECONDS`) < session
Cloud Run 180 s < gateway `deadline` 190 s on `POST /v1/sessions/end`. Turns get a 30 s gateway
deadline; every other route keeps the 15 s gateway default. Change the `locals` in `main.tf` and
`infra/gateway.yaml.template` together.

## Logging

Cloud Run request logs and API Gateway logs record method, path, status and latency, never request
bodies, and this module enables nothing that would add them. Route paths carry no session content.
Application logs must go through the content-free helper (#63).
