# Speech provider candidate: Deepgram

**Status:** Bake-off candidate for #20, approved by owner 2026-11-22 for **synthetic data only**
(POLICY DAT-5, DAT-6), #101. It is not a provider selection. Selection needs the #20 ADR, an
owner decision and Deepgram's written terms (#19).

## What it is used for

`services/session/cst_session/speech/adapters/deepgram.py` implements the #64 `SpeechProvider`
interface:

| Use | Model | Endpoint | Audio |
|---|---|---|---|
| Speech-to-text, streaming | Flux, `flux-general-en` | `wss://api.deepgram.com/v2/listen` | 16 kHz `linear16` in |
| Text-to-speech | Aura-2, `aura-2-<voice>-en` (default `thalia`) | `POST https://api.deepgram.com/v1/speak` | 24 kHz `linear16`, `container=none` out |

Out of scope: Flux TTS (Early Access), Deepgram Voice Agent and any speech-to-speech mode.

## Data Deepgram would see

The student's speech audio (STT) and the persona's reply text (TTS). Nothing else: no name, email,
account ID or session ID is sent. Until a provider is selected, only generated audio and scripted
text from test accounts may be sent (DAT-6).

## Required settings

- `mip_opt_out=true` on **every** request, on both endpoints. Deepgram documents that opted-out
  data is kept only as long as needed to process the request and is not used for model
  improvement. The adapter builds every URL through one function that adds it, and
  `tests/test_deepgram_speech.py` fails if any recorded request lacks it.
- The API key is sent only in the `Authorization: Token` header, never in a URL, a log line or a
  `repr`. The transport gives `websockets` a silenced logger that sits outside the logging
  registry, because its debug output includes the handshake headers and frame payloads; later
  logging config cannot switch it back on. `tests/test_deepgram_transport.py` checks that no
  client log record contains the key, the transcript or the synthesis text (DAT-7), and
  `tests/test_speech_import_boundary.py` keeps `websockets` inside `adapters/`.
- The key belongs in Secret Manager, readable only by the session service account, and never in the
  client. That project does not exist until #18, so no key is stored or loaded yet. The adapter
  takes the key as a constructor argument and has no loader.

## Client choice

Owner decision, 2026-11-22: use `httpx` and `websockets` behind a `DeepgramTransport` seam, not
`deepgram-sdk`. The two endpoints are a WebSocket and one POST, so the SDK adds a large dependency
for little code saved. The seam lets the tests record every request without a network, and keeps
both libraries inside `adapters/`.

## Network egress

The session service connects out to `api.deepgram.com` on 443 (WSS and HTTPS). No inbound access.

## Open, needs the owner (HUMAN ACTION)

1. **Live benchmark (#101 AC3).** Run #20's scripted synthetic session (30+ turns, device and web)
   with a Deepgram test key from Secret Manager once #18 exists. It also confirms three behaviors
   the docs leave unclear and the adapter handles defensively:
   - what Flux sends after `CloseStream` (the adapter accepts a manual `EndOfTurn` or a normal close);
   - the Aura-2 response content type for `container=none` (the adapter fails safe on anything but
     24 kHz `audio/l16`);
   - how a rejected key shows on the WebSocket upgrade (mapped to provider unavailable).
2. **Written terms (#101 AC4).** Request a signed data agreement, no retention and no training
   covering `/v2/listen` and `/v1/speak`, a sub-processor list, and permission to process simulated
   self-harm role-play. Update the Deepgram row in `provider-zero-retention.md` (#19), which is the
   AG-3 zero-retention record and stays **Pending** until then.
