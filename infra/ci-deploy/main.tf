# Keyless deploys from GitHub Actions to the development project (#105).
# Only the owner applies this module (POLICY AGT-6); agents cannot change IAM.
# It never grants access to Terraform state, which holds the Identity Platform API key.

variable "project_id" {
  type    = string
  default = "casestudy-tech-dev-2e03d0"
}
variable "region" {
  type    = string
  default = "us-central1"
}
# The numeric ID never changes when a repository is renamed or transferred, so the provider
# condition pins it rather than the name. Read it with `gh api repos/OWNER/REPO --jq .id`.
variable "github_repository_id" {
  type    = string
  default = "1382155772"
  validation {
    condition     = can(regex("^[0-9]+$", var.github_repository_id))
    error_message = "github_repository_id must be the numeric repository ID."
  }
}
variable "github_repository" {
  type    = string
  default = "sandythomas1/Case-Study-Tech"
}
# The owner's numeric user ID, for the immutable OIDC subject. Read it with
# `gh api users/OWNER --jq .id`.
variable "github_owner_id" {
  type    = string
  default = "145699956"
  validation {
    condition     = can(regex("^[0-9]+$", var.github_owner_id))
    error_message = "github_owner_id must be the numeric user ID."
  }
}

locals {
  # The GitHub environment that gates deploys to this project. deploy.yml names the same one.
  environment = "development"
  # The repository uses GitHub's immutable subject format (`use_immutable_subject: true` in
  # `gh api repos/OWNER/REPO/actions/oidc/customization/sub`), so the token's `sub` is
  # repo:OWNER@OWNER_ID/REPO@REPO_ID:environment:ENV. The name-only format never matches (#124).
  github_owner     = split("/", var.github_repository)[0]
  github_repo_name = split("/", var.github_repository)[1]
  github_subject   = "repo:${local.github_owner}@${var.github_owner_id}/${local.github_repo_name}@${var.github_repository_id}:environment:${local.environment}"
  # The runtime identities the deploy sets on its services, job and gateway config.
  runtime_identities = toset(["accounts", "deletion", "gateway", "session", "grading"])
}

resource "google_project_service" "sts" {
  service            = "sts.googleapis.com"
  disable_on_destroy = false
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
  description               = "Short-lived GitHub OIDC tokens for the deploy workflow (#105)."
  depends_on                = [google_project_service.sts]
}

# Tokens from any other repository, branch or environment are rejected here, before any
# service-account binding is checked.
resource "google_iam_workload_identity_pool_provider" "repository" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "case-study-tech"
  display_name                       = "Case-Study-Tech staging"
  attribute_mapping = {
    "google.subject"          = "assertion.sub"
    "attribute.repository_id" = "assertion.repository_id"
    "attribute.ref"           = "assertion.ref"
    "attribute.environment"   = "assertion.environment"
  }
  # Only the first attempt of a push to staging, running this repository's deploy workflow in the
  # development environment, gets a token. Another workflow on staging, a pull_request_target run
  # or a re-run of any run (anyone with Write can re-run) cannot (owner decision 2026-11-22).
  attribute_condition = join(" && ", [
    "assertion.repository_id == '${var.github_repository_id}'",
    "assertion.ref == 'refs/heads/staging'",
    "assertion.environment == '${local.environment}'",
    "assertion.event_name == 'push'",
    "assertion.run_attempt == '1'",
    "assertion.job_workflow_ref == '${var.github_repository}/.github/workflows/deploy.yml@refs/heads/staging'",
  ])
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "deploy" {
  account_id   = "cst-deploy"
  display_name = "CaseStudy deploy from GitHub Actions"
  description  = "Rolls Cloud Run images and the gateway config. No keys (#105)."
}

# Exactly the subject GitHub sends for a job in the development environment, and no
# principalSet (owner decision 2026-11-22, #124).
resource "google_service_account_iam_member" "github" {
  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principal://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/subject/${local.github_subject}"
}

# Update existing services and the job, and read their status. No create, delete, IAM policy
# or invoke, so the deploy can neither add a service nor make one public.
resource "google_project_iam_custom_role" "deploy" {
  role_id     = "cstDeploy"
  title       = "CaseStudy deploy rollout"
  description = "Roll images on existing Cloud Run services and jobs, and read their status."
  permissions = [
    "run.services.get",
    "run.services.update",
    "run.jobs.get",
    "run.jobs.update",
    "run.revisions.get",
    "run.revisions.list",
    "run.operations.get",
  ]
}
resource "google_project_iam_member" "deploy" {
  project = var.project_id
  role    = google_project_iam_custom_role.deploy.name
  member  = google_service_account.deploy.member
}

# Owner decision 2026-11-22: creating a config and pointing the gateway at it needs the
# predefined admin role; no narrower predefined role covers both.
resource "google_project_iam_member" "gateway" {
  project = var.project_id
  role    = "roles/apigateway.admin"
  member  = google_service_account.deploy.member
}

# Push and read the accounts image. Repository scope only, not the practice repository.
resource "google_artifact_registry_repository_iam_member" "accounts" {
  location   = var.region
  repository = "accounts"
  role       = "roles/artifactregistry.writer"
  member     = google_service_account.deploy.member
}

data "google_service_account" "runtime" {
  for_each   = local.runtime_identities
  account_id = "cst-${each.key}"
}

# A Cloud Run update must act as the revision's identity, and a gateway config as its backend
# identity. Bound per identity, never at project level.
resource "google_service_account_iam_member" "act_as" {
  for_each           = data.google_service_account.runtime
  service_account_id = each.value.name
  role               = "roles/iam.serviceAccountUser"
  member             = google_service_account.deploy.member
}

output "workload_identity_provider" {
  description = "workloadIdentityProvider in infra/environments/development.json."
  value       = google_iam_workload_identity_pool_provider.repository.name
}
output "deploy_service_account" {
  description = "deployServiceAccount in infra/environments/development.json."
  value       = google_service_account.deploy.email
}
