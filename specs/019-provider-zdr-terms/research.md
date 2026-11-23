# Research: zero-retention and no-training terms per provider (#19)

- **Date read:** every URL below was read on **2026-11-22** unless marked otherwise. Vendor pages
  change often (none of the Google docs pages showed a last-updated date), so re-read before the
  owner signs anything.
- **Scope:** RC-05, POLICY DAT-4/DAT-5/DAT-6, plan PA-3, CD-1, CD-2. Re-verifies and extends the
  2026-11-18 speech research (PR #100) for OpenAI and Google.
- **Legend:** **UNVERIFIED** = no current primary source confirmed it. "Published terms" = public
  vendor pages. "Written confirmation" = a signed agreement or vendor reply on *our* account, which
  PA-3 and DAT-4 require (spec open question: whether published terms alone count is an owner call).
- **Assumption:** the project's Google Cloud use is governed by the **online Google Cloud Platform
  Terms of Service** (self-serve billing), not a negotiated Google Cloud Master Agreement. If that is
  wrong, the Vertex abuse-monitoring finding below changes in our favour.

## Summary

| Provider / product | Training on our data | Retention by default | What breaks zero retention | Depends on | Provisional verdict |
|---|---|---|---|---|---|
| **Vertex AI (Gemini on Agent Platform)**: persona + grading | No, without our permission (SST §18) | Prompts not stored beyond what is needed to generate output (SST §20(h)). **But:** implicit cache ≤24 h (on by default, durable tier at rest); **abuse-monitoring logging of classifier-flagged prompts up to 90 days with possible human review** for online-terms customers | Durable/implicit cache unless disabled; explicit context caches; abuse-monitoring logging (online terms); Grounding with Google Search (3 days) / Maps (30 days); request-response logging; Interactions API `store` default `true`; Live API session resumption; Frontier models (Gemini 4 Carbon) log prompts+responses ≤30 days | Online ToS vs. Master Agreement (MA customers exempt by default) | **NEEDS AGREEMENT OR WRITTEN EXCEPTION** for abuse-monitoring logging; everything else **CAN MEET with settings** |
| **Cloud Speech-to-Text v2 (Chirp 3)** | No, unless we opt in to data logging | Streaming/sync audio "in memory only", no customer data stored; batch transcripts ~5 days | Opting in to data logging; batch recognition | Default for any project (data logging is an opt-in) | **CAN MEET RC-05 WITH SETTINGS** (data logging off + streaming/sync only); written confirmation still needed for PA-3 |
| **Cloud Text-to-Speech** (standard / Chirp 3 HD) | Not stated explicitly; nothing is logged | "Google does not log any customer Cloud TTS text or audio data"; service is stateless | Unclear for **Gemini-TTS** voices (may fall under Gemini abuse monitoring, UNVERIFIED) | Default | **CAN MEET RC-05 WITH SETTINGS** for non-Gemini voices; Gemini-TTS **UNVERIFIED** |
| **Gemini Live / native audio on Vertex** (`gemini-3.8-live`, `gemini-live-2.5-flash-native-audio`) | Same as Vertex | Same as Vertex, plus session resumption (off by default) caches ≤24 h | Session resumption; abuse monitoring | Same as Vertex | Same as Vertex: **NEEDS AGREEMENT OR WRITTEN EXCEPTION** |
| **OpenAI API speech** (`gpt-transcribe`, `gpt-live-transcribe`, TTS via `gpt-realtime-2.1-mini`) | No by default (Services Agreement §4.2) | `/v1/audio/transcriptions`: **no** abuse-monitoring retention. `/v1/realtime`, `/v1/audio/speech`, `/v1/live/sessions`: **30 days** abuse monitoring | 30-day abuse logs on Realtime (needed for live STT and for the only non-deprecated TTS); file uploads (CSAM scan retention even under ZDR); Files, Batches, Audio voices not ZDR-eligible | **ZDR / Modified Abuse Monitoring needs OpenAI's prior approval via sales** | File STT (`gpt-transcribe` on `/v1/audio/transcriptions`) **CAN MEET by default**; live STT and TTS **NEED APPROVAL (ZDR)**. No plain-TTS successor exists |

## 1. Vertex AI: Gemini on Agent Platform (persona inference and grading)

Vertex AI is now "Gemini Enterprise Agent Platform" (rename confirmed in PR #100). The docs keep
the `vertex-ai/generative-ai/docs/...` URLs.

### Published terms

**(b) Training**
- Service Specific Terms (SST) **§18 Training Restriction** (formerly §17): "Google will not use
  Customer Data to train or fine-tune any AI/ML models without Customer's prior permission or
  instruction." https://cloud.google.com/terms/service-terms (page footer: last modified
  April 2, 2026).
- Same statement on the ZDR page, covering "all managed models", GA and pre-GA:
  https://docs.cloud.google.com/vertex-ai/generative-ai/docs/vertex-ai-zero-data-retention and
  https://docs.cloud.google.com/vertex-ai/generative-ai/docs/data-governance
- Abuse-monitoring logs: "This data won't be used to train or fine-tune any AI/ML models."
  https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/abuse-monitoring

**(a) Retention**
- SST **§20(h)** (Generative AI Services, "Handling of Prompts and Generated Output"): "Absent
  Customer's prior permission or instruction, Google will not store outside Customer's Account
  (i) Customer Data prompted to a Generative AI Service for longer than is reasonably necessary to
  create the Generated Output, or (ii) the Generated Output."
  https://cloud.google.com/terms/service-terms
- **Implicit data caching** (ZDR page above): on by default for supported Gemini models, two tiers.
  *In-memory*: project-scoped, "deleted no later than 24 hours after it's written". *Durable*: used
  when in-memory is full, stored **at rest** with Google default encryption, deleted within 24 h;
  "Customer-managed encryption keys (CMEK) aren't supported for durable caching." Cache data is never
  used for training.
- **Abuse monitoring**: Cloud ToS **§4.3** "Generative AI Safety and Abuse for GCP Services":
  "Notwithstanding the 'Handling of Prompts and Generated Output' section ... if these tools detect
  potential abuse or violations of Google's AUP or Prohibited Use Policy, Google may log Customer
  prompts solely for the purpose of reviewing and determining whether a violation has occurred."
  https://cloud.google.com/terms
  The abuse-monitoring page adds, for Google models not designated Frontier: logging happens when
  "automated safety classifiers detect suspicious activity", data is "stored securely for up to 90
  days in the same region or multi-region" selected for the project, "Authorized Google employees
  may assess the flagged prompts", and logs are **not CMEK-encrypted**. "Only customers whose use of
  Google Cloud is governed by the Google Cloud Platform Terms of Service" are in scope;
  "customers with a Google Cloud Master Agreement are exempt from prompt logging for this abuse
  monitoring by default."
  https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/abuse-monitoring
- **Google Frontier Models** (SST §34): **Gemini 4 Carbon**, Gemini 4 Carbon for cyber, Gemini 4
  Argon Cyber Permissive. "Google may log customer prompts and responses solely for ensuring safe
  use", "stored securely inside the customer's environment for up to 30 days"; online-terms
  customers may also get "human review of prompts flagged by our abuse classifiers". Same URL.
- **Why this matters for us:** our personas role-play crisis and self-harm scenarios (POLICY SES-2, SES-8; RC-19). That
  content is exactly what a safety classifier may flag, so for an online-terms customer the
  classifier-triggered 90-day log with human review is a **realistic** path, not a theoretical one.

**(c) Agreement / tier dependency**
- Abuse-monitoring logging depends on the agreement: **online ToS = in scope; Google Cloud Master
  Agreement = exempt by default.**
- A search snippet (Google search index of the ZDR/data-governance page) said "If you are in scope
  for prompt logging for abuse monitoring and want zero data retention, you can request an exception
  for abuse monitoring." That sentence is **not on the current live pages** (re-fetched twice on
  2026-11-22). Whether an exception request process (historically a form for invoiced billing
  accounts) still exists is **UNVERIFIED**.
- Cloud Data Processing Addendum (CDPA) is "incorporated into the Agreement(s)", Google processes
  Customer Data only "to provide, secure, and monitor the Services" and per Customer instructions
  (§5.2), 30-day notice of new subprocessors (§11.4).
  https://cloud.google.com/terms/data-processing-addendum . Whether it is auto-accepted for online
  customers was not visible in the fetched text (**UNVERIFIED**, but historically it is).
- Google AI Studio / Gemini Developer API is a **different product with different terms**; it was
  not researched here and must not be used for session content (keep all Gemini calls on the
  `aiplatform.googleapis.com` endpoint under the Cloud terms).

**(d) Settings to apply** (owner applies; GCP baseline #18 not merged)
1. **Disable all implicit caching** for the project (applies to all regions):
   `PATCH https://aiplatform.googleapis.com/v1/projects/PROJECT_ID/cacheConfig` with body
   `{"name":"projects/PROJECT_ID/cacheConfig","disableCache":true}` (needs `roles/aiplatform.admin`).
   Verify with `GET .../v1/projects/PROJECT_ID/cacheConfig` → `disableCache: true`. Weaker option:
   `{"disableCache":false,"retentionType":"EPHEMERAL"}` keeps in-memory caching (≤24 h, not at rest).
   Source: ZDR page. A Terraform resource for `cacheConfig` was **not found** (**UNVERIFIED**); a
   `null_resource`/`gcloud`/curl step or a startup assertion is the fallback.
2. **Never create explicit context caches** ("disable implicit caching and avoid creating explicit
   caches"; explicit caches have default 60-min TTL and "There isn't a maximum cache duration").
   https://docs.cloud.google.com/vertex-ai/generative-ai/docs/context-cache/context-cache-overview
3. **Leave request-response logging off** ("disabled by default ... per-model, per-project ... To
   achieve zero data retention, do not enable this feature"). ZDR page.
4. **No Grounding with Google Search or Google Maps** (cannot be disabled once used: 3-day query logs
   / 30-day prompt+output storage; SST §20(k)(ii), §20(m)(ii)).
5. If the Interactions API is used, send **`store=false`** on every request (default is `true`).
6. **Live API:** do not enable session resumption (off by default, caches ≤24 h).
7. **Model choice (#65):** avoid **Frontier models (Gemini 4 Carbon)** and any "Advanced AI"
   partner model unless the Master Agreement question is resolved; avoid OpenAI/Anthropic models on
   Model Garden (30-day logging unless partner ZDR approved).
8. **Endpoint:** use the `us-central1` regional endpoint, not `global` ("Don't use the global
   endpoint if you have ML processing requirements"; "Endpoints don't guarantee data residency or
   in-region ML processing").
   https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/locations . Which current GA
   models are served on `us-central1` regionally (vs. only `global`/`us`) did not render
   (**UNVERIFIED**; check the console).
9. **Batch prediction**: not covered on the ZDR page; inputs/outputs live in our own GCS/BigQuery,
   which would itself be persistence of session content (RC-03). Do not use for session content.

**(e) Current GA models** (display names; API IDs not shown on the page):
Gemini 4 Hydrogen, 4 Carbon (Frontier), 4 Argon, 3.8 Flash, 3.8 Live, 3.8 Flash TTS, 3.7/3.6/3.5
Flash, 3.5 Flash-Lite, 2.5 Pro/Flash/Flash-Lite, 2.5 Flash Live (native audio). Preview: 3.1 Pro,
3 Flash and others. https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models

### Needs written confirmation on our account
- That our account is (or is not) under a Master Agreement; if not, a written **abuse-monitoring
  exception** (or MA) so flagged prompts are not logged or human-reviewed.
- That `disableCache: true` is in force for the production project (screenshot or API output).
- That the chosen persona/grader model is not a Frontier or Advanced AI model.

**Verdict: NEEDS AGREEMENT OR WRITTEN EXCEPTION.** Training and caching are solvable by settings,
but on online terms Google reserves the right to log classifier-flagged prompts for up to 90 days
with human review, and our crisis role-play content is likely to be flagged. Under CD-2 a missing
Vertex confirmation holds the release (no swap).

## 2. Google Cloud Speech-to-Text (Chirp 3) and Cloud Text-to-Speech

### Speech-to-Text, published terms
- **(a)/(b)** "By default, Cloud Speech-to-Text does not log customer audio data or transcripts."
  Opt-in data logging "allows Google to use logged customer data to refine and improve the service";
  "Google uses this data solely to train and improve Google products and services"; opt-in buys
  discounted pricing; "Your logged data is not deleted when you delete your project."
  https://docs.cloud.google.com/speech-to-text/docs/data-logging
- Data usage FAQ: "Google does not use any of your content for any purpose except to provide you with
  the Cloud Speech-to-Text API service." Streaming and sync audio is processed **in memory only**,
  with no customer data stored; Google keeps request metadata (receipt time, size). **Batch**
  (async) keeps the transcript ~**5 days**. https://docs.cloud.google.com/speech-to-text/docs/data-usage-faq
- No STT-specific clause was found in the Service Specific Terms; the GCP SST §18 training restriction
  covers it as an AI/ML service (whether STT/Chirp is a "Generative AI Service" subject to ToS §4.3
  abuse monitoring is **UNVERIFIED**; the services list page did not render).
- **(c)** Default for any Cloud project; no tier dependency.
- **(d) Setting:** keep **data logging disabled** (default). Console: *APIs & Services > Dashboard >
  Cloud Speech API > Data logging tab > Disable data logging*; enrollment is per project and requires
  certifying consent, so it cannot turn on silently. No API/Terraform toggle and no status check are
  documented (**UNVERIFIED**); evidence = console screenshot.
  https://docs.cloud.google.com/speech-to-text/docs/enable-data-logging . The page does not say
  whether it applies to V2 / Chirp (**UNVERIFIED**).
- **(e)** Use `StreamingRecognize` / sync `Recognize` only, never `BatchRecognize`. **Chirp 3 is GA
  only in the `us` and `eu` multi-regions; `us-central1` is not listed.**
  https://docs.cloud.google.com/speech-to-text/docs/models/chirp-3 . Use `us` (still US-only).

### Text-to-Speech, published terms
- "Google does not log any customer Cloud TTS text or audio data"; "Cloud Text-to-Speech is both
  stateless and resourceless." https://docs.cloud.google.com/text-to-speech/docs/data-logging
- No explicit no-training sentence on that page; SST §18 applies. Nothing to set.
- **Gemini-TTS** voices in Cloud TTS and Gemini 3.8 Flash TTS on Vertex: whether they follow the
  stateless statement or Gemini abuse monitoring is **UNVERIFIED**. Prefer Chirp 3 HD / standard
  voices until confirmed.

### Needs written confirmation
- Google confirms streaming STT (Chirp 3, `us`) and TTS keep no audio/text beyond processing, are
  not used for training, and are (or are not) subject to ToS §4.3 abuse logging.

**Verdict: CAN MEET RC-05 WITH SETTINGS** (STT data logging off, streaming/sync only, `us`
multi-region; TTS non-Gemini voices), pending written confirmation for PA-3.

### Gemini Live / native audio as a speech path
`gemini-3.8-live` and `gemini-live-2.5-flash-native-audio` are GA; `gemini-3.5-transcribe-live-preview`
is Preview STT-only. https://docs.cloud.google.com/vertex-ai/generative-ai/docs/live-api . Same terms
as §1 plus: do not enable session resumption (caches text/audio/output ≤24 h; ZDR page). Regions not
listed on the page (**UNVERIFIED**). Same verdict as Vertex.

## 3. OpenAI API speech

### Model status (deprecations)
https://developers.openai.com/api/docs/deprecations
- `whisper-1`, `gpt-4o-transcribe`, `gpt-4o-mini-transcribe` (+ `-2025-12-15`),
  `gpt-4o-transcribe-diarize`: notice Aug 26, 2026, **shutdown Feb 26, 2027** → `gpt-live-transcribe`
  or `gpt-transcribe`. `/v1/audio/translations` also shuts down Feb 26, 2027.
- `tts-1`, `tts-1-hd`, `gpt-4o-mini-tts` (all snapshots): notice **Oct 1, 2026**, **shutdown
  Jan 6, 2027** → `gpt-realtime-2.1-mini`.
- `gpt-realtime`, `gpt-4o-realtime`, `gpt-realtime-mini`: shutdown Jan 20, 2027 → `gpt-realtime-2.1`
  / `-2.1-mini`. No audio entries with notice after Nov 1, 2026.
- **There is no non-deprecated model on `/v1/audio/speech`.** `gpt-realtime-2.1-mini` "isn't a
  supported model for `/v1/audio/speech`"; TTS moves to the Realtime API.
  https://developers.openai.com/api/docs/guides/text-to-speech ,
  https://developers.openai.com/api/docs/models/gpt-realtime-2.1-mini (Realtime only, token-priced:
  audio $10 in / $20 out per 1M tokens). It is a speech LLM, so verbatim read-out and refusal
  behaviour on crisis role-play are **UNVERIFIED**.
- `gpt-transcribe`: $0.0045/min, endpoints `v1/audio/transcriptions` and
  `v1/realtime/transcription_sessions`. https://developers.openai.com/api/docs/models/gpt-transcribe
- `gpt-live-transcribe`: $0.017/min, **only** `v1/realtime/transcription_sessions`.
  https://developers.openai.com/api/docs/models/gpt-live-transcribe . The guide connects via
  `wss://api.openai.com/v1/realtime?intent=transcription`; no server VAD.
  https://developers.openai.com/api/docs/guides/realtime-transcription

### Published terms
- **(b)** "data sent to the OpenAI API is not used to train or improve OpenAI models" unless you opt
  in. https://developers.openai.com/api/docs/guides/your-data . Services Agreement §4.2: "OpenAI will
  not use Customer Content to develop or improve the Services, unless Customer explicitly agrees."
  https://openai.com/policies/services-agreement/ (updated Dec 1, 2025, effective Jan 1, 2026).
- **(a)** "abuse monitoring logs are generated for all API feature usage and retained for up to 30
  days" (longer if legally required). Per-endpoint table (your-data page):

  | Endpoint | Training | Abuse monitoring | App state | ZDR eligible |
  |---|---|---|---|---|
  | `/v1/audio/transcriptions` | No | **None** | None | Yes |
  | `/v1/audio/speech` | No | 30 days | None | Yes |
  | `/v1/realtime` | No | 30 days | None | Yes |
  | `/v1/live/sessions` | No | 30 days | None, or 30 days if stored | Yes, with limitations (not explained) |
  | `/v1/files` | No | 30 days | Until deleted | No |

  `/v1/realtime/transcription_sessions` (the endpoint both new STT models list) **is not in the
  table**; whether it inherits the `/v1/realtime` row is **UNVERIFIED** (same gap as PR #100).
- Services Agreement §11.3: OpenAI deletes Customer Content within 30 days (termination section),
  but "may retain Abusive Customer Content".
- File/image inputs "are scanned for CSAM content upon submission" and flagged content is kept for
  manual review even under ZDR/MAM. Not ZDR-eligible: Files, Batches, Audio voices (custom voices),
  Assistants, Conversations, Vector stores, Evals, Fine-tuning.
- **DPA** (updated Dec 1, 2025) is "incorporated into the OpenAI Services Agreement" and has an
  "Execute Data Processing Agreement" signing link; it does not explicitly address training.
  https://openai.com/policies/data-processing-addendum/

**(c) Tier dependency:** ZDR and Modified Abuse Monitoring "are subject to prior approval by OpenAI
and acceptance of additional requirements"; contact sales. No minimum spend or enterprise tier is
stated (**UNVERIFIED** in practice). MAM excludes customer content from abuse logs; ZDR also forces
`store=false`.

**(d) Settings:** after approval, *Settings → Organization → Data controls → Data Retention*; choose
ZDR (or MAM) at org level, or per project (`default` inherits). Without approval the tab is absent.
For file STT, no setting is needed (`/v1/audio/transcriptions` has no abuse-monitoring retention).

**(e)** Breakers: Realtime sessions (30-day logs; needed for live STT and all future TTS), stored
`/v1/live/sessions`, file uploads, Batches, custom voices. OpenAI has no `us-central1` concept;
traffic leaves GCP (new processor under DAT-5). Data residency options exist on a separate page (not
read; **UNVERIFIED**).

**Verdict:**
- `gpt-transcribe` on **`/v1/audio/transcriptions`** (turn-by-turn file STT): **CAN MEET RC-05 with
  no setting** per published terms (no training, no abuse-monitoring retention, no app state);
  written confirmation + DPA still needed for PA-3 and DAT-5.
- `gpt-live-transcribe` / Realtime STT and **all OpenAI TTS** (`gpt-realtime-2.1-mini` on
  `/v1/realtime`): **NEEDS APPROVAL (ZDR or MAM)**; 30-day abuse logs otherwise.
- `tts-1` / `gpt-4o-mini-tts` / `whisper-1` / `gpt-4o-transcribe`: **REJECT for new work**
  (shutdown Jan 6 / Feb 26, 2027), not on terms grounds.

## Requests to send each vendor

### Google Cloud (Vertex AI / Agent Platform, Speech-to-Text, Text-to-Speech)
Send via Google Cloud Support case (Billing/Account or Technical) or the account team.

> We use Gemini on Agent Platform (Vertex AI) in the `us` multi-region for real-time role-play and grading,
> and Cloud Speech-to-Text V2 (Chirp 3, `us` multi-region, streaming) and Cloud Text-to-Speech
> (non-Gemini voices) for speech. Our content is sensitive educational session content. Please
> confirm in writing, for project number [PROJECT_NUMBER]:
> 1. Under SST §18 and §20(h), no prompt, audio, transcript or output is stored beyond request
>    processing or used to train or fine-tune any model.
> 2. Whether our account is governed by the online Google Cloud Platform Terms of Service or a Google
>    Cloud Master Agreement. If online terms: how we obtain an exemption from prompt logging for
>    abuse monitoring (ToS §4.3), including classifier-triggered logging and human review, so that no
>    prompt or response is retained. Our role-play includes simulated crisis and self-harm dialogue by
>    design.
> 3. That with `cacheConfig.disableCache = true`, no in-memory or durable cache of our prompts exists.
> 4. That Speech-to-Text streaming/sync recognition (Chirp 3) and Text-to-Speech keep no audio or
>    text after processing, are not used for training, and are or are not subject to ToS §4.3 abuse
>    logging. Whether Gemini-TTS voices follow the same terms.
> 5. Which agreement and version (CDPA, SST) governs these commitments for our account.

### OpenAI (only if OpenAI is kept as a speech candidate)
Send to OpenAI sales / via the API platform contact form.

> We request Zero Data Retention (or Modified Abuse Monitoring) for organization [ORG_ID], project
> [PROJECT_ID], for speech only: `gpt-transcribe` on `/v1/audio/transcriptions`,
> `gpt-live-transcribe` on Realtime transcription sessions, and `gpt-realtime-2.1-mini` for speech
> output. Content is sensitive educational role-play, including simulated crisis dialogue. Please
> confirm in writing:
> 1. Approval of ZDR (or MAM) and the additional requirements we must accept.
> 2. That ZDR covers `/v1/realtime/transcription_sessions` and `/v1/realtime?intent=transcription`
>    (not listed in the data-controls table) and `/v1/realtime`.
> 3. That `/v1/audio/transcriptions` keeps no abuse-monitoring logs or application state today,
>    without ZDR.
> 4. That no customer content is used for training (Services Agreement §4.2), and how we execute
>    the DPA.
> 5. Whether `gpt-realtime-2.1-mini` can be configured to read supplied text verbatim without
>    refusing or altering simulated crisis dialogue.

## Open / unverified

1. **Vertex abuse-monitoring exception path for online-terms customers**: the "request an exception"
   sentence seen in a search snippet is not on the live pages. Decisive for CD-2.
2. Whether our account has a Google Cloud Master Agreement (owner knows; assumed no).
3. Terraform/API toggle for Vertex `cacheConfig` and for STT data logging: none found.
4. Whether STT data logging (v1-era console page) governs Speech-to-Text **V2 / Chirp 3**.
5. Whether STT/Chirp and Gemini-TTS are "Generative AI Services" subject to ToS §4.3 abuse logging.
6. Regional (`us-central1`) availability of current GA Gemini models and Live models (table did not
   render).
7. OpenAI: ZDR coverage of `/v1/realtime/transcription_sessions`; meaning of "with limitations" for
   `/v1/live/sessions`; OpenAI data residency; DPA execution for small customers; refusal behaviour
   of `gpt-realtime-2.1-mini`.
8. Google CDPA auto-acceptance for online customers (not visible in the fetched text).
