# Development session and grading infrastructure

This module owns the private `session` and `grading` Cloud Run services (#18), their dedicated
identities, the `practice` image repository, and the empty `session-state-signing-key` secret. It
adds no transcript, audio or session store. Encrypted transcript storage with Cloud KMS (owner
decision 2026-11-18; POLICY DAT-1 and ARCHITECTURE §7–§8 as amended in
`docs/decisions/transcript-storage.md`) is a separate follow-up Issue. No real image runs here until
the #72 approval check is deployed (runbook step 3). The shared API
Gateway stays in `infra/accounts` (AD-4). The deploy workflow renders its session routes from the
live `session` URL.

Bootstrap and verify with [the runbook](../../docs/runbooks/session-grading-deploy.md). After
bootstrap, the deploy workflow rolls both images from `sessionImage` and `gradingImage` in
`infra/environments/development.json`, and Terraform ignores image changes. Roll back with
[the CI deploy runbook](../../docs/runbooks/ci-deploy.md#rollback). `cst-deploy` (from
`infra/ci-deploy`) can act as `cst-session` and `cst-grading` to roll a revision; it holds no role
in the table below.

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
and training jobs. It is also a zero-retention control: without `cachedContents.create` or
`batchPredictionJobs.create`, neither service can create a context cache or a batch job. Adding any
permission needs an owner decision and an update to `docs/decisions/vertex-ai-governance.md`.

## Vertex AI models and region (#65)

`local.vertex` in `main.tf` pins the region and the models (OD-2). Each service gets only its own
model:

| Service | Env var | Value |
|---|---|---|
| `session`, `grading` | `CST_VERTEX_LOCATION` | `us`, the multi-region (never `global`) |
| `session` | `CST_PERSONA_MODEL` | `gemini-3.8-flash` |
| `grading` | `CST_GRADER_MODEL` | `gemini-4-argon` |

They are locals, so no tfvars or `-var` flag can change them. Neither model is served on
`us-central1` (HTTP 404), so a Vertex client must call the `us` multi-region host
`https://aiplatform.us.rep.googleapis.com` (ARCHITECTURE §6 exception). The project-wide Vertex
settings that Terraform can't express are applied and checked by the owner with `vertex_governance.py`:
`disable-cache` sets setting 1, `check` reads settings 1–3 (setting 2 counts a 404 only after a control read of the same model succeeds) and `probe` checks the location. It uses the owner's gcloud session and prints only PASS/FAIL lines.
`docs/decisions/vertex-ai-governance.md` lists the steps and holds the evidence.

Checks, offline:

```
python -m unittest discover -s infra/session-grading -p "test_*.py"
terraform -chdir=infra/session-grading init -backend=false   # in a scratch copy if you hold real state
terraform -chdir=infra/session-grading test
```

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
