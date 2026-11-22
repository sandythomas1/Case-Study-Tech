# Session service

Holds the practice-session logic (ARCHITECTURE §3). So far it contains the replaceable speech
provider interface from #64 and the Deepgram bake-off adapter from #101. The HTTP layer, signed
state and persona turns come with #31.

## Layout

| Path | What it is |
|---|---|
| `cst_session/speech/interface.py` | The `SpeechProvider` protocol, transcript events and the audio format contract |
| `cst_session/speech/errors.py` | Typed errors: provider unavailable, timeout, unsupported audio |
| `cst_session/speech/fake.py` | `FakeSpeechProvider`, which plays scripted responses and simulates latency and each error |
| `cst_session/speech/adapters/` | Vendor adapters. The only place a vendor speech SDK or client may be imported |
| `cst_session/speech/adapters/deepgram.py` | `DeepgramSpeechProvider`: Flux speech-to-text and Aura-2 text-to-speech, a #20 bake-off candidate (#101). Synthetic data only, see `docs/decisions/speech-deepgram.md` |
| `cst_session/speech/adapters/deepgram_transport.py` | The adapter's network transport, over `websockets` and `httpx` |
| `tests/speech_contract.py` | `SpeechProviderContract`, the suite every adapter must pass |
| `tests/test_speech_import_boundary.py` | Fails when a vendor speech SDK is imported outside `adapters/` |
| `tests/deepgram_fakes.py` | A scripted fake Deepgram network that records every request |

## Audio contract

Raw PCM, signed 16-bit little-endian, mono, no header. Transcription takes 16 kHz audio and synthesis
returns 24 kHz audio. The full contract is in the `interface.py` docstring.

## Adding an adapter

1. Add the module under `cst_session/speech/adapters/`. The vendor itself needs an owner decision
   and a zero-retention record first (ARCHITECTURE §8, POLICY DAT-5).
2. In `tests/`, subclass `SpeechProviderContract` as `Test<Adapter>Contract` and implement
   `make_provider` against a stubbed transport. Tests use generated audio only.
3. If the vendor's SDK is not yet in `VENDOR_SPEECH_MODULES`, add it.

## Commands

```sh
uv sync --python 3.12
uv run pytest
uv run ruff check .
uv run mypy .
```
