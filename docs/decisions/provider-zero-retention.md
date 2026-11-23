# Provider zero-retention and no-training terms

**Status:** Draft, 2026-11-22, #19. **Not approved.** No provider is cleared for session content yet.
Until the owner records written confirmation below, development uses synthetic data only (plan PA-3),
and a missing Vertex AI confirmation at the release gate holds the release (CD-2).

**Rules this record applies:** RC-05, DD-04, OQ-02 · POLICY DAT-4 (written terms and settings that forbid
retention and training, otherwise reject) and DAT-5 (no new processor without an owner decision) ·
plan PA-3, CD-1, CD-2.

**Evidence:** `specs/019-provider-zdr-terms/research.md` has every quote and source URL, all read on
2026-11-22. Vendor pages change without notice, so re-read them before anyone signs.

## Status by provider

"Published terms" means the vendor's public pages, with their URL and the date read. "Written
confirmation" means a signed agreement or a vendor reply on this project's account.

**What counts as written terms (owner decision, 2026-11-22; PA-3, DAT-4):**
- If a service's terms don't depend on which agreement or tier we're on (Google Speech-to-Text and
  Text-to-Speech), published terms plus dated evidence that the required settings are applied are enough.
  No vendor contact is needed.
- Vertex AI is different. Its prompt logging depends on the agreement, so it needs written confirmation:
  either a Google reply granting the abuse-monitoring exemption, or proof that the account is on a Master
  Agreement. That takes one Google support case.

A row turns **Confirmed** only once its condition is met and the evidence is recorded here.

| Provider and use | Published terms allow RC-05? | Written confirmation | Settings applied | Verdict |
|---|---|---|---|---|
| Vertex AI Gemini, personas and grader (`us` multi-region) | **Only with caching disabled (setting 1) and an abuse-monitoring exemption.** Implicit caching is on by default and includes a durable at-rest tier. No training (SST §18). No storage past output (SST §20(h)). But on the online Cloud terms, Google may keep prompts its safety classifiers flag for up to 90 days, with human review (ToS §4.3). Master Agreement customers are exempt by default. | Not requested | Settings 1, 3 and 8 verified 2026-11-23. Setting 2 waits for the owner's `check` and console screenshot, setting 7 for the `us` apply. Settings 4–6 are code rules with no caller yet (`vertex-ai-governance.md`) | **Pending**. Needs the exemption or a Master Agreement in writing. |
| Vertex AI Frontier models (SST §34: Gemini 4 Carbon, Gemini 4 Carbon for cyber, Gemini 4 Argon Cyber Permissive) | No. Prompts and responses are logged for up to 30 days (SST §34). | n/a | n/a | **Rejected** for session content. #65 must not pick them. |
| Partner models on Vertex Model Garden (OpenAI, Anthropic and other "Advanced AI" models) | No, unless the partner's own ZDR is approved. Otherwise prompts are logged for 30 days. | n/a | n/a | **Rejected** for session content |
| Gemini Live / native audio on Vertex (speech path option) | Same as Vertex AI above, plus session resumption caches for up to 24 h if enabled | Not requested | No | **Pending**, same as Vertex AI |
| Google Cloud Speech-to-Text V2, Chirp 3, streaming or sync | **Likely, see open items 4 and 5.** Audio is processed in memory only, and data logging (which allows training) is opt-in and off by default. It is unverified whether ToS §4.3 abuse logging applies, and whether the data-logging control covers V2 / Chirp 3. **Region:** Chirp 3 runs in the `us` multi-region, per the owner decision of 2026-11-22 (ARCHITECTURE §6 exception). | Not needed (published terms) | No | **Pending** dated settings evidence (settings 9, 10, 12) and the §4.3 answer from the Vertex support case |
| Google Cloud Speech-to-Text batch recognition | No. Transcripts are kept about 5 days. | n/a | n/a | **Rejected** for session content |
| Google Cloud Text-to-Speech, standard and Chirp 3 HD voices | **Retention: yes.** Google states it logs no TTS text or audio and the service is stateless. **Training: by inference only.** The TTS page has no explicit no-training sentence, so this relies on SST §18. Whether §4.3 applies is unverified. | Not needed (published terms) | Nothing to set | **Pending** the §4.3 answer from the Vertex support case |
| Google Cloud Text-to-Speech, Gemini-TTS voices | Unknown. They may fall under Gemini abuse monitoring. | Not requested | n/a | **Pending**. Not to be used until confirmed. |
| Deepgram Flux STT (`/v2/listen`) and Aura-2 TTS (`/v1/speak`), #101 | **Only with `mip_opt_out=true` (setting 13), and unconfirmed in writing.** Deepgram documents that opted-out data is kept only as long as needed to process the request and is not used for model improvement. A signed agreement, the sub-processor list and permission for simulated self-harm role-play are not yet requested. See `speech-deepgram.md`. | Not requested (#101 AC4) | Set in code on every request; no key exists until #18 | **Pending**. Approved by the owner on 2026-11-22 for synthetic-data benchmarking only (DAT-6). No session content. |
| Anthropic Claude, calibration-set drafting (CD-5), #47 | Not assessed. #47 sets the access path, the account holder and the terms, and records them here before the first call. | Not requested | None yet | **Pending**. Approved by the owner on 2026-11-22 for synthetic transcripts only (DAT-5). It never receives student data or session content. No call until this row is filled. |
| OpenAI (all speech models) | Assessed in `research.md`: file transcription likely meets RC-05 by default; Realtime and speech output need ZDR or MAM approval | n/a | n/a | **Dropped by owner decision, 2026-11-22.** The speech candidates are Google, Deepgram (#101) and Azure (#102). Not to be used. |

No provider is used for session content until its row says **Confirmed**, with the date and where the
evidence or signed terms are stored. #115 tracks that.

## Required settings

The owner applies these now that the GCP baseline (#18) exists. Settings 1–8 belong to #65, and their
evidence is recorded in `vertex-ai-governance.md`. Settings 9–12 belong to #115 and are recorded here.
Each one needs evidence: API output or a dated console screenshot. Settings 1, 3 and 8 have it
(2026-11-23); settings 2 and 7 wait for the owner's run. Settings 9–12 are not applied yet.

**Vertex AI (project-wide)**
1. Turn off implicit caching: `PATCH https://aiplatform.googleapis.com/v1/projects/<PROJECT_ID>/cacheConfig`
   with `{"name":"projects/<PROJECT_ID>/cacheConfig","disableCache":true}`. Verify with a `GET` on the same
   URL that it shows `disableCache: true`. The research found no Terraform resource for it (unverified),
   so #65 applies it with `infra/session-grading/vertex_governance.py disable-cache`, which calls this URL.
2. Leave request-response logging off (the default) for every model.
3. Create no explicit context caches.
4. Use no Grounding with Google Search or Google Maps. Their logs can't be turned off.
5. Send `store=false` on any Interactions API call, because the default is `true`.
6. Don't turn on Live API session resumption.
7. Call the `us` multi-region endpoint, `https://aiplatform.us.rep.googleapis.com`, never `global`. The
   #65 probe found neither pinned model on `us-central1` (HTTP 404), so the owner's fallback applies
   (owner decision 2026-11-22, `vertex-ai-governance.md`, ARCHITECTURE §6 exception).
8. Keep session content out of batch prediction. Its inputs and outputs persist in our buckets (RC-03).

**Speech-to-Text and Text-to-Speech**
9. Keep Speech-to-Text data logging off: *APIs & Services › Cloud Speech API › Data logging*. A dated
   console screenshot is the only evidence available.
10. Use only streaming or sync recognition, never `BatchRecognize`.
11. Use standard or Chirp 3 HD voices, not Gemini-TTS, until it is confirmed.
12. If Chirp 3 is used, call the `us` multi-region endpoint (ARCHITECTURE §6 exception). Vertex AI also
    uses `us` (setting 7). Everything else stays in `us-central1`.

**Deepgram**
13. Send `mip_opt_out=true` on every `/v2/listen` and `/v1/speak` request. The adapter adds it to every URL
    it builds, and `services/session/tests/test_deepgram_speech.py` fails if any request lacks it. The key
    goes only in the `Authorization` header.

## Request to send

Send one Google Cloud support case, about Vertex AI. You can skip it if the billing account turns out to be
on a Master Agreement. `specs/019-provider-zdr-terms/research.md` has fuller wording. Keep the case to:

- if we're on the online terms, grant an exemption from abuse-monitoring prompt logging for this project
  (the simulated crisis dialogue is by design);
- confirm that `disableCache` removes both cache tiers;
- while open, say whether Speech-to-Text, Chirp 3 and Gemini-TTS fall under ToS §4.3.

Signed documents and vendor replies are stored outside the repo. Record their location here, not the
documents themselves.

## Open items

1. Can online-terms customers still ask for the Vertex abuse-monitoring exemption? The public pages no
   longer say. This decides whether CD-2 holds the release.
2. Is the project's Google Cloud account on the online terms or a Master Agreement? Only the owner knows.
3. **Closed 2026-11-23 (#65).** Which current GA Gemini models serve regionally in `us-central1`? Neither
   pinned model does: the probe got HTTP 404 on `us-central1` and HTTP 200 on `us`. Vertex AI uses the
   `us` multi-region (`vertex-ai-governance.md`, "Region probe").
4. Do STT data-logging controls apply to Speech-to-Text V2 / Chirp 3?
5. Are Speech-to-Text, Chirp 3 and Gemini-TTS "Generative AI Services" under ToS §4.3?
6. Is the Google Cloud Data Processing Addendum auto-accepted for online-terms customers?

## Owner decisions

- **2026-11-22: What counts as written terms.** For Google speech, published terms plus dated settings
  evidence. For Vertex, one support case or a Master Agreement. See "Status by provider".
- **2026-11-22: #19 split.** #19 covers recording the terms status and documenting the settings. The
  follow-up Issue, #115, covers the Vertex confirmation, the applied settings and the final verdict for each row.
- **2026-11-22: #65 and #115 split.** "#65 owns Vertex 1–8 (Recommended)". #65 owns the model choice,
  region, IAM, governance record and Vertex settings 1–8. #115 keeps the support case, speech settings
  9–12 and the final verdicts.
- **2026-11-22: OD-2.** Personas use `gemini-3.8-flash` and the grader uses `gemini-4-argon`. Neither is
  an SST §34 Frontier model. `vertex-ai-governance.md` records the decision.
- **2026-11-22: Anthropic recorded before use.** "Add a Pending row now (Recommended)". The Anthropic
  row above is the ARCHITECTURE §8 zero-retention record for calibration drafting. It stays Pending,
  and nothing calls Anthropic, until #47 fills in the access path and terms.
- **2026-11-22: OpenAI dropped** as a speech candidate. Google, Deepgram (#101) and Azure (#102) remain.
  Plan line 204 (OpenAI and Google adapters) and the CD-1 swap target still name OpenAI. They need a
  follow-up update.
- **2026-11-22: Deepgram synthetic-only.** The Deepgram adapter (#101) may merge and be benchmarked with
  synthetic audio and scripted text only, with its row above at Pending. This row is the AG-3 zero-retention
  record for it. Real session content waits for written terms (#101 AC4) and a Confirmed row.
- **2026-11-22: Chirp 3 region.** If Chirp 3 is used, it runs in the `us` multi-region. ARCHITECTURE §6
  records this exception.
- **2026-11-22: Vertex AI region.** "Probe, then fall back to us (Recommended)". The probe failed on
  `us-central1` (2026-11-23), so Vertex AI runs in the `us` multi-region. ARCHITECTURE §6 records this
  exception too.
