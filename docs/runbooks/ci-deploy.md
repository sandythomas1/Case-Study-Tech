# CI deploy runbook (#105)

`.github/workflows/deploy.yml` rolls the Cloud Run services and the gateway config from GitHub
Actions. It signs in with Workload Identity Federation, so no Google Cloud key exists anywhere.
This runbook covers the owner's one-time setup, what a deploy does, how to roll back and how to
test the rollback once.

Only the owner merges into `staging` and `main` (Rulesets, POLICY AGT-6). That merge is the
approval for a development deploy (owner decision 2026-11-22, plan AG-9). No agent merges into
those branches or runs any cloud command below. Re-running a Deploy run cannot deploy: the
provider issues a token only to a run's first attempt.

Project `casestudy-tech-dev-2e03d0`, region `us-central1`, synthetic data only (AD-5). Commands run
from the repository root in PowerShell and set no gcloud defaults.

## When it runs

| Push to | Job | What happens |
|---|---|---|
| `staging` | Deploy to development | Runs at once. The merge was the approval. |
| `main` | Deploy to production | Waits for the owner's approval on the `production` environment. Until #77 creates the production project, an approved run deploys nothing and says so in its summary. |

Pushes to the same branch queue. A deploy that has started is never cancelled halfway.

## What a development deploy does

1. **Validates `infra/environments/development.json`** (`scripts/ci/deploy/deploy_config.py`).
   A malformed project, provider, URL or image stops the run before it signs in. Session and
   grading images must be the digest-pinned Cloud Run `hello` placeholder until #72 and S12
   (#104) are cleared (see below).
2. **Signs in** as `cst-deploy` with a short-lived token. The provider accepts only the first
   attempt of a `push` to `refs/heads/staging` in this repository (by numeric ID), running
   `.github/workflows/deploy.yml` in the `development` environment.
3. **Builds the accounts image** from `services/accounts` and pushes it as
   `…/accounts/accounts:src-<git tree of services/accounts>`. If that tag already exists, it reuses
   the image, so unchanged source is never rebuilt. The CI gate already ran the accounts tests on
   the pull request that reached `staging`.
4. **Rolls the services**, callee first: `grading`, `session`, `accounts`, then the
   `account-deletion` job. A service gets a new revision only when its image differs from the
   target. Each service then sends 100% of traffic to its newest revision.
5. **Rolls the gateway config** only when the rendered `infra/gateway.yaml.template` differs from
   the config the gateway serves (`scripts/ci/deploy/gateway_config.py`). The new config is named
   `accounts-ci-<first 12 hex of its sha256>`, uses the `cst-gateway` backend identity, and is
   reused if a re-run renders the same content.
6. **Checks health** (`scripts/ci/deploy/check_health.py`): each service is Ready, runs exactly the
   target image and serves all traffic from its newest revision. Then gateway `/health` and
   `/v1/sessions/health` must return 200, and each service's own run.app URL must refuse an
   anonymous caller with 403, so the deploy made none of them public. The HTTP
   checks retry for up to 2.5 minutes while a new gateway config starts serving. The job summary
   lists status codes and revision names only.

## Who owns what

CI now owns the running images and the served gateway config. Terraform still owns everything
else: services' settings, environment, secrets, scaling, IAM, the job's schedule and the gateway
itself.

| Setting | Owner after the first deploy | Terraform setting |
|---|---|---|
| accounts service and `account-deletion` job image | CI (`services/accounts` on `staging`) | `ignore_changes` on the image and the gcloud client annotations |
| `session` and `grading` image | CI (`sessionImage`, `gradingImage` in `development.json`) | same |
| Served gateway config | CI (`infra/gateway.yaml.template`) | the api_config ignores `openapi_documents`; the gateway ignores `api_config` |

So `-var=image` (accounts), `-var=session_image`, `-var=grading_image` and
`-var=session_service_url` only seed a new environment. They still need valid values, but a plan
never changes a running image or the served gateway config. A change to the gateway template
reaches the gateway on the next deploy, not through `terraform apply`.

**Before `sessionImage` or `gradingImage` points at a real image:** the preconditions in
`docs/runbooks/session-grading-deploy.md` step 3 still apply. #72's approval check must be deployed
and security finding S12 (#104) resolved first. Until then the validator rejects anything but the
placeholder (owner decision 2026-11-22). The pull request that ships a real image relaxes it in
`scripts/ci/deploy/deploy_config.py`, which CODEOWNERS sends to the owner, and says how both
preconditions are met.

## One-time owner setup

### 1. Apply the deploy identity

```powershell
$env:GOOGLE_OAUTH_ACCESS_TOKEN = (gcloud.cmd auth print-access-token --project=casestudy-tech-dev-2e03d0 --quiet) -join ''
terraform -chdir=infra/ci-deploy init -backend-config=bucket=casestudy-tech-dev-2e03d0-tfstate -backend-config=prefix=ci-deploy/development
terraform -chdir=infra/ci-deploy plan "-out=ci-deploy.tfplan"
terraform -chdir=infra/ci-deploy apply ci-deploy.tfplan
terraform -chdir=infra/ci-deploy output
```

The plan should create the STS API enablement, the `github` pool and its `case-study-tech`
provider, the `cst-deploy` account, the `cstDeploy` custom role and these bindings:

| Binding | Scope |
|---|---|
| `roles/iam.workloadIdentityUser` | `cst-deploy`, for subject `repo:sandythomas1@145699956/Case-Study-Tech@1382155772:environment:development` only (GitHub's immutable subject format, #124) |
| `cstDeploy` (get and update services and jobs, read revisions and operations) | project |
| `roles/apigateway.admin` (owner decision 2026-11-22) | project |
| `roles/artifactregistry.writer` | the `accounts` repository only |
| `roles/iam.serviceAccountUser` | each of `cst-accounts`, `cst-deletion`, `cst-gateway`, `cst-session` and `cst-grading` |

Stop if it grants anything on the state bucket, a secret, Firestore or a project-wide
`serviceAccountUser`. The two outputs must equal `workloadIdentityProvider` and
`deployServiceAccount` in `infra/environments/development.json`.

### 2. Move image and gateway ownership to CI

Re-plan both existing modules with this branch. Adding `ignore_changes` changes no resource:

```powershell
$hello = "us-docker.pkg.dev/cloudrun/container/hello@" + (gcloud.cmd artifacts docker images describe us-docker.pkg.dev/cloudrun/container/hello:latest --format="value(image_summary.digest)")
$accountsImage = gcloud.cmd run services describe accounts --region=us-central1 --project=casestudy-tech-dev-2e03d0 --format="value(spec.template.spec.containers[0].image)"
$sessionUrl = gcloud.cmd run services describe session --region=us-central1 --project=casestudy-tech-dev-2e03d0 --format="value(status.url)"
terraform -chdir=infra/session-grading plan "-var=session_image=$hello" "-var=grading_image=$hello"
terraform -chdir=infra/accounts plan "-var=image=$accountsImage" "-var=session_service_url=$sessionUrl"
```

Both must report no changes. If either wants to change an image, an annotation or the gateway,
stop: the branch is not the one this runbook describes.

### 3. Create the GitHub environments

Create both before this change is promoted to `staging`. GitHub creates a missing environment on
first use with no protection rules, so a `production` run that arrives first would not wait for
approval. In **Settings → Environments**:

| Environment | Required reviewers | Deployment branches | Secrets and variables |
|---|---|---|---|
| `development` | none (the `staging` merge is the approval) | **Selected branches**: `staging` only | none |
| `production` | `sandythomas1` | **Selected branches**: `main` only | none |

Leave **Prevent self-review** off on `production`. The owner is the only person who merges into
`main`, so turning it on would block every approval. Leave **Allow administrators to bypass** off
if the plan offers it.

The provider also checks the branch and environment, so a workflow on another branch, or a job
without the `development` environment, cannot get a token even if this setting is wrong.

## The first deploy (AC1 evidence)

1. Merge `dev` into `staging` through a pull request.
2. Open **Actions → Deploy** and watch **Deploy to development**.
3. The job summary ends with lines like:

   ```text
   grading: healthy (revision grading-00002-abc)
   session: healthy (revision session-00002-def)
   accounts: healthy (revision accounts-00004-ghi)
   accounts through the gateway: HTTP 200 (expected 200)
   session through the gateway: HTTP 200 (expected 200)
   grading refuses anonymous callers: HTTP 403 (expected 403)
   session refuses anonymous callers: HTTP 403 (expected 403)
   accounts refuses anonymous callers: HTTP 403 (expected 403)
   All services are healthy.
   ```

4. Copy the summary into #105. Then rerun the eleven checks in
   `docs/runbooks/session-grading-deploy.md` step 5 and `python infra/accounts/check_gateway.py`.

## Rollback

A rollback is an owner action. All commands print revision and config names only.

```powershell
$where = @("--region=us-central1", "--project=casestudy-tech-dev-2e03d0")
```

### A service

List the newest two revisions, then send all traffic to the previous one:

```powershell
gcloud.cmd run revisions list --service=accounts @where --sort-by="~metadata.creationTimestamp" --limit=2 --format="value(metadata.name)"
gcloud.cmd run services update-traffic accounts "--to-revisions=PREVIOUS_REVISION=100" @where
```

This takes effect in seconds and builds nothing. It works the same for `session` and `grading`.

### The deletion job

A job has no traffic. Point it at the previous image:

```powershell
$previous = gcloud.cmd run revisions describe PREVIOUS_REVISION @where --format="value(spec.containers[0].image)"
gcloud.cmd run jobs update account-deletion "--image=$previous" @where
```

### The gateway

```powershell
gcloud.cmd api-gateway api-configs list --api=accounts --project=casestudy-tech-dev-2e03d0 --sort-by="~createTime" --format="table(name.basename(),createTime,state)"
gcloud.cmd api-gateway gateways update accounts --api=accounts "--api-config=PREVIOUS_CONFIG" --location=us-central1 --project=casestudy-tech-dev-2e03d0
```

A gateway update can take several minutes to serve.

### Make it stick

Every rollback above lasts only until the next deploy. That deploy sends all traffic to each
service's newest revision, points the job at the target image and rolls the gateway back to the
template. If the bad change is still on `staging`, it comes back.

To stay rolled back, revert the change in a pull request into `dev`, then promote it to `staging`.
For accounts, reverted source has the old git tree, so the deploy reuses the old image under a new
revision instead of rebuilding. For session and grading, revert `sessionImage` or `gradingImage`.
For the gateway, revert the template; the deploy reuses the old content-addressed config.

Once the session service mounts the signing key (`inject_state_signing_key=true`), never roll it
back to the `hello` placeholder: that would hand the key to a third-party image. Apply
`inject_state_signing_key=false` first, or roll back to the previous reviewed session image.

## Prove the production gate (AC2)

After the environments exist, merge `staging` into `main`. The **Deploy to production** run must
stop at **Waiting for review** with the owner as the required reviewer. Screenshot that, approve
it, and post both on #105. The approved run deploys nothing until #77.

## Test the rollback once (AC4)

Run this on development after the first deploy, while the services still run the placeholders or
other synthetic builds. It needs at least two accounts revisions, which the first deploy creates.

1. Record the current state:
   `gcloud.cmd run services describe accounts @where --format="value(status.traffic)"`.
2. Roll accounts back to the previous revision (see **A service**).
3. Check that traffic moved: the same `describe` shows `PREVIOUS_REVISION` at 100%.
4. Check that it still serves: `python infra/accounts/check_gateway.py` passes, and the private URL
   still returns 403.
5. Restore: `gcloud.cmd run services update-traffic accounts --to-latest @where`, and check step 1
   again.
6. Post the revision names and the results of steps 3–5 on #105. Tick AC4 only then.

## Clean up old gateway configs

Every gateway template change leaves an `accounts-ci-*` config behind. API Gateway allows a
limited number of configs per API, so prune once more than five exist:

```powershell
gcloud.cmd api-gateway api-configs list --api=accounts --project=casestudy-tech-dev-2e03d0 --sort-by="~createTime" --format="table(name.basename(),createTime)"
gcloud.cmd api-gateway api-configs delete OLD_CONFIG --api=accounts --project=casestudy-tech-dev-2e03d0
```

Keep the config the gateway serves, the one before it (the rollback target) and the Terraform
bootstrap config (`accounts-` followed by a timestamp, without `ci`). Deleting the bootstrap config
makes the next accounts plan recreate it.

## Troubleshooting

| Symptom in the log | Cause | Fix |
|---|---|---|
| `Deploy config rejected: <field> is missing or malformed` | `development.json` changed | Fix the field in a pull request. Never weaken the validator to pass. |
| Auth fails with `unauthorized_client` or an attribute condition error | The run is a re-run, not a push to `staging`, not from `deploy.yml`, not in the `development` environment, or the repository ID changed | Re-runs never deploy. To retry a failed deploy, merge a fix (or an empty change) into `staging` through a pull request. Re-read the ID with `gh api repos/sandythomas1/Case-Study-Tech --jq .id`. |
| Auth passes, then the first `gcloud` call fails with `iam.serviceAccounts.getAccessToken` denied | The token's subject doesn't match the `workloadIdentityUser` binding on `cst-deploy` | Check the repository's OIDC subject format first: `gh api repos/sandythomas1/Case-Study-Tech/actions/oidc/customization/sub`. With `use_immutable_subject: true`, the subject is `repo:OWNER@OWNER_ID/REPO@REPO_ID:environment:development`. Fix `github_owner_id`, `github_repository` or `github_repository_id` in `infra/ci-deploy` in a reviewed change, and have the owner apply it. Never widen the binding to a `principalSet`. |
| `iam.serviceAccounts.actAs` denied | A service runs as an identity the deploy cannot act as | Add the identity to `runtime_identities` in `infra/ci-deploy/main.tf` in a reviewed change |
| `run.services.update` denied on a new service | `cstDeploy` updates services; it cannot create them | Create the service with Terraform first |
| Health check `the revision does not run the image this deploy set` | A revision failed to start, or someone deployed by hand | Read the revision's logs. Fix forward or roll back as above. |
| Gateway `/health` not 200 after retries | The new config failed or is still starting | Roll the gateway back, then read the config's state |

Never make a Cloud Run service public, add an invoker or download a service-account key to get a
deploy through.
