variable "project_id" {
  type    = string
  default = "casestudy-tech-dev-2e03d0"
}
variable "region" {
  type    = string
  default = "us-central1"
}
# Images must be digest-pinned (no tags, no default), so a revision can never run
# an unreviewed image. Until #31 ships, the runbook pins the public hello image by
# digest and leaves inject_state_signing_key false, so the key never reaches it.
variable "session_image" {
  type        = string
  description = "Session image pinned by digest (...@sha256:<64 hex>)."
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.session_image))
    error_message = "session_image must be pinned by digest (@sha256:<64 hex>)."
  }
}
variable "grading_image" {
  type        = string
  description = "Grading image pinned by digest (...@sha256:<64 hex>)."
  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.grading_image))
    error_message = "grading_image must be pinned by digest (@sha256:<64 hex>)."
  }
}
variable "inject_state_signing_key" {
  type        = bool
  default     = false
  description = "Expose the state-signing key to the session container. Set true only for a reviewed #31 image."
}
variable "allowed_origins" {
  type    = list(string)
  default = ["https://casestudy-tech-dev-2e03d0.web.app", "https://casestudy-tech-dev-2e03d0.firebaseapp.com"]
}

locals {
  # Pinned by owner decision OD-2 (2026-11-22, #65). docs/decisions/agent-platform-governance.md records why.
  # These are locals, not variables, so no tfvars file or -var flag can swap a model or region at
  # apply time. A change needs a reviewed diff, a new owner decision and an updated record.
  # Location is the `us` multi-region: us-central1 returned 404 for both models in the #65 probe, so
  # the owner's fallback applies (ARCHITECTURE §6 exception). Never "global": it may route a request
  # outside the US.
  agent_platform = {
    location      = "us"
    persona_model = "gemini-3.8-flash"
    grader_model  = "gemini-4-argon"
  }
  services = toset([
    "run.googleapis.com", "artifactregistry.googleapis.com", "secretmanager.googleapis.com",
    "iam.googleapis.com", "aiplatform.googleapis.com", "firestore.googleapis.com"
  ])
  # AD-3 timeout chain (innermost fires first so the session returns a controlled
  # lost-content error instead of a gateway 504):
  #   grading request (120s) < session's call to grading (130s)
  #   < session request (180s) < gateway end-session deadline (190s, gateway.yaml.template).
  # Change all four together.
  grading_timeout_seconds        = 120
  session_grading_client_seconds = 130
  session_timeout_seconds        = 180
}
resource "google_project_service" "required" {
  for_each           = local.services
  service            = each.key
  disable_on_destroy = false
}

# The gateway identity is owned by infra/accounts (AD-4: one gateway config).
data "google_service_account" "gateway" {
  account_id = "cst-gateway"
}
data "google_service_account" "build" {
  account_id = "cst-build"
}

resource "google_service_account" "identity" {
  for_each     = toset(["session", "grading"])
  account_id   = "cst-${each.key}"
  display_name = "CaseStudy ${each.key} development"
  depends_on   = [google_project_service.required]
}

# Agent Platform: inference only. roles/aiplatform.user also grants dataset, model,
# training-job and endpoint management, which neither service needs. This role is
# also part of the zero-retention controls (#65): without cachedContents.create or
# batchPredictionJobs.create, neither service can create an explicit context cache
# or a batch job (record settings 3 and 8). Adding either permission needs an owner decision.
# Renamed from Vertex AI on 2026-11-25 (docs/decisions/agent-platform-governance.md,
# "Rename, 2026-11-25"). The new role_id still forces a replacement.
moved {
  from = google_project_iam_custom_role.vertex_invoke
  to   = google_project_iam_custom_role.agent_platform_invoke
}
moved {
  from = google_project_iam_member.vertex
  to   = google_project_iam_member.agent_platform
}
resource "google_project_iam_custom_role" "agent_platform_invoke" {
  role_id     = "cstAgentPlatformInvoke"
  title       = "CaseStudy Agent Platform inference"
  description = "Call hosted Agent Platform models (generateContent / predict) only."
  permissions = ["aiplatform.endpoints.predict"]
}
# Session repeats the accounts identity check (ARCHITECTURE flow 2): revocation
# lookup plus point reads of the deletion marker and access record. Read-only,
# no list, no write. Firestore IAM cannot be scoped to a collection, so this
# role can point-read any document by path; the service code limits it to
# account_deletions/{uid} and the access record.
resource "google_project_iam_custom_role" "session" {
  role_id     = "cstSessionIdentity"
  title       = "CaseStudy session identity check"
  description = "Check token revocation and read the owner's deletion marker and access record."
  permissions = ["firebaseauth.users.get", "datastore.databases.get", "datastore.entities.get"]
}
# Grading creates score documents and point-reads (get) so #40 can check the
# deletion marker inside the score-write transaction. No list, update or delete.
# Firestore IAM is project-wide (it cannot be scoped to students/{uid}/scores),
# so the grading code must write only that path and use create(), not set().
resource "google_project_iam_custom_role" "grading" {
  role_id     = "cstGrading"
  title       = "CaseStudy grading score writer"
  description = "Create new score records and read the deletion marker; nothing else in Firestore."
  permissions = ["datastore.databases.get", "datastore.entities.get", "datastore.entities.create"]
}
resource "google_project_iam_member" "agent_platform" {
  for_each = google_service_account.identity
  project  = var.project_id
  role     = google_project_iam_custom_role.agent_platform_invoke.name
  member   = "serviceAccount:${each.value.email}"
}
resource "google_project_iam_member" "runtime" {
  for_each = {
    session = google_project_iam_custom_role.session.name
    grading = google_project_iam_custom_role.grading.name
  }
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.identity[each.key].email}"
}

resource "google_artifact_registry_repository" "practice" {
  location      = var.region
  repository_id = "practice"
  description   = "Session and grading images"
  format        = "DOCKER"
  depends_on    = [google_project_service.required]
}
resource "google_artifact_registry_repository_iam_member" "build" {
  location   = google_artifact_registry_repository.practice.location
  repository = google_artifact_registry_repository.practice.name
  role       = "roles/artifactregistry.writer"
  member     = data.google_service_account.build.member
}

resource "google_secret_manager_secret" "state_signing" {
  secret_id = "session-state-signing-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.required]
}
# The value is generated and added in memory by bootstrap_signing_key.py; it is
# never in Terraform configuration, state, tfvars, an output or git.
resource "google_secret_manager_secret_iam_binding" "session" {
  secret_id = google_secret_manager_secret.state_signing.id
  role      = "roles/secretmanager.secretAccessor"
  members   = ["serviceAccount:${google_service_account.identity["session"].email}"]
}

# Ingress stays ALL because the gateway and the session service reach Cloud Run
# over Google's public front end; IAM invoker bindings are the access boundary.
resource "google_cloud_run_v2_service" "grading" {
  name                = "grading"
  location            = var.region
  deletion_protection = true
  ingress             = "INGRESS_TRAFFIC_ALL"
  template {
    service_account                  = google_service_account.identity["grading"].email
    max_instance_request_concurrency = 10
    timeout                          = "${local.grading_timeout_seconds}s"
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
    containers {
      image = var.grading_image
      resources { limits = { cpu = "1", memory = "512Mi" } }
      env {
        name  = "CST_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "CST_AGENT_PLATFORM_LOCATION"
        value = local.agent_platform.location
      }
      env {
        name  = "CST_GRADER_MODEL"
        value = local.agent_platform.grader_model
      }
      startup_probe {
        http_get { path = "/health" }
        initial_delay_seconds = 2
        period_seconds        = 5
      }
      liveness_probe {
        http_get { path = "/health" }
        period_seconds    = 30
        failure_threshold = 3
      }
    }
  }
  # The deploy workflow sets the image after bootstrap (#105); gcloud stamps the client fields.
  lifecycle { ignore_changes = [template[0].containers[0].image, client, client_version] }
  depends_on = [google_project_iam_member.runtime, google_project_iam_member.agent_platform]
}
# Authoritative: only the session identity may invoke the grader (AD-3).
# The gateway has no binding and no route here.
resource "google_cloud_run_v2_service_iam_binding" "grading" {
  location = var.region
  name     = google_cloud_run_v2_service.grading.name
  role     = "roles/run.invoker"
  members  = ["serviceAccount:${google_service_account.identity["session"].email}"]
}

resource "google_cloud_run_v2_service" "session" {
  name                = "session"
  location            = var.region
  deletion_protection = true
  ingress             = "INGRESS_TRAFFIC_ALL"
  template {
    service_account                  = google_service_account.identity["session"].email
    max_instance_request_concurrency = 20
    timeout                          = "${local.session_timeout_seconds}s"
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
    containers {
      image = var.session_image
      resources { limits = { cpu = "1", memory = "512Mi" } }
      env {
        name  = "CST_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "CST_AGENT_PLATFORM_LOCATION"
        value = local.agent_platform.location
      }
      env {
        name  = "CST_PERSONA_MODEL"
        value = local.agent_platform.persona_model
      }
      env {
        name  = "CST_ALLOWED_ORIGINS"
        value = jsonencode(var.allowed_origins)
      }
      env {
        name  = "CST_GRADING_URL"
        value = google_cloud_run_v2_service.grading.uri
      }
      env {
        name  = "CST_GRADING_TIMEOUT_SECONDS"
        value = tostring(local.session_grading_client_seconds)
      }
      dynamic "env" {
        for_each = var.inject_state_signing_key ? [1] : []
        content {
          name = "CST_STATE_SIGNING_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.state_signing.secret_id
              version = "latest"
            }
          }
        }
      }
      startup_probe {
        http_get { path = "/health" }
        initial_delay_seconds = 2
        period_seconds        = 5
      }
      liveness_probe {
        http_get { path = "/health" }
        period_seconds    = 30
        failure_threshold = 3
      }
    }
  }
  # The deploy workflow sets the image after bootstrap (#105); gcloud stamps the client fields.
  lifecycle { ignore_changes = [template[0].containers[0].image, client, client_version] }
  depends_on = [
    google_project_iam_member.runtime,
    google_project_iam_member.agent_platform,
    google_secret_manager_secret_iam_binding.session,
  ]
}
# Authoritative: only the gateway identity; no allUsers binding.
resource "google_cloud_run_v2_service_iam_binding" "session" {
  location = var.region
  name     = google_cloud_run_v2_service.session.name
  role     = "roles/run.invoker"
  members  = [data.google_service_account.gateway.member]
}

output "session_service_url" { value = google_cloud_run_v2_service.session.uri }
output "grading_service_url" { value = google_cloud_run_v2_service.grading.uri }
output "image_repository" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.practice.repository_id}"
}
