# CI tool: google-github-actions/auth

**Status:** Approved by owner 2026-11-22, #105 ("google-github-actions/auth (Recommended)").

## Purpose

Signs the **Deploy to development** job in `.github/workflows/deploy.yml` in to Google Cloud
without a key. It exchanges the job's short-lived GitHub OIDC token for a Google access token for
`cst-deploy` through Workload Identity Federation. The gcloud and docker steps after it use that
token. No service-account key exists, and no Google credential is stored in GitHub (AC3).

Alternative considered: calling the STS and IAM Credentials APIs by hand with `curl`. That would
remove a third-party action, but it is more code to review and easier to get subtly wrong, such
as by logging a token. Google maintains this action, and it is the documented path.

## Pin and verification

- v3.0.0, pinned by full commit SHA `7c6bc770dae815cd3e89ee6cdf493a5fab2cc093` in
  `deploy.yml`. Resolved on 2026-11-22 with
  `gh api repos/google-github-actions/auth/commits/v3.0.0 --jq .sha`.
- Only the inputs `workload_identity_provider` and `service_account` are set. Both come from
  `infra/environments/development.json` after `scripts/ci/deploy/deploy_config.py` validates them,
  never from event data.
- zizmor (pedantic, offline) lints the workflow on every pull request
  ([ci-tool-zizmor.md](ci-tool-zizmor.md)).

## What limits the token

The token is only as strong as the conditions on it, and those live in Google Cloud, not in the
workflow (`infra/ci-deploy/main.tf`):

- The provider accepts a token only when `repository_id` is this repository's numeric ID, `ref` is
  `refs/heads/staging`, `environment` is `development`, `event_name` is `push`, `run_attempt` is
  `1` and `job_workflow_ref` is `.github/workflows/deploy.yml` on `staging`. A fork, another
  branch, a pull request (including `pull_request_target`), another workflow file, a job without
  the environment or a re-run cannot get a Google token. The re-run rule (owner decision
  2026-11-22) means repository Write, which can re-run jobs, cannot deploy.
- Only the subject `repo:sandythomas1/Case-Study-Tech:environment:development` may act as
  `cst-deploy`.
- `cst-deploy` can update existing Cloud Run services and the job, push to the `accounts` image
  repository and act as the five runtime identities. It cannot read Terraform state, secrets or
  Firestore, create or delete a Cloud Run service, or change Cloud Run or project IAM.
- Two grants are broader than the workflow uses. `run.services.update` with act-as covers every
  setting of an existing service: environment, secret references, ingress and its runtime
  identity among them. `roles/apigateway.admin` (owner decision 2026-11-22) also covers creating
  and deleting API Gateway APIs and gateways and their IAM policies. Review of `deploy.yml`
  (CODEOWNERS) keeps the workflow to images and gateway configs; IAM does not. The owner kept
  the role for development (synthetic data) on 2026-11-22; a custom role replaces it before
  production (#77).
- Each Google access token gcloud gets through the credential file lasts one hour.

## Data it sees

- The job's OIDC token, which names the repository, ref, environment, workflow and commit. It
  holds no user data.
- The workflow sets no `token_format`, so the action mints no access token itself. gcloud and
  docker get short-lived tokens through the credential file, and no step prints one.
- No session content, student data or secret. The deploy reads only repository code and
  `development.json`.

The action writes a credential configuration file (`gha-creds-*.json`) to the workspace root and
points gcloud at it. It holds no key, but it does hold the job's OIDC request credential, which
can mint new OIDC tokens until the job ends. So treat it as a secret for the job's lifetime. It is
outside the only docker build context (`services/accounts`), so no image can contain it. No step
prints or uploads it, and the action's post step deletes it when the job ends.

## Network egress

- `token.actions.githubusercontent.com`, for the job's OIDC token.
- `sts.googleapis.com` and `iamcredentials.googleapis.com`, which gcloud calls through the
  credential file to exchange the OIDC token and act as `cst-deploy`.

The gcloud CLI the later steps use is the one preinstalled on `ubuntu-latest`. It is not pinned,
so a runner image update can change its version. The steps use only long-stable commands
(`run services update`, `update-traffic`, `api-gateway`). Pin it with `setup-gcloud` if a change
ever breaks a deploy.

## Upgrade

1. Dependabot proposes new action releases once they are a week old
   ([ci-tool-dependabot.md](ci-tool-dependabot.md)). To move it by hand, resolve the tag with
   `gh api repos/google-github-actions/auth/commits/<tag> --jq .sha` and update the SHA and the
   `# vX` comment.
2. Read the release notes for changes to defaults: credential file location, token lifetime or
   exported environment variables.
3. Update this record. The change needs the owner's review through CODEOWNERS.
