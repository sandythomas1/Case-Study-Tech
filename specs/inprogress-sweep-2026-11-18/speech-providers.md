# Speech provider research: Whisper, non-Google/OpenAI vendors, and the GEAP rename

- **Run:** `/build` inprogress-sweep-2026-11-18 (research specialist)
- **Date researched:** 2026-11-18. Every price and term below was read from the cited page on this
  date. Vendor pages change often, so re-check them before the owner signs anything.
- **Feeds:** Phase 2 provider bake-off (#20), OQ-01 (turn transport), POLICY DAT-4 / DAT-5 / DAT-6,
  POLICY §9 ("no self-hosted models"), and ETH-6 (FERPA review).
- **Legend:** **UNVERIFIED** means no primary source confirmed it. "Third-party" means the figure
  comes from an aggregator or blog, not the vendor.

## 0. Gates and assumptions used for scoring

| Gate | Source in repo | How it is applied here |
|---|---|---|
| DAT-4: written terms and settings that forbid retention **and** training, otherwise reject. Outranks quality and cost. | `docs/POLICY.md` DAT-4 | A vendor passes only if a *written* term (DPA, contract, or published data-use doc) says no retention and no training, **and** the setting that turns it on can be enabled for our account tier. |
| DAT-5: no new data processor without an owner decision and a written data-use record. | `docs/POLICY.md` DAT-5 | Every vendor outside Google is a new processor, so each needs an owner decision. |
| Latency: full turn p50 ≤ 2.0 s, p95 ≤ 3.5 s, shared by STT + LLM + TTS. | Task brief, PA-2 | STT finalisation + TTS first audio should take ≤ ~500 ms p50 so the Gemini persona gets ≥ ~1.3 s. |
| Crisis/self-harm role-play must not be refused. | Task brief, ETH-7 | STT engines do not moderate. TTS engines and speech-to-speech LLMs might. |
| FERPA alignment | Owner request, ETH-6 | Look for a DPA that names the vendor a FERPA "school official", or education/student-data terms. |
| No self-hosted models in the MVP. | `docs/POLICY.md` §9 | Any option that runs model weights on our own GPU or a dedicated endpoint conflicts with this. |

**Interface fit** is judged against `SpeechProvider` (`interface.py`): input is streamed 16 kHz
mono s16le PCM, and the output is partial `TranscriptEvent`s followed by exactly one final event.
`synthesize` yields 24 kHz mono s16le PCM chunks. Adapters may resample internally.

**Session cost model.** A session lasts up to 10 minutes. We assume the student speaks about
5 minutes and the persona speaks about 5 minutes. At roughly 150 words per minute and about
6 characters per word, that is **~4,500 TTS characters per session**. STT is shown as a range:
**5 min** of billed audio when the stream is opened per turn, and **10 min** when one stream stays
open for the whole session. This matters for vendors that bill WebSocket time rather than audio
sent (AssemblyAI says so explicitly).

---

## 1. Whisper: what it would actually mean

Whisper is **speech-to-text only**. Every Whisper option below still needs a separate TTS vendor
behind `synthesize`.

### 1(a) OpenAI API (`whisper-1`, `gpt-4o-transcribe` and successors)

**The models are being retired.** OpenAI's deprecations page lists `whisper-1`,
`gpt-4o-transcribe` and `gpt-4o-mini-transcribe` as deprecated. Notice was given on
Aug 26, 2026, they **shut down on Feb 26, 2027**, and the recommended replacements are
`gpt-live-transcribe` or `gpt-transcribe`. OpenAI's TTS models `tts-1`, `tts-1-hd` and
`gpt-4o-mini-tts` shut down on **Jan 6, 2027**, and their recommended replacement is
`gpt-realtime-2.1-mini`.
Source: https://developers.openai.com/api/docs/deprecations

**What replaces them:**

| Model | Use | Price | Streaming | Source |
|---|---|---|---|---|
| `gpt-transcribe` | Recommended file/turn transcription | $0.0045/min | `stream=true` gives `transcript.text.delta` events, then `transcript.text.done` | https://developers.openai.com/api/docs/pricing , https://developers.openai.com/api/docs/guides/speech-to-text |
| `gpt-live-transcribe` | Recommended live transcription (Realtime transcription sessions) | $0.017/min | WebSocket `wss://api.openai.com/v1/realtime?intent=transcription`. Server VAD is **not** supported, so the client must run VAD and send `input_audio_buffer.commit` | https://developers.openai.com/api/docs/guides/realtime-transcription , https://developers.openai.com/api/docs/models/gpt-live-transcribe |
| `gpt-realtime-whisper` | Streaming STT, Realtime transcription sessions only | $0.017/min | Realtime transcription sessions only. Not marked deprecated | https://developers.openai.com/api/docs/models/gpt-realtime-whisper |
| `whisper-1` (deprecated) | File transcription | $0.006/min | `whisper-1` does **not** support `stream=true` | pricing and STT guide above |
| `gpt-4o-transcribe` / `-mini` (deprecated) | File transcription | $0.006 / $0.003 per min | Yes | pricing above |

- **Training:** By default, "data sent to the OpenAI API is not used to train or improve OpenAI
  models" unless you opt in. Source: https://developers.openai.com/api/docs/guides/your-data
- **Retention, by endpoint** (same source): `/v1/audio/transcriptions` has **no** abuse-monitoring
  retention and no application state, and it is ZDR-eligible. `/v1/audio/speech` and `/v1/realtime`
  keep **30 days** of abuse-monitoring logs by default, and both are ZDR-eligible. The Realtime
  transcription-session endpoint is **not listed by name** in the table. Whether
  `gpt-live-transcribe` sessions fall under the `/v1/realtime` ZDR row is **UNVERIFIED**.
- **How to get Zero Data Retention:** ZDR and Modified Abuse Monitoring "are subject to prior
  approval by OpenAI and acceptance of additional requirements". You apply through sales, and the
  control is applied at org/project level. Self-serve accounts cannot turn it on. Source: same page.
- **DPA:** OpenAI publishes a Data Processing Addendum that is incorporated into the Services
  Agreement: https://openai.com/policies/data-processing-addendum/ . How a small customer
  executes it (form or click-through) is **UNVERIFIED**.
- **BAA:** `/v1/audio/transcriptions` is HIPAA-eligible only with ZDR or MAM plus a signed BAA:
  https://cdn.openai.com/osa/hipaa-endpoints.pdf
- **FERPA / education terms for the API:** None found. **UNVERIFIED**.
- **Audio format fit:** The Realtime transcription examples use **24 kHz** PCM16, so the adapter
  would upsample our 16 kHz input. The file endpoint takes containers (wav, flac, mp3, and so on)
  up to 25 MB, so the adapter would wrap PCM in WAV.
- **Moderation risk:** Transcription does not refuse. The *TTS* replacement, `gpt-realtime-2.1-mini`,
  is a speech LLM, and its behaviour on scripted self-harm role-play is **UNVERIFIED**. Treat it as
  a risk.
- **Verdict:** **Feasible only through the successor models.** Building on `whisper-1` now would
  mean a forced migration within about 3 months. DAT-4 needs OpenAI's *approved* ZDR (a sales
  process) plus written confirmation that it covers Realtime transcription sessions. OpenAI is a
  fair *secondary STT* candidate, not a full STT+TTS answer.

### 1(b) Open-source Whisper self-hosted on GCP (Cloud Run GPU or GKE)

- **Policy conflict, first:** `docs/POLICY.md` §9 lists "self-hosted models" under *Not in the
  MVP, do not build*. This option needs an owner decision to amend §9 before it can enter the
  bake-off (AGT-1, AGT-3).
- **What it buys:** DAT-4 becomes trivially true, because no third party sees the audio. It is
  the strongest privacy story.
- **Cloud Run GPU facts** (https://docs.cloud.google.com/run/docs/configuring/services/gpu):
  - NVIDIA L4 (24 GB) and RTX PRO 6000 (96 GB) are both available in **us-central1**. L4 needs at
    least 4 vCPU and 16 GiB (8 vCPU / 32 GiB recommended). GPU requires **instance-based billing**.
    Minimum instances are "charged at the full rate even when idle".
  - The documented start time is about 5 s to GPU-ready. That *excludes* loading Whisper weights
    (large-v3 is about 3 GB), so a realistic cold start is several seconds to tens of seconds
    (**UNVERIFIED** estimate). Scale-to-zero would break the p95 3.5 s turn budget on the first turn,
    so **min-instances ≥ 1 is required**.
- **Cost:** The L4 rate is **$0.0001867/s without zonal redundancy** or **$0.0002909/s with it**
  (third-party search excerpt of https://cloud.google.com/run/pricing ; the live page did not render
  the table, so the us-central1 row is **UNVERIFIED**). One always-on instance costs about
  **$485/month** for the GPU alone (≈ $755 with zonal redundancy), plus vCPU and memory. That is
  about $650–950/month before any traffic. At MVP volume this is 1,000×+ the per-minute vendors.
- **Latency:** Whisper is not a native streaming model. It transcribes whole utterances, so we
  would add client- or server-side VAD and endpointing ourselves, and partial events would be
  synthetic. The per-turn latency of large-v3 / faster-whisper on an L4 is **UNVERIFIED**. It must
  be benchmarked, and turbo/distil variants are likely needed to stay under ~500 ms.
- **GKE:** Same model and the same conflict, plus cluster operations. It is not justified at MVP
  scale (workspace stack rule: Kubernetes only when justified).
- **Verdict:** **Not recommended for the MVP.** It conflicts with §9, costs a fixed $650+/month, we
  would own streaming, VAD and the GPU fleet, and it still needs a TTS vendor. Revisit only if no
  vendor can meet DAT-4 in writing.

### 1(c) Whisper on Vertex AI Model Garden (now "Model Garden" in Agent Platform)

- **Existence:** No current official Google page listing a Whisper model card was found. Google's
  Model Garden docs show the general self-deploy flow (`gcloud ai model-garden models list` /
  `deploy`), with Gemma as the example:
  https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-garden/deploy-and-inference-tutorial .
  A third-party guide claims Whisper Large could be deployed from Model Garden in about 20–25 min
  (https://bitsector.notion.site/How-to-deploy-Whisper-LLM-for-speech-recognition-on-Google-s-Vertex-AI-197cfe2b2f5c8081bdd1ce4c49ea4f6c ,
  page did not render). Google's "OpenAI models on Vertex" page lists only gpt-oss MaaS models:
  https://cloud.google.com/vertex-ai/generative-ai/docs/maas/openai . **Current availability of
  Whisper in Model Garden: UNVERIFIED.** The owner can check with
  `gcloud ai model-garden models list --model-filter=whisper`.
- **Does it count as self-deployed?** **Yes.** An open model from Model Garden is deployed to a
  dedicated endpoint in *our* project on GPU machines that we choose and pay for by node-hour. It is
  not a managed per-call API (contrast Gemini or gpt-oss MaaS). It carries the same §9 conflict and
  the same always-on GPU cost and cold-start issues as 1(b). Its one advantage over 1(b) is that it
  stays inside the Google Cloud DPA perimeter.

---

## 2. Vendors outside Google and OpenAI

Seven vendors were screened. Five are shortlisted below. AWS is summarised at the end because it
fits worst with a GCP-only stack.

### 2.1 Deepgram

| Item | Finding | Source |
|---|---|---|
| STT | **Flux** (`flux-general-en`, `flux-general-multi`) is a conversational STT with model-integrated end-of-turn detection on WebSocket `/v2/listen`. **Nova-3** runs on `/v1/listen`. | https://developers.deepgram.com/docs/flux/quickstart |
| TTS | **Aura-2** (`aura-2-{voice}-en`) on `/v1/speak` is now called "previous generation". **Flux TTS** on `/v2/speak` (REST + WebSocket) is Early Access in the docs ("API surface and voice catalog may change"), while a changelog says it is GA in the Voice Agent API. | https://developers.deepgram.com/docs/flux-tts/overview , https://developers.deepgram.com/docs/flux-tts/migrating , https://developers.deepgram.com/changelog/2026/8/12 |
| No-training / retention | Training uses only data "contractually included" through the Model Improvement Partnership Program. Adding `mip_opt_out=true` to a request excludes it, and "data from opted-out requests is retained only for the duration necessary to process the request". The flag covers STT (streaming and batch), TTS (REST and streaming) and Voice Agent. Since **Mar 5, 2026**, opting out has "no impact on the rates" for PAYG and Growth. | https://developers.deepgram.com/docs/the-deepgram-model-improvement-partnership-program , https://developers.deepgram.com/changelog/2026/3/5 |
| How to enable | A **per-request API flag** that is self-serve on any paid tier. Our adapter must set it on every call, and a test should enforce that. | as above |
| DPA / BAA / FERPA | BAA for Enterprise (pricing page). A DPA is offered on request per a Deepgram community answer; no public DPA URL was found, so its status is **UNVERIFIED**. No FERPA or education terms were found (**UNVERIFIED**). | https://deepgram.com/pricing , https://community.deepgram.com/answers/en/deepgram-nova-2-model-europe-gdpr-compliance-1337814212071658666 |
| Streaming | Full-duplex WebSocket for both STT and TTS. Flux emits `EndOfTurn` and `EagerEndOfTurn` events. | quickstart above |
| Published latency | Flux: "~260 ms end-of-turn detection". Aura-2: sub-200 ms TTFB at launch, and about 90 ms steady-state with p95 < 200 ms (Deepgram engineering blog). | quickstart; https://developers.deepgram.com/changelog/2025/5/14 ; https://deepgram.com/learn/engineering-real-time-low-latency-voice-ai-at-scale |
| Price | Flux EN $0.0065/min PAYG ($0.0057 Growth). Nova-3 $0.0048/min. Aura-2 $0.030 per 1k chars. Flux TTS price not shown (**UNVERIFIED**). | https://deepgram.com/pricing |
| **Cost / 10-min session** | STT $0.033–0.065 + TTS $0.135 = **≈ $0.17–0.20** | computed |
| SDK | `pip install deepgram-sdk` (`AsyncDeepgramClient`, `client.listen.v2.connect`) and plain WebSocket/REST. | quickstart |
| Interface fit | **Excellent.** Flux takes `linear16` at 16 kHz natively (16 kHz is the recommended rate, in ~80 ms / 2,560-byte chunks), so no resampling is needed, and interim and final events map 1:1 to `TranscriptEvent`. Whether Aura-2 can output linear16 at 24 kHz is **UNVERIFIED** (check the TTS media-output docs). |  |
| Moderation | No content moderation of STT/TTS input is documented. **UNVERIFIED**, so test with the safeguard set. |  |

### 2.2 Microsoft Azure AI Speech (in Foundry Tools)

| Item | Finding | Source |
|---|---|---|
| STT | Real-time speech to text (Speech SDK / WebSocket), fast transcription and batch. | https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/speech-service/speech-to-text/data-privacy-security |
| TTS | Prebuilt neural voices, Neural HD and HD Flash voices. | https://azure.microsoft.com/en-us/pricing/details/speech/ |
| No-retention (default, written) | Real-time STT: "audio input is processed only on the Azure's server memory, and no data is stored at rest". For real-time STT and fast transcription, "Microsoft does not retain or store the data provided by customers." Real-time TTS: "Neither input text nor output audio content is stored in Microsoft logs" and "Microsoft doesn't retain or store the text". | STT page above; https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/speech-service/text-to-speech/data-privacy-security |
| No-training | Customer custom-voice training data "isn't used by Microsoft to train or improve any Microsoft text to speech voice models". For prebuilt real-time use, nothing is stored and so nothing is available to train on. An explicit no-training sentence for real-time STT audio was not found, so get it in writing from the DPA / Product Terms. | TTS page above |
| How to enable | **Default behaviour** for real-time APIs. No flag, no enterprise tier. Batch transcription is the exception: it stores files in customer or Microsoft storage with `timeToLive`, so do not use batch. | as above |
| DPA / FERPA | The Microsoft Products and Services **DPA** is incorporated into Azure agreements. In it, Microsoft "agrees to be designated as a 'school official' with 'legitimate educational interests'" under FERPA, and **Azure** is in scope. This is the **strongest written FERPA position found**. BAA via the Microsoft HIPAA BAA (standard Azure offering). | https://learn.microsoft.com/en-us/compliance/regulatory/offering-ferpa , https://aka.ms/dpa |
| Streaming | Full-duplex streaming STT through the Speech SDK (WebSocket underneath). Streaming TTS returns audio chunks. |  |
| Published latency | No official millisecond figure found (**UNVERIFIED**). The SDK exposes `SpeechServiceResponse_SynthesisFirstByteLatencyMs` for measurement. One user on Microsoft Q&A reports < 200 ms first-byte (anecdote). | https://learn.microsoft.com/en-gb/azure/ai-services/speech-service/how-to-lower-speech-synthesis-latency , https://learn.microsoft.com/en-us/answers/questions/1638490/reduce-latency-in-text-to-speech-microsoft-speedh |
| Price | The official page rendered "$-" placeholders. Third-party figures: real-time STT **$1.00/hr**, neural TTS **$15 per 1M chars** (HD about $22 per 1M per one aggregator). All **UNVERIFIED**; use the Azure pricing calculator. Free tier F0: 5 audio hrs STT and 0.5M TTS chars per month. | https://azure.microsoft.com/en-us/pricing/details/speech/ , https://costbench.com/software/ai-voice-tools/microsoft-speech/ |
| **Cost / 10-min session** | STT $0.083–0.167 + TTS $0.068 = **≈ $0.15–0.23** (third-party prices) | computed |
| SDK | `azure-cognitiveservices-speech` (Python Speech SDK), plus REST for TTS. |  |
| Interface fit | **Good.** STT natively accepts 16 kHz/16-bit mono PCM through a push stream. TTS offers raw 24 kHz 16-bit mono PCM output. The SDK is callback/thread-based, so the adapter must bridge it to `async` iterators (more glue than Deepgram). |  |
| Moderation | Content-safety classifiers are documented only for the **TTS avatar** (preview). None are documented for prebuilt-voice TTS or STT. | TTS page above |
| Caveat | This is a new cloud account and a new processor (DAT-5). Traffic crosses clouds from us-central1 to an Azure US region, so pick one near Iowa (for example, Central US). |  |

### 2.3 ElevenLabs

| Item | Finding | Source |
|---|---|---|
| STT | **Scribe v2 Realtime** (WebSocket), Scribe v2 (batch). The latency page also mentions Scribe v3 and **Scribe v3 Live**. | https://elevenlabs.io/docs/eleven-api/concepts/latency-methodology |
| TTS | **Eleven Flash v2.5**, Flash v2, **Eleven v4 Turbo**, Eleven v3 Conversational, Multilingual v2, v3. | same |
| Zero retention | **Zero Retention Mode (ZRM)**: "Enterprise customers can use Zero Retention Mode", "available to select enterprise customers", and access "may be restricted for high-risk use cases". It is enabled **per request with `enable_logging=false`** and covers all `/v1/text-to-speech/` and `/v1/speech-to-text/` endpoints plus the TTS WebSocket. **Without** ZRM, history is kept by default and backups and moderation logs can keep data. | https://elevenlabs.io/docs/developers/resources/zero-retention-mode |
| No-training | "By default, we don't train on any data from our Enterprise customers". Non-enterprise accounts use data to "improve the quality of our audio models for everyone" unless the user turns off a **Data use** toggle, and the opt-out applies to new data only. | https://elevenlabs.io/docs/help-center/legal/is-my-data-used-to-improve-eleven-labs-ai-models |
| How to enable | **Enterprise contract required** for ZRM, then a per-request API flag. A self-serve plan **fails DAT-4**. |  |
| DPA / BAA / FERPA | Enterprise: "custom terms and assurances around DPA and SLAs" and BAAs for HIPAA customers. No FERPA terms found (**UNVERIFIED**). | https://elevenlabs.io/pricing/api |
| Streaming | WebSocket STT and TTS (input streaming of text tokens). |  |
| Published latency | Server-side medians (they exclude the network): Flash v2.5 ~100 ms, v4 Turbo ~100 ms, v3 Conversational ~165 ms. Scribe v2 Realtime ~150 ms to committed transcript. Updated Oct 29, 2026. | latency page above |
| Price (self-serve list) | Flash/Turbo $0.04 per 1k chars, Multilingual v2/v3 $0.08 per 1k chars, Scribe v2 Realtime $0.22/hr. Enterprise prices are custom (**UNVERIFIED**). | https://elevenlabs.io/pricing/api |
| **Cost / 10-min session** | STT $0.018–0.037 + TTS (Flash) $0.18 = **≈ $0.20–0.22** at list prices | computed |
| SDK | `elevenlabs` Python SDK, plus REST and WebSocket. |  |
| Interface fit | Good. STT realtime accepts PCM at 16 kHz and TTS can return `pcm_24000` (format names **UNVERIFIED** against the current API reference). |  |
| Moderation risk | **Highest of the shortlist.** ElevenLabs runs moderation (moderation logs are mentioned on the ZRM page), and ZRM access can be restricted for "high-risk use cases". Whether crisis role-play text is blocked is **UNVERIFIED**. Confirm in writing and test with the safeguard set. | ZRM page |

### 2.4 AssemblyAI

| Item | Finding | Source |
|---|---|---|
| STT | `assemblyai-stt-3-7-realtime` ($0.30/hr) and `assemblyai-stt-3-7-realtime-agent` (for voice agents, $0.45/hr base). Universal-3.6 Pro Realtime is the previous generation, and Universal-Streaming is "replaced". **Streaming is billed on WebSocket session duration.** | https://www.assemblyai.com/pricing |
| TTS | **AssemblyAI-TTS-1**, launched **Oct 27, 2026**, $15 per 1M input characters. It is three weeks old, so its maturity is a risk. | same |
| No-training | "AssemblyAI will not use your Customer Data to train its artificial intelligence and machine learning models" applies under the opt-out. Signing a BAA auto-opts out, irreversibly. | https://www.assemblyai.com/docs/data-controls |
| Zero retention | "we offer zero data retention of audio and transcripts for our Streaming product" **for customers opted out of training**. Async files are deleted after 24–48 h by default (TTL down to 1 h). The page names TTS in the zero-retention group, but the opt-out FAQ does not confirm that the opt-out covers TTS (**UNVERIFIED**). | https://www.assemblyai.com/docs/data-retention-and-model-training |
| How to enable | **Email** `data-opt-out@assemblyai.com` from the account address. It is paid plans only ("Free users do not have the ability to opt out") and means "forgoing the discounts" on the pricing page. **Or** sign the self-serve BAA. | https://support.assemblyai.com/articles/5930031898-how-to-opt-out-of-data-sharing-for-model-training , pricing page |
| DPA / BAA / FERPA | A DPA is published (https://www.assemblyai.com/legal/data-processing-addendum). A BAA is "signable without a sales call". SOC 2 Type 2 and ISO 27001. No FERPA terms found (**UNVERIFIED**). | pricing page |
| Streaming | WebSocket STT with turn detection. TTS streaming support is **UNVERIFIED**. |  |
| Published latency | No STT-3.7 figure found. The previous Universal-3.5 Pro Realtime had **282 ms median / 354 ms p95** time-to-final-segment on Daily's Pipecat benchmark (AssemblyAI blog). TTS-1 latency **UNVERIFIED**. | https://www.assemblyai.com/blog/real-time-stt-latency-benchmarks-voice-agents |
| **Cost / 10-min session** | STT (Agent, session-billed) $0.0375–0.075 + TTS $0.068 = **≈ $0.11–0.14**. This is the cheapest option, before the opt-out discount loss. | computed |
| SDK | `assemblyai` Python SDK, plus REST and WebSocket. |  |
| Interface fit | Good for STT (pcm_s16le at 16 kHz is the streaming default). TTS output formats are **UNVERIFIED**. |  |

### 2.5 Cartesia

| Item | Finding | Source |
|---|---|---|
| STT / TTS | **Ink-2** STT (3 credits per second of audio) and **Sonic-3.6** TTS (1 credit per character). | https://cartesia.ai/pricing |
| Zero retention | ZDR is "available to Cartesia Enterprise customers" for TTS and STT APIs. When an org admin enables it in Playground settings, it applies to all eligible API requests. | https://docs.cartesia.ai/enterprise/zero-data-retention |
| No-training | No explicit no-training statement found (**UNVERIFIED**). Ask for it in the DPA. | https://cartesia.ai/legal/privacy |
| How to enable | **Enterprise contract**, then an org-level setting. |  |
| DPA / BAA | "DPAs and BAAs" on Enterprise. SOC 2 Type II. No FERPA terms found (**UNVERIFIED**). | pricing page |
| Latency | No figure verified this session (**UNVERIFIED**). |  |
| **Cost / 10-min session** | ~5,400–6,300 credits ≈ **$0.21–0.28** at Scale/Startup overage rates. The enterprise price is custom. | computed |
| Interface fit | Good (raw PCM output at configurable rates, **UNVERIFIED** for Ink-2 input). |  |

### 2.6 Amazon Transcribe + Polly (screened, not shortlisted)

- AWS AI services "may use and store customer content for service improvement ... or model
  training", and may store it **outside the Region in use**. **Transcribe and Polly** are both in
  the list covered by the Organizations **AI services opt-out policy**. Opting out deletes the
  historical content stored for improvement.
  Sources: https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_ai-opt-out.html ,
  https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_ai-opt-out_all.html
- It can pass DAT-4 with an org-level opt-out, but it adds a third cloud and AWS Organizations
  setup. Its prices and latency were not researched further.

### 2.7 Speechmatics

Not researched this session (time-boxed). **UNVERIFIED**, so it is not ranked.

---

## 3. Fact-check: "Vertex AI is now called Google Enterprise Agent Platform (GEAP)"

**Verdict: substantially true, but the name is slightly wrong.** The correct name is **Gemini
Enterprise Agent Platform**, not "Google Enterprise Agent Platform".

- **Source:** Gemini Enterprise Agent Platform release notes, entry dated **April 22, 2026**, titled
  "Vertex AI to Gemini Enterprise Agent Platform naming changes". It reads: "Vertex AI is now part of
  Gemini Enterprise Agent Platform." It was announced at Google Cloud Next '26.
  https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes
  Trade-press confirmation: https://www.theregister.com/2026/04/22/google_enterprise/ ,
  https://thenewstack.io/google-finally-builds-the-ai-and-agent-platform-its-been-describing-for-years/
- **"GEAP":** The abbreviation comes from third parties (for example, Revolgy's Jun 22, 2026 guide:
  https://www.revolgy.com/insights/blog/definitive-guide-to-gemini-enterprise-agent-platform-geap ).
  Google's own release notes use the short form **"Agent Platform"**.
- **Current names** (from the official mapping table in the release notes):

| Old name | Current name |
|---|---|
| Vertex AI Platform / Vertex AI API | **Agent Platform** / **Agent Platform API** |
| Vertex AI Prediction / Vertex AI Inference (model hosting) | **Agent Platform Inference** (Online / Batch Inference) |
| Vertex AI Endpoints | **Agent Platform Endpoints** |
| Vertex AI Model Garden | **Model Garden** |
| Gemini on Vertex AI | **Gemini on Agent Platform** |
| Vertex AI Studio | **Agent Studio** |
| Vertex AI Agent Engine | **Agent Runtime** |

- **Chirp STT is not affected.** Chirp 3 (`chirp_3`) is still documented as **Google Cloud
  Speech-to-Text API V2**. Its docs mention neither Vertex AI nor Agent Platform.
  https://docs.cloud.google.com/speech-to-text/docs/models/chirp-3
  - A side finding that matters to us: the docs list Chirp 3 as GA only in the **`us` and `eu`
    multi-regions**. **us-central1** is not listed as a region, so the Google baseline adapter
    should target the `us` multi-region (check whether that is acceptable for data-location
    wording).
- **Impact on our docs:** Repo docs that say "Vertex AI" are still understood, and the API and SDK
  were not broken by the rename (**UNVERIFIED** for SDK package names). On the next docs touch,
  write "Gemini on Agent Platform (formerly Vertex AI)" for accuracy. This is a docs change only,
  with no code impact.

---

## 4. Comparison summary

| Vendor | DAT-4 path | Enable by | Written DPA | FERPA terms | STT + TTS latency (vendor-published) | ≈ $/10-min session | Python | Fit |
|---|---|---|---|---|---|---|---|---|
| **Azure AI Speech** | Default: real-time not stored | Nothing (avoid batch) | Yes (MS DPA) | **Yes, "school official"** | Not published (**UNVERIFIED**) | $0.15–0.23 (3rd-party prices) | Speech SDK | Good (sync to async glue) |
| **Deepgram** | `mip_opt_out=true` means processing-only retention, no training | Per-request flag, self-serve | On request (**UNVERIFIED**) | None found | ~260 ms EoT + ~90–200 ms TTFB | $0.17–0.20 | `deepgram-sdk` | Excellent |
| **AssemblyAI** | Opt-out (or BAA), then streaming ZDR, no training | Email or self-serve BAA | Yes (published) | None found | ~282 ms p50 (prior model) + TTS **UNVERIFIED** | $0.11–0.14 | `assemblyai` | Good (TTS new) |
| **ElevenLabs** | ZRM + Enterprise no-training | **Enterprise contract** + `enable_logging=false` | Enterprise custom | None found | ~150 ms + ~100 ms (server-side) | ~$0.20–0.22 list | `elevenlabs` | Good (moderation risk) |
| **Cartesia** | Enterprise ZDR (training **UNVERIFIED**) | **Enterprise contract** + org setting | Enterprise | None found | **UNVERIFIED** | $0.21–0.28 | REST/SDK | Good |
| OpenAI (successor STT) | Approved ZDR | **Sales approval** | Yes | None found | Not published | STT $0.02–0.09 (+TTS TBD) | `openai` | STT only, 24 kHz resample |
| Self-hosted Whisper | Trivially true | n/a | n/a (GCP DPA) | via GCP | **UNVERIFIED**; batch per-turn | $650+/month fixed | n/a | Poor (no native streaming); **violates §9** |

All latency figures are vendor-reported and exclude the us-central1 to vendor round trip.
Every vendor must be measured in the bake-off from Cloud Run us-central1.

---

## 5. Recommendation

### Whisper

Do **not** pursue Whisper as such. `whisper-1` shuts down on Feb 26, 2027. Self-hosted and
Model Garden Whisper both violate POLICY §9, cost a fixed $650+/month, and lack native streaming.
If OpenAI is wanted, test **`gpt-live-transcribe`** as an STT-only candidate, and only after
OpenAI approves ZDR in writing.

### Ranked shortlist for the Phase 2 bake-off (#20)

Run the incumbent **Google Chirp 3 + Cloud TTS** as the control arm. The ranking is by DAT-4
certainty first, then latency, then FERPA, then cost.

1. **Deepgram (Flux STT + Aura-2, with Flux TTS as a variant)**: the best interface fit and the
   best published turn-taking latency. The no-training and processing-only retention terms are
   self-serve through a documented flag at no price change.
2. **Azure AI Speech (real-time STT + neural TTS)**: the strongest *written default* terms (real-time
   data is never stored) and the **only vendor with an explicit FERPA "school official" DPA**.
   It is a new cloud account, and its latency must be measured.
3. **AssemblyAI (STT-3.7-Realtime-Agent + TTS-1)**: the cheapest, with a published DPA and a
   self-serve BAA that locks in no-training. The TTS is three weeks old, so it may end up as an
   STT-only pick paired with another TTS.
4. **ElevenLabs (Scribe v2 Realtime + Flash v2.5 / v4 Turbo)**: the best published TTS latency and
   voice quality, but **it passes DAT-4 only with an Enterprise contract**, and it carries a
   moderation and "high-risk use" restriction risk for crisis role-play. Include it only if the
   owner is willing to start an enterprise conversation.
5. *(Reserve)* **Cartesia**: Enterprise-only ZDR, and a no-training term is still needed.

### What the owner must obtain in writing, per vendor (before DAT-6 allows any real student session)

- **Every vendor (DAT-5):** a written data-use record, an owner decision adding the processor, a
  signed DPA, the sub-processor list, and a statement that session audio and text are **not
  retained beyond processing and not used for training**. That statement must cover *both* the STT
  and TTS endpoints we call. Also get a clause on content moderation: either the vendor does not
  block, or it gives notice before blocking, self-harm role-play text.
- **Deepgram:** (a) a signed DPA (none is public), (b) written confirmation that `mip_opt_out=true`
  means no retention beyond the request for streaming `/v2/listen` and for `/v1/speak` or
  `/v2/speak`, and that this covers abuse/debug logs, (c) a FERPA school-official addendum if the
  owner wants FERPA alignment.
- **Azure:** (a) acceptance of the Microsoft Products and Services DPA through the Azure agreement,
  with its FERPA school-official clause, (b) a written no-training statement for real-time STT
  audio, from the DPA or Product Terms, (c) a choice of Azure region and a confirmation that
  batch/Long-Audio APIs are not used.
- **AssemblyAI:** (a) the confirmation email for the training opt-out *or* an executed BAA,
  (b) written confirmation that streaming ZDR and the opt-out cover **TTS-1**, (c) a signed DPA and
  a FERPA addendum.
- **ElevenLabs:** (a) an Enterprise agreement that enables **Zero Retention Mode** for STT and TTS,
  (b) contractual no-training, (c) written confirmation that counseling crisis role-play is not a
  restricted "high-risk use case" and is not moderated or blocked, (d) a DPA and a FERPA addendum.
- **Cartesia (if used):** an Enterprise agreement with ZDR enabled, an explicit no-training clause,
  and a DPA.
- **OpenAI (if used):** OpenAI's written **ZDR approval** for the org/project, confirmation that it
  covers Realtime transcription sessions (`gpt-live-transcribe`), and an executed DPA.

### Notes for OQ-01 (transport)

All four ranked vendors offer full-duplex WebSocket STT with server-side turn detection (except
OpenAI's `gpt-live-transcribe`, which needs client VAD) and streaming TTS. The streaming
`SpeechProvider` interface fits all of them without change, so the transport decision does not
narrow the vendor list.
