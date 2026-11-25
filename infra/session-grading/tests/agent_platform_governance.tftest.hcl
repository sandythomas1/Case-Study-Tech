# Offline configuration check for the Agent Platform governance pins (#65).
# The provider is mocked, so this needs no credentials, state or network beyond
# `terraform init -backend=false`. Run: terraform test (from infra/session-grading).

mock_provider "google" {
  # Generated mock strings fail the provider's IAM member validation.
  mock_data "google_service_account" {
    defaults = {
      email  = "mock@casestudy-tech-dev-2e03d0.iam.gserviceaccount.com"
      member = "serviceAccount:mock@casestudy-tech-dev-2e03d0.iam.gserviceaccount.com"
    }
  }
}

variables {
  # Synthetic digests: the plan only needs syntactically valid pinned images.
  session_image = "us-docker.pkg.dev/cloudrun/container/hello@sha256:0000000000000000000000000000000000000000000000000000000000000000"
  grading_image = "us-docker.pkg.dev/cloudrun/container/hello@sha256:1111111111111111111111111111111111111111111111111111111111111111"
}

run "agent_platform_pins_match_the_governance_record" {
  command = plan

  assert {
    condition     = local.agent_platform.location == "us"
    error_message = "Agent Platform location must be the us multi-region recorded in docs/decisions/agent-platform-governance.md."
  }
  assert {
    condition     = local.agent_platform.location != "global"
    error_message = "The global endpoint may route outside the US and is never allowed (ARCHITECTURE §6)."
  }
  assert {
    condition     = local.agent_platform.persona_model == "gemini-3.8-flash" && local.agent_platform.grader_model == "gemini-4-argon"
    error_message = "Model IDs must match OD-2 in docs/decisions/agent-platform-governance.md."
  }
  assert {
    # SST §34 Frontier models and the cyber variants log prompts for up to 30 days.
    condition = alltrue([
      for model in [local.agent_platform.persona_model, local.agent_platform.grader_model] :
      !can(regex("carbon|cyber|permissive", model))
    ])
    error_message = "A Frontier or cyber model logs prompts and is rejected for session content."
  }
}

run "each_service_gets_only_its_own_model" {
  command = plan

  assert {
    condition = {
      for e in google_cloud_run_v2_service.session.template[0].containers[0].env : e.name => e.value
    }["CST_PERSONA_MODEL"] == "gemini-3.8-flash"
    error_message = "The session service must receive the pinned persona model."
  }
  assert {
    condition = {
      for e in google_cloud_run_v2_service.grading.template[0].containers[0].env : e.name => e.value
    }["CST_GRADER_MODEL"] == "gemini-4-argon"
    error_message = "The grading service must receive the pinned grader model."
  }
  assert {
    condition = alltrue([
      for service in [google_cloud_run_v2_service.session, google_cloud_run_v2_service.grading] :
      contains([for e in service.template[0].containers[0].env : e.value if e.name == "CST_AGENT_PLATFORM_LOCATION"], "us")
    ])
    error_message = "Both services must receive the pinned Agent Platform location."
  }
  assert {
    condition = (
      !contains([for e in google_cloud_run_v2_service.session.template[0].containers[0].env : e.name], "CST_GRADER_MODEL") &&
      !contains([for e in google_cloud_run_v2_service.grading.template[0].containers[0].env : e.name], "CST_PERSONA_MODEL")
    )
    error_message = "A service must not receive the other service's model."
  }
}

run "agent_platform_role_is_inference_only" {
  command = plan

  assert {
    # Record settings 3 and 8: no explicit context caches and no batch jobs.
    condition     = toset(google_project_iam_custom_role.agent_platform_invoke.permissions) == toset(["aiplatform.endpoints.predict"])
    error_message = "cstAgentPlatformInvoke must hold only aiplatform.endpoints.predict (no cachedContents.create or batchPredictionJobs.create)."
  }
}
