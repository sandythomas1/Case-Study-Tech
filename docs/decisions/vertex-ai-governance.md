# Vertex AI governance: models, region and zero-retention settings

**Status:** Draft, 2026-11-22, #65. The models are approved by the owner. **The settings that need
the owner to run a command are not applied yet**, so their rows below say *Owner to run*.

> **Synthetic data only (PA-3).** Written zero-retention terms for Vertex AI are not confirmed
> (`provider-zero-retention.md`, row "Vertex AI Gemini", **Pending**). Until that row says
> **Confirmed**, no real student data or session content goes to Vertex AI, in any environment. If the
> terms are still missing at the release gate, the release is held (CD-2).

**Rules this record applies:** RC-05, DD-04, OQ-02 · settles OD-2 · POLICY DAT-4, DAT-5 · plan PA-3,
CD-2, CD-5, AG-3, AG-7, AG-9.

**Sources:** Google's model-versions and lifecycle, data-residency, zero-data-retention and
abuse-monitoring pages, all read on 2026-11-22. Vendor pages change without notice, so re-read them
before a model or region changes.

## Models (OD-2)

| Use | Model ID | Released | Retires no earlier than | Pinned in |
|---|---|---|---|---|
| Personas (session service) | `gemini-3.8-flash` | 2026-09-02 (GA) | 2027-09-02 | `infra/session-grading/main.tf`, `local.vertex.persona_model` → `CST_PERSONA_MODEL` |
| Grader (grading service) | `gemini-4-argon` | 2026-10-13 (GA) | 2027-10-13 | `local.vertex.grader_model` → `CST_GRADER_MODEL` |
| Calibration-set drafting (CD-5) | Anthropic Claude family | n/a | n/a | Not deployed here. Chosen by #47. |

- Google's model-versions page (read 2026-11-22) lists both as GA model IDs with fixed release and
  retirement dates, not `-preview` or `-latest` aliases. Re-check that page before relying on it. Before either retirement date, a new owner decision picks the replacement
  and this record is updated.
- Neither model is an SST §34 Frontier model. That list (Gemini 4 Carbon, Gemini 4 Carbon for cyber,
  Gemini 4 Argon Cyber Permissive) logs prompts for up to 30 days and is rejected for session content.
  `gemini-4-argon` is the plain Argon model, not the Cyber Permissive variant.
- **CD-5:** the calibration-drafting family (Anthropic Claude) differs from the grader's family
  (Gemini), so the grader isn't calibrated on its own family's writing.
- **DAT-5:** Anthropic is a new processor. The owner approved it on 2026-11-22 **for synthetic
  transcripts only**. It never receives student data or session content. Its Pending row in
  `provider-zero-retention.md` is the ARCHITECTURE §8 record: #47 fills in the access path and terms
  before the first call. Any other use needs a new owner decision.

The pins are Terraform `locals`, not variables. No tfvars file or `-var` flag can swap a model or the
region at apply time. A change needs a reviewed diff, a new owner decision and an update to this
record. `infra/session-grading/tests/vertex_governance.tftest.hcl` fails the plan check if the pins
drift from this table or name a Frontier or cyber model.

## Region

- **Pinned:** `us-central1`, regional endpoint `https://us-central1-aiplatform.googleapis.com`. Never
  `global`, which may route a request outside the US (ARCHITECTURE §6).
- **Open question:** the model pages list pay-as-you-go serving for both models only on `global` and
  the `us` and `eu` multi-regions, not on `us-central1`. The owner decided to probe first
  (below, "Region probe").
- **Fallback (owner decision, 2026-11-22):** if `us-central1` refuses either model, Vertex AI moves to
  the `us` multi-region. That needs a reviewed change to `local.vertex.location`, to the script's
  endpoint (taken from Google's multi-region endpoint docs at the time) and to the Terraform test, plus
  a Vertex AI exception in ARCHITECTURE §6 worded like the Chirp 3 one. Data stays in the US either way.
- This answers open item 3 in `provider-zero-retention.md` once the probe result is recorded here.

## Zero-retention settings 1–8

These are settings 1–8 from `provider-zero-retention.md` "Required settings". #65 owns them; #115 owns
settings 9–12 and the support case (owner decision, 2026-11-22). Changing the live project is owner
work, like a deploy (AG-9): the owner runs each command and pastes its output into the evidence column.
"Config test" means `terraform test` with a mocked provider. It proves the configuration, not the live
project, so the owner's real `terraform plan` and `apply` output is the evidence for the live state.

| # | Setting | How it is applied | Verification | Evidence |
|---|---|---|---|---|
| 1 | Implicit caching off, project-wide (both tiers) | No Terraform resource exists, so the owner runs `python infra/session-grading/vertex_governance.py disable-cache` (PATCH the documented `https://aiplatform.googleapis.com/v1/projects/<PROJECT_ID>/cacheConfig` with `disableCache: true`, then GET it back) | `vertex_governance.py check` prints `PASS setting 1` only when the GET shows `disableCache: true` | **Owner to run.** Paste the output with its UTC timestamp. |
| 2 | Request-response logging stays off | Off by default. `cstVertexInvoke` holds only `aiplatform.endpoints.predict`. Which permission the publisher-model logging config API checks is **unverified**; the owner confirms it from Google's IAM permission reference | Terraform test `vertex_role_is_inference_only`; the owner records a console check that no publisher model has request-response logging enabled | Config test passes (2026-11-22). **Owner to record the console check and the permission.** |
| 3 | No explicit context caches | `cstVertexInvoke` has no `aiplatform.cachedContents.create` | Terraform test `vertex_role_is_inference_only`; `vertex_governance.py check` prints `PASS setting 3` when the `us-central1` list is empty | Config test passes (2026-11-22). **Owner to run `check`.** |
| 4 | No Grounding with Google Search or Maps | Code rule: no request includes a `googleSearch` or `googleMaps` tool | Repo search, 2026-11-22: no application code calls Vertex AI yet. The persona harness (#67) and the grader (#35) must each ship a test that fails if a request carries a grounding tool. | Search clean (2026-11-22). Tests due with #67 and #35; tracked by a comment on each (owner decision, 2026-11-22). |
| 5 | `store=false` on any Interactions API call | Code rule | Same repo search. Any caller of the Interactions API must ship a test that every request sets `store=false`. | Search clean (2026-11-22). No caller planned. |
| 6 | Live API session resumption stays off | Code rule | Same repo search. A Live API caller must ship a test that no session sets `sessionResumption`. | Search clean (2026-11-22). No caller planned. |
| 7 | Regional endpoint, never `global` | `local.vertex.location = "us-central1"` → `CST_VERTEX_LOCATION` on both services | Terraform tests `vertex_pins_match_the_governance_record` and `each_service_gets_only_its_own_model`; `vertex_governance.py probe` | Config tests pass (2026-11-22). **Owner to run `probe` and send the `plan`/`apply` output.** |
| 8 | No batch prediction for session content | `cstVertexInvoke` has no `aiplatform.batchPredictionJobs.create` | Terraform test `vertex_role_is_inference_only` | Config test passes (2026-11-22). **Owner to send the `plan`/`apply` output.** |

**Abuse-monitoring logging exemption.** It can't be set by us: it depends on the agreement
(`provider-zero-retention.md`, "What counts as written terms"). #115 owns the support case that asks for
it. Until it is granted, or the account is shown to be on a Master Agreement, the Vertex AI row stays
**Pending**, and so does the synthetic-data-only rule above.

### Region probe

`python infra/session-grading/vertex_governance.py probe` sends one fixed synthetic prompt ("Reply with
the single word OK.", 8 output tokens) to each pinned model on `us-central1`. It prints only the HTTP
status, never a response. Allowed under PA-3 because the prompt is synthetic.

**Owner to run.** Paste the output here. If either line is `FAIL` with HTTP 400 or 404, apply the
fallback above.

## How the owner applies and verifies (AG-9)

From the repo root, signed in with `gcloud auth login` as an account with `roles/aiplatform.admin` on
`casestudy-tech-dev-2e03d0`:

1. `terraform -chdir=infra/session-grading plan`, then `apply` once the plan shows only the new
   `CST_VERTEX_LOCATION`, `CST_PERSONA_MODEL` and `CST_GRADER_MODEL` env vars on the two services.
2. `python infra/session-grading/vertex_governance.py disable-cache`
3. `python infra/session-grading/vertex_governance.py check`
4. `python infra/session-grading/vertex_governance.py probe`
5. Paste each output into the Evidence column, and record the setting 2 console check with its date.

Re-run `check` whenever the project's Vertex AI configuration changes and before the release gate (#70).

## Terms

- **Written terms:** Pending. `provider-zero-retention.md` holds the status; #115 holds the support case
  and the final verdict.
- **Where signed terms are stored:** outside the repo. None exist yet. When the first one arrives, the
  owner records its location here and in `provider-zero-retention.md`, never the document itself.
- Nothing in this repo is a signed vendor document, credential or key. The script uses the owner's
  gcloud session, keeps the access token in memory and never prints it.

## Owner decisions

All on 2026-11-22, verbatim answers. The scope answer is in #65's first progress comment; the model and
region answers are in comment 7090369227, and the last two are in the PR progress comment.

- **Scope:** "#65 owns Vertex 1–8 (Recommended)". #65 owns the model choice, region, IAM, governance
  record and settings 1–8. #115 keeps the support case, settings 9–12 and the final verdicts.
- **Persona model:** "gemini-3.8-flash (Recommended)".
- **Grader model:** "gemini-4-argon (Recommended)".
- **Calibration-drafting family (CD-5):** "Anthropic Claude (Recommended)". Synthetic transcripts only.
- **Region:** "Probe, then fall back to us (Recommended)".
- **Anthropic record:** "Add a Pending row now (Recommended)". The Pending row is in
  `provider-zero-retention.md`.
- **Settings 4–6 tests:** "Comment on #35, no AC change (Recommended)". Comments on #67 and #35, no
  acceptance-criteria change.
