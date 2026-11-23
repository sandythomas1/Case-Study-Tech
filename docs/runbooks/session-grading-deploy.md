# Session and grading deployment runbook (development)

Deploys the private `session` and `grading` Cloud Run services from `infra/session-grading/` and
adds the session routes to the shared gateway in `infra/accounts/` (#18). A human runs every
`plan`/`apply` and every cloud command below (plan AG-9). Agents never do. The 2026-11-22 first
run of steps 2–4 by an agent was a one-off owner exception that does not carry forward
(`docs/decisions/ag9-one-off-exceptions.md`).

Project `casestudy-tech-dev-2e03d0`, region `us-central1`, synthetic data only (AD-5). Commands run
from the repository root in PowerShell. They set no gcloud defaults.

What this deploys: two private services running the Cloud Run `hello` placeholder until #31 and
Phase 5 build real images, two service identities and three custom roles, the `practice` image
repository and the `session-state-signing-key` secret. It stores no transcript, audio or session
state.

Encrypted transcript storage (owner decision 2026-11-18; POLICY DAT-1 and ARCHITECTURE §7–§8 as
amended in `docs/decisions/transcript-storage.md`) is a follow-up Issue and is not built here: app-layer
Cloud KMS, where the grader encrypts and the accounts service decrypts.

## Prerequisites

- Terraform 1.9+, gcloud authenticated as a project Owner, Python 3.12 and `curl.exe`.
- `infra/accounts` is applied, so `cst-gateway`, `cst-build` and the gateway
  `https://accounts-7tnmor5w.uc.gateway.dev` exist. This module reads the two identities as data
  sources and fails at plan time without them.
- The private state bucket `gs://casestudy-tech-dev-2e03d0-tfstate` exists (`infra/accounts/README.md` step 1).
- No `.tfvars` file is needed. Every input has a safe default or goes on the command line, and no
  input is a secret.

## 1. Initialize

```powershell
$env:GOOGLE_OAUTH_ACCESS_TOKEN = (gcloud.cmd auth print-access-token --project=casestudy-tech-dev-2e03d0 --quiet) -join ''
terraform -chdir=infra/session-grading init -backend-config=bucket=casestudy-tech-dev-2e03d0-tfstate -backend-config=prefix=session-grading/development
```

Do not echo the token. The state prefix is separate from `accounts/development`.

## 2. Bootstrap identities and the empty secret (first time only)

Cloud Run will not start a revision whose secret has no version, so this runs in two stages, as the
accounts module does. Inspect the saved plan before applying it.

Quote every `-out=`, `-target=` and `-var=` argument. Windows PowerShell 5.1 splits an unquoted
`-name=value` at a dot before passing it on (`-out=bootstrap.tfplan` arrives as `-out=bootstrap` and
`.tfplan`), and Terraform stops with "Too many command line arguments".

A targeted plan still needs both image variables (step 3 explains the digest pin). Without them,
Terraform stops at an `Enter a value:` prompt and holds the state lock until that process exits.

```powershell
$hello = "us-docker.pkg.dev/cloudrun/container/hello@" + (gcloud.cmd artifacts docker images describe us-docker.pkg.dev/cloudrun/container/hello:latest --format="value(image_summary.digest)")
terraform -chdir=infra/session-grading plan "-out=bootstrap.tfplan" "-var=session_image=$hello" "-var=grading_image=$hello" `
  "-target=google_project_service.required" "-target=google_service_account.identity" `
  "-target=google_project_iam_custom_role.vertex_invoke" "-target=google_project_iam_custom_role.session" `
  "-target=google_project_iam_custom_role.grading" "-target=google_project_iam_member.vertex" `
  "-target=google_project_iam_member.runtime" "-target=google_artifact_registry_repository.practice" `
  "-target=google_artifact_registry_repository_iam_member.build" `
  "-target=google_secret_manager_secret.state_signing" "-target=google_secret_manager_secret_iam_binding.session"
terraform -chdir=infra/session-grading apply bootstrap.tfplan
python infra/session-grading/bootstrap_signing_key.py
```

The script generates a 256-bit key in memory and adds it as a secret version. It prints only the
version number. Run it again only to rotate the key (see Rollback).

## 3. Deploy both services

Both image variables have no default and must end in `@sha256:<64 hex>`. Terraform rejects
tags. Until #31 and Phase 5 ship, pin the public placeholder by digest with this read-only lookup.
Leave `inject_state_signing_key` at its default of `false`, so the signing key never reaches a
third-party image.

```powershell
terraform -chdir=infra/session-grading plan "-out=services.tfplan" "-var=session_image=$hello" "-var=grading_image=$hello"
terraform -chdir=infra/session-grading apply services.tfplan
$sessionUrl = terraform -chdir=infra/session-grading output -raw session_service_url
$gradingUrl = terraform -chdir=infra/session-grading output -raw grading_service_url
```

The image variables seed the first deploy only. Terraform ignores later image changes, because
the deploy workflow owns the running images (#105, `docs/runbooks/ci-deploy.md`). To run a reviewed
image from `us-central1-docker.pkg.dev/casestudy-tech-dev-2e03d0/practice`, change `sessionImage` or
`gradingImage` in `infra/environments/development.json` in a pull request; the next `staging`
deploy rolls it. Until the hard precondition below is met, the deploy validator accepts only the
placeholder, and that pull request also relaxes `scripts/ci/deploy/deploy_config.py`. Every plan
must still pass valid image variables, or it fails validation. Add
`-var=inject_state_signing_key=true` only with the reviewed #31 session image already running.

**Hard precondition for any real image or `inject_state_signing_key=true`:** the #72 approval check
is deployed in the accounts service, the session service and the Firestore rules. Until then, deploy
only the digest-pinned `hello` placeholder, because without #72 an unapproved account could start
sessions. Stop and ask the owner if #72 is not deployed. Separately, before a real grading image
runs, resolve security review S12 (#104): grading's project-wide create permission could also write
deletion markers.

## 4. Add the session routes to the gateway

The first CI deploy adds them (`docs/runbooks/ci-deploy.md`). It renders
`infra/gateway.yaml.template` with the live `session` URL and rolls a new gateway config. Terraform
no longer can: its gateway config is the bootstrap config, and it ignores template changes (#105).
So apply `infra/ci-deploy`, create the GitHub environments, and merge into `staging`. A new gateway
config can take several minutes to serve; the deploy's health check waits for it.

## 5. Verify private access

Never paste a token into a command line, a log or an Issue. Each check prints only a status code.

```powershell
$gw = "https://accounts-7tnmor5w.uc.gateway.dev"
function Get-Status($uri, $method = "GET", $headers = @()) {
  curl.exe -s -o NUL -w "%{http_code}" -X $method @headers $uri
}
```

| # | Check | Command | Expect |
|---|---|---|---|
| 1 | Session refuses unauthenticated callers | `Get-Status "$sessionUrl/health"` | 403 |
| 2 | Grading refuses unauthenticated callers | `Get-Status "$gradingUrl/health"` | 403 |
| 3 | The gateway reaches session | `Get-Status "$gw/v1/sessions/health"` | 200 |
| 4 | Protected session routes need a Firebase JWT | `Get-Status "$gw/v1/sessions/end" "POST" @("-H","Content-Type: application/json","--data","{}")` and `Get-Status "$gw/v1/sessions/turns" "POST" @("-H","Content-Type: application/json","--data","{}","-H","Authorization: Bearer invalid")` | 401, 401. A POST with no body gets 411 from Google's front end before the JWT check runs. |
| 5 | The gateway has no route to grading | `Get-Status "$gw/v1/grading/health"` | 404 |
| 6 | Grading's only invoker is the session identity | `gcloud.cmd run services get-iam-policy grading --region=us-central1 --project=casestudy-tech-dev-2e03d0` | one `roles/run.invoker` binding, member `cst-session@...` only |
| 7 | Session's only invoker is the gateway identity | `gcloud.cmd run services get-iam-policy session --region=us-central1 --project=casestudy-tech-dev-2e03d0` | one `roles/run.invoker` binding, member `cst-gateway@...` only |
| 8 | The gateway holds no project role that could invoke grading | `gcloud.cmd projects get-iam-policy casestudy-tech-dev-2e03d0 --flatten="bindings[].members" --filter="bindings.members:cst-gateway@" --format="value(bindings.role)"` | empty |
| 9 | Grading is healthy | `$t = gcloud.cmd auth print-identity-token; Get-Status "$gradingUrl/health" "GET" @("-H","Authorization: Bearer $t"); Remove-Variable t` | 200 (project Owner includes `run.routes.invoke`) |
| 10 | Runtime roles are the custom ones | `gcloud.cmd projects get-iam-policy casestudy-tech-dev-2e03d0 --flatten="bindings[].members" --filter="bindings.members:(cst-session@ OR cst-grading@)" --format="table(bindings.role,bindings.members)"` | only `cstSessionIdentity`, `cstGrading` and `cstVertexInvoke`; no Owner, Editor or Viewer |
| 11 | Only the session identity reads the signing key | `gcloud.cmd secrets get-iam-policy session-state-signing-key --project=casestudy-tech-dev-2e03d0` | `secretAccessor` for `cst-session@...` only |

Checks 6 to 8 together prove that the session identity can reach grading and the gateway cannot.
Two runtime proofs wait for real code. A session-to-grading call needs the session image that ships
the grader client (#66 and Phase 5), and you exercise it with a synthetic end-session request. The
placeholder cannot make that call. Checks 3 and 9 hit the placeholder too, so rerun all eleven
checks after the first real image deploy. That rerun covers #18's health-through-gateway criterion
for session. Grading has no gateway route by design (AD-3), so check 9 is its health check.

Finish with a full `terraform plan` in both modules. Each must report no changes.

## Rollback

- **Gateway routes or a bad image:** follow [the CI deploy runbook](ci-deploy.md#rollback).
  Terraform no longer changes the running image or the served gateway config. Rerun the checks
  afterwards.
- **Signing key:** rotation invalidates every signed state in flight. Those sessions take the
  lost-content path (ARCHITECTURE flow 8). To rotate, run `bootstrap_signing_key.py`, then roll a
  new session revision, because Cloud Run resolves `latest` when an instance starts:
  `gcloud.cmd run services update session --update-labels=key-rotation=YYYYMMDD --region=us-central1 --project=casestudy-tech-dev-2e03d0`.
  A deploy will not do it, because it rolls only a changed image. The next `infra/session-grading`
  plan shows that label's removal; apply it or leave it. Disable the old
  version once the longest session time limit has passed.
- **Removing the services:** both services have `deletion_protection = true`. Set it to false in a
  reviewed change and apply that first, then destroy. A deleted custom role ID can't be reused for
  weeks, so leave the roles in place unless they are truly retired.
- Never make Cloud Run public, or add the gateway as a grading invoker, to work around an access
  failure.
