variable "project_id" {
  type    = string
  default = "casestudy-tech-dev-2e03d0"
}
variable "region" {
  type    = string
  default = "us-central1"
}
variable "image" {
  type        = string
  description = "Immutable accounts image digest or revision tag built from verified source."
}
variable "allowed_origins" {
  type    = list(string)
  default = ["https://casestudy-tech-dev-2e03d0.web.app", "https://casestudy-tech-dev-2e03d0.firebaseapp.com"]
}

locals {
  services = toset([
    "run.googleapis.com", "cloudbuild.googleapis.com", "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com", "apikeys.googleapis.com", "iam.googleapis.com",
    "iamcredentials.googleapis.com", "apigateway.googleapis.com", "servicemanagement.googleapis.com",
    "servicecontrol.googleapis.com", "cloudscheduler.googleapis.com", "monitoring.googleapis.com"
  ])
}
resource "google_project_service" "required" {
  for_each           = local.services
  service            = each.key
  disable_on_destroy = false
}
resource "google_service_account" "identity" {
  for_each     = toset(["accounts", "deletion", "gateway", "scheduler", "build"])
  account_id   = "cst-${each.key}"
  display_name = "CaseStudy ${each.key} development"
  depends_on   = [google_project_service.required]
}
resource "google_project_iam_custom_role" "accounts" {
  role_id     = "cstAccounts"
  title       = "CaseStudy account API"
  description = "Verify and disable owners; read scores and record durable deletion requests."
  permissions = [
    "firebaseauth.users.get", "firebaseauth.users.update",
    "datastore.databases.get", "datastore.entities.get", "datastore.entities.list",
    "datastore.entities.create", "datastore.entities.update"
  ]
}
resource "google_project_iam_custom_role" "deletion" {
  role_id     = "cstDeletion"
  title       = "CaseStudy deletion worker"
  description = "Read queued requests, disable/delete auth users, erase owner records and mark completion."
  permissions = [
    "firebaseauth.users.get", "firebaseauth.users.update", "firebaseauth.users.delete",
    "datastore.databases.get", "datastore.entities.get", "datastore.entities.list",
    "datastore.entities.update", "datastore.entities.delete"
  ]
}
resource "google_project_iam_member" "runtime" {
  for_each = {
    accounts = google_project_iam_custom_role.accounts.name
    deletion = google_project_iam_custom_role.deletion.name
  }
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.identity[each.key].email}"
}
resource "google_artifact_registry_repository" "accounts" {
  location      = var.region
  repository_id = "accounts"
  format        = "DOCKER"
  depends_on    = [google_project_service.required]
}
resource "google_storage_bucket" "build" {
  name                        = "${var.project_id}-account-builds"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  lifecycle_rule {
    condition { age = 14 }
    action { type = "Delete" }
  }
}
resource "google_artifact_registry_repository_iam_member" "build" {
  location   = google_artifact_registry_repository.accounts.location
  repository = google_artifact_registry_repository.accounts.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.identity["build"].email}"
}
resource "google_storage_bucket_iam_member" "build" {
  # Cloud Build also checks bucket metadata before reading the source archive.
  for_each = toset(["roles/storage.objectViewer", "roles/storage.legacyBucketReader"])
  bucket   = google_storage_bucket.build.name
  role     = each.key
  member   = "serviceAccount:${google_service_account.identity["build"].email}"
}
resource "google_project_iam_member" "build_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.identity["build"].email}"
}
resource "google_apikeys_key" "identity" {
  name         = "accounts-identity"
  display_name = "Accounts server Identity Platform exchange only"
  restrictions {
    api_targets { service = "identitytoolkit.googleapis.com" }
    api_targets { service = "securetoken.googleapis.com" }
  }
  depends_on = [google_project_service.required]
}
resource "google_secret_manager_secret" "identity" {
  secret_id = "accounts-identity-api-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.required]
}
# Secret value is transferred in memory by bootstrap_identity_secret.py, never
# placed in Terraform configuration, a local env file, an output or a build.
resource "google_secret_manager_secret_iam_member" "runtime" {
  for_each  = toset(["accounts", "deletion"])
  secret_id = google_secret_manager_secret.identity.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.identity[each.key].email}"
}
resource "google_cloud_run_v2_service" "accounts" {
  name                = "accounts"
  location            = var.region
  deletion_protection = true
  ingress             = "INGRESS_TRAFFIC_ALL"
  template {
    service_account                  = google_service_account.identity["accounts"].email
    max_instance_request_concurrency = 20
    timeout                          = "30s"
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
    containers {
      image = var.image
      resources { limits = { cpu = "1", memory = "512Mi" } }
      env {
        name  = "CST_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "CST_REQUEST_URI"
        value = "https://${var.project_id}.firebaseapp.com"
      }
      env {
        name  = "CST_ALLOWED_ORIGINS"
        value = jsonencode(var.allowed_origins)
      }
      env {
        name = "CST_IDENTITY_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.identity.secret_id
            version = "latest"
          }
        }
      }
      startup_probe {
        http_get { path = "/health" }
        initial_delay_seconds = 2
        period_seconds        = 5
      }
    }
  }
  depends_on = [google_project_iam_member.runtime, google_secret_manager_secret_iam_member.runtime]
}
# Authoritative invoker policy: only the gateway identity; no allUsers binding.
resource "google_cloud_run_v2_service_iam_binding" "gateway" {
  location = var.region
  name     = google_cloud_run_v2_service.accounts.name
  role     = "roles/run.invoker"
  members  = ["serviceAccount:${google_service_account.identity["gateway"].email}"]
}
resource "google_cloud_run_v2_job" "deletion" {
  name                = "account-deletion"
  location            = var.region
  deletion_protection = true
  template {
    template {
      service_account = google_service_account.identity["deletion"].email
      max_retries     = 2
      timeout         = "600s"
      containers {
        image   = var.image
        command = ["python", "-m", "cst_accounts.main"]
        resources { limits = { cpu = "1", memory = "512Mi" } }
        env {
          name  = "CST_PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "CST_REQUEST_URI"
          value = "https://${var.project_id}.firebaseapp.com"
        }
        env {
          name = "CST_IDENTITY_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.identity.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }
  depends_on = [google_project_iam_member.runtime, google_secret_manager_secret_iam_member.runtime]
}
resource "google_cloud_run_v2_job_iam_binding" "scheduler" {
  location = var.region
  name     = google_cloud_run_v2_job.deletion.name
  role     = "roles/run.invoker"
  members  = ["serviceAccount:${google_service_account.identity["scheduler"].email}"]
}
resource "google_cloud_scheduler_job" "deletion" {
  name             = "account-deletion-hourly"
  region           = var.region
  schedule         = "0 * * * *"
  time_zone        = "Etc/UTC"
  attempt_deadline = "180s"
  retry_config {
    retry_count          = 3
    min_backoff_duration = "30s"
    max_backoff_duration = "300s"
  }
  http_target {
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.deletion.name}:run"
    http_method = "POST"
    body        = base64encode("{}")
    headers     = { "Content-Type" = "application/json" }
    oauth_token { service_account_email = google_service_account.identity["scheduler"].email }
  }
  depends_on = [google_cloud_run_v2_job_iam_binding.scheduler]
}
resource "google_api_gateway_api" "accounts" {
  provider   = google-beta
  api_id     = "accounts"
  depends_on = [google_project_service.required]
}
resource "google_api_gateway_api_config" "accounts" {
  provider             = google-beta
  api                  = google_api_gateway_api.accounts.api_id
  api_config_id_prefix = "accounts-"
  openapi_documents {
    document {
      path = "accounts.yaml"
      contents = base64encode(templatefile("${path.module}/../gateway.yaml.template", {
        PROJECT_ID           = var.project_id
        ACCOUNTS_SERVICE_URL = google_cloud_run_v2_service.accounts.uri
      }))
    }
  }
  gateway_config {
    backend_config { google_service_account = google_service_account.identity["gateway"].email }
  }
  lifecycle { create_before_destroy = true }
  depends_on = [google_cloud_run_v2_service_iam_binding.gateway]
}
resource "google_api_gateway_gateway" "accounts" {
  provider   = google-beta
  gateway_id = "accounts"
  region     = var.region
  api_config = google_api_gateway_api_config.accounts.id
}
resource "google_logging_metric" "sweeps" {
  name   = "account_deletion_sweeps"
  filter = "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"account-deletion\" AND jsonPayload.event=\"account_deletion_sweep\""
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}
resource "google_monitoring_alert_policy" "sweep_missing" {
  display_name = "Account cleanup has not reported for three hours"
  combiner     = "OR"
  conditions {
    display_name = "No completed deletion sweep"
    condition_absent {
      filter   = "resource.type=\"cloud_run_job\" AND metric.type=\"logging.googleapis.com/user/${google_logging_metric.sweeps.name}\""
      duration = "10800s"
      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }
  documentation {
    content   = "Inspect Cloud Run account-deletion executions and Cloud Scheduler. Logs contain counts only. Resolve failures before any original 30-day deletion deadline. Notification channels must be attached before enrolling real students."
    mime_type = "text/markdown"
  }
}
resource "google_logging_metric" "sweep_failures" {
  name   = "account_deletion_failures"
  filter = "resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"account-deletion\" AND (jsonPayload.failed>0 OR jsonPayload.overdue>0 OR severity>=ERROR)"
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}
resource "google_monitoring_alert_policy" "sweep_failure" {
  display_name = "Account cleanup failed or exceeded its deadline"
  combiner     = "OR"
  conditions {
    display_name = "Cleanup failure"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_job\" AND metric.type=\"logging.googleapis.com/user/${google_logging_metric.sweep_failures.name}\""
      duration        = "0s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }
  documentation {
    content   = "Inspect account-deletion job counts and retry executions. Do not log credentials or owner records. Attach verified notification channels before real student use."
    mime_type = "text/markdown"
  }
}
output "service_url" { value = google_cloud_run_v2_service.accounts.uri }
output "gateway_url" { value = "https://${google_api_gateway_gateway.accounts.default_hostname}" }
output "identity_key_name" { value = google_apikeys_key.identity.id }
output "build_bucket" { value = google_storage_bucket.build.name }
