# Vertex AI governance: models, region and zero-retention settings

**Status:** Draft, 2026-11-22, #65. The models are approved by the owner. Settings 1, 2, 3, 7 and 8
are verified on the live development project (2026-11-23 UTC). An agent ran the first steps under a recorded one-off AG-9 exception
(`ag9-one-off-exceptions.md`); the owner ran the `us` apply and the final `check`.

> **Synthetic data only (PA-3).** Written zero-retention terms for Vertex AI are not confirmed
> (`provider-zero-retention.md`, row "Vertex AI Gemini", **Pending**). Until that row says
> **Confirmed**, no real student data or session content goes to Vertex AI, in any environment. If the
> terms are still missing at the release gate, the release is held (CD-2).

**Rules this record applies:** RC-05, DD-04, OQ-02 · settles OD-2 · POLICY DAT-4, DAT-5 · plan PA-3,
CD-2, CD-5, AG-3, AG-7, AG-9.

**Sources:** Google's model-versions and lifecycle, data-residency, zero-data-retention and
abuse-monitoring pages, read on 2026-11-22. Google's Vertex AI locations, data-residency and
request-response logging pages, read on 2026-11-23. Vendor pages change without notice, so re-read them
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

- **Pinned:** the `us` multi-region, location `us`, endpoint `https://aiplatform.us.rep.googleapis.com`.
  Google's locations page says multi-region calls must use this `.rep.` host. Never `global`, which
  may route a request outside the US (ARCHITECTURE §6).
- **Why not `us-central1`:** the model pages list pay-as-you-go serving for both models only on
  `global`, `us` and `eu`. The probe confirmed it. On 2026-11-23 `us-central1` returned HTTP 404 for
  both models, and `us` returned HTTP 200 for both ("Region probe" below). So the owner's fallback
  applies: "Probe, then fall back to us (Recommended)" (2026-11-22). ARCHITECTURE §6 records the
  exception.
- **Residency:** ML processing for the pinned models stays in the US multi-region, per Google's
  data-residency table. Google's data-residency page lists both `gemini-3.8-flash` and `gemini-4-argon` with
  "Yes" under "US multi-region". The page says "Checkmarks in the following tables indicate the
  geographic boundary where ML processing occurs". By contrast, `global` requests "may be processed in
  any Google Cloud location around the world". The locations page warns that "Endpoints don't
  guarantee data residency or in-region ML processing", so the per-model table is Google's documented
  processing boundary, not the endpoint. It is a documentation table, not a contractual data-location
  commitment, and it says nothing about where abuse-monitoring logs are kept while that exemption is
  pending (#115). Re-read the table before a model changes.
- This closes open item 3 in `provider-zero-retention.md`.

## Zero-retention settings 1–8

These are settings 1–8 from `provider-zero-retention.md` "Required settings". #65 owns them; #115 owns
settings 9–12 and the support case (owner decision, 2026-11-22). Changing the live project is owner
work, like a deploy (AG-9): the owner runs each command and pastes its output into the evidence column.
The 2026-11-23 run was done by an agent under a recorded one-off exception (`ag9-one-off-exceptions.md`).
All times are UTC.
"Config test" means `terraform test` with a mocked provider. It proves the configuration, not the live
project, so the owner's real `terraform plan` and `apply` output is the evidence for the live state.

| # | Setting | How it is applied | Verification | Evidence |
|---|---|---|---|---|
| 1 | Implicit caching off, project-wide (both tiers) | No Terraform resource exists, so the owner runs `python infra/session-grading/vertex_governance.py disable-cache` (PATCH the documented `https://aiplatform.googleapis.com/v1/projects/<PROJECT_ID>/cacheConfig` with `disableCache: true`, then GET it back) | `vertex_governance.py check` prints `PASS setting 1` only when the GET shows `disableCache: true` | **PASS.** `disable-cache` 2026-11-23T03:24:06Z: `PATCH cacheConfig: HTTP 200`, then `disableCache: true`. `check` 03:24:08Z and 03:28:43Z: `PASS setting 1`. |
| 2 | Request-response logging stays off | Off by default: Google says logging "is disabled by default until you configure a `PublisherModelConfig` resource", one per model and location. Turning it on takes `aiplatform.endpoints.setPublisherModelConfig` (Google's request-response logging page says to restrict it). `cstVertexInvoke` holds only `aiplatform.endpoints.predict`, so neither service can turn it on | Terraform test `vertex_role_is_inference_only`; `vertex_governance.py check` reads `fetchPublisherModelConfig` for each pinned model on `us` and prints `PASS setting 2` on `enabled: false`, or on HTTP 404 (never configured) only when a control read of the same model on the same host and API version returns HTTP 200. A wrong host, version or model ID also returns 404, so a 404 alone proves nothing. Plus a dated Logs Explorer search: no console screen shows this setting (Google: base models are configured "by using the REST API or Python SDK"), so the console evidence is the Admin Activity audit log, which is always on and kept 400 days | **PASS.** Owner's `check` 2026-11-23T03:58:50Z: `PASS setting 2` for `gemini-3.8-flash` and `gemini-4-argon`, each "HTTP 404, never configured (off by default); model read HTTP 200". The earlier 03:28:43Z 404s had no control read and are not counted. Logs Explorer, 2026-11-23 ~04:07Z, last 400 days: `protoPayload.methodName:"SetPublisherModelConfig"` returned **0 results**; the control search `protoPayload.methodName:"CacheConfig"` in the same window returned 1, the setting 1 `UpdateCacheConfig` call at 03:24:06Z. Screenshots kept outside the repo. |
| 3 | No explicit context caches | `cstVertexInvoke` has no `aiplatform.cachedContents.create` | Terraform test `vertex_role_is_inference_only`; `vertex_governance.py check` prints `PASS setting 3` when the `us` list is empty | **PASS.** 0 caches on `us-central1` (03:24:08Z) and on `us` (03:28:43Z). Config test passes. |
| 4 | No Grounding with Google Search or Maps | Code rule: no request includes a `googleSearch` or `googleMaps` tool | Repo search, 2026-11-22: no application code calls Vertex AI yet. The persona harness (#67) and the grader (#35) must each ship a test that fails if a request carries a grounding tool. | Search clean (2026-11-22). Tests due with #67 and #35; tracked by a comment on each (owner decision, 2026-11-22). |
| 5 | `store=false` on any Interactions API call | Code rule | Same repo search. Any caller of the Interactions API must ship a test that every request sets `store=false`. | Search clean (2026-11-22). No caller planned. |
| 6 | Live API session resumption stays off | Code rule | Same repo search. A Live API caller must ship a test that no session sets `sessionResumption`. | Search clean (2026-11-22). No caller planned. |
| 7 | `us` multi-region endpoint, never `global` | `local.vertex.location = "us"` → `CST_VERTEX_LOCATION` on both services | Terraform tests `vertex_pins_match_the_governance_record` and `each_service_gets_only_its_own_model`; `vertex_governance.py probe` | Probe: `us-central1` HTTP 404 for both (03:24:10Z); `us` HTTP 200 for both (03:28:46Z). Config tests pass. **PASS.** The owner applied the saved `us` plan on 2026-11-23, before the 03:58:50Z `check` (the apply output has no timestamp): `0 added, 2 changed, 0 destroyed`, `CST_VERTEX_LOCATION` on the grading and session services only. The plan after it: `No changes`. |
| 8 | No batch prediction for session content | `cstVertexInvoke` has no `aiplatform.batchPredictionJobs.create` | Terraform test `vertex_role_is_inference_only` | **PASS.** Config test passes. Live apply 2026-11-23T03:23:50Z: `0 added, 2 changed, 0 destroyed`, env vars only, IAM unchanged. The plan after it: `No changes`. |

**Abuse-monitoring logging exemption.** It can't be set by us: it depends on the agreement
(`provider-zero-retention.md`, "What counts as written terms"). #115 owns the support case that asks for
it. Until it is granted, or the account is shown to be on a Master Agreement, the Vertex AI row stays
**Pending**, and so does the synthetic-data-only rule above.

### Region probe

`python infra/session-grading/vertex_governance.py probe` sends one fixed synthetic prompt ("Reply with
the single word OK.", 8 output tokens) to each pinned model on the pinned location. It prints only the
HTTP status, never a response. Allowed under PA-3 because the prompt is synthetic.

| When (UTC) | Location | `gemini-3.8-flash` | `gemini-4-argon` |
|---|---|---|---|
| 2026-11-23T03:24:10Z | `us-central1` | FAIL, HTTP 404 | FAIL, HTTP 404 |
| 2026-11-23T03:24:50Z | `us` (same prompt, ad hoc call before the script changed) | HTTP 200 | HTTP 200 |
| 2026-11-23T03:28:46Z | `us` (`probe`, after the change) | PASS, HTTP 200 | PASS, HTTP 200 |

Both models answer on `us` under their exact IDs, so the 404 was about the location, not the model
ID.

## How the owner applies and verifies (AG-9)

From the repo root, signed in with `gcloud auth login` as an account with `roles/aiplatform.admin` on
`casestudy-tech-dev-2e03d0`:

1. `terraform -chdir=infra/session-grading plan`, then `apply`, only if the plan changes nothing but
   Vertex env vars on the session and grading services. The next run is the pending `us` change: one
   value, `CST_VERTEX_LOCATION` from `us-central1` to `us`, on each of the two services
   (`0 added, 2 changed, 0 destroyed`).
2. `python infra/session-grading/vertex_governance.py disable-cache` (once per project; already done on
   development)
3. `python infra/session-grading/vertex_governance.py check` (settings 1, 2 and 3)
4. `python infra/session-grading/vertex_governance.py probe`
5. In Logs Explorer, search the last 400 days for `protoPayload.methodName:"SetPublisherModelConfig"`
   (expect 0 results) and, as the control, `protoPayload.methodName:"CacheConfig"` (expect the
   setting 1 call). Save dated screenshots outside the repo (setting 2).
6. Paste each output with its UTC time into the Evidence column.

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
- **Apply run:** "Authorize me, one-off (Recommended)". An agent ran the owner steps on the
  development project only, and applied the saved plan only because it changed nothing but the two
  services' env vars. Every call it made is listed in `ag9-one-off-exceptions.md`. It doesn't carry
  forward.
- **Second apply (the `us` change):** "Apply it, same limits (Recommended)". The tool permission prompt
  blocked the agent's command, so nothing was applied. On the policy review's escalation the owner
  then chose "You run it, I record (Recommended)": the owner runs the apply and the agent records it.
- **Setting 2 evidence:** "Add control read + console check (Recommended)". `check` counts a 404 only
  after a successful control read, and the owner adds one dated console screenshot.
- **Setting 2 console evidence:** no console screen shows request-response logging for base models,
  so the owner chose "Audit log search (Recommended)": a dated Logs Explorer search for any
  `SetPublisherModelConfig` call, with a control search that must find a known call.
