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
| `cst_session/speech/adapters/` | Vendor adapters. The only place a vendor speech SDK or `websockets` may be imported (`tests/test_speech_import_boundary.py`) |
| `cst_session/speech/adapters/deepgram.py` | `DeepgramSpeechProvider`: Flux speech-to-text and Aura-2 text-to-speech, a #20 bake-off candidate (#101). Synthetic data only, see `docs/decisions/speech-deepgram.md` |
| `cst_session/speech/adapters/deepgram_transport.py` | The adapter's network transport, over `websockets` and `httpx` |
| `cst_session/content_free_log.py` | The content-free logging helper. A byte-identical copy of the accounts service's canonical module; see "Logging" |
| `tests/test_content_free_log_copies.py` | Fails when this copy drifts from `services/accounts/cst_accounts/content_free_log.py` |
| `tests/test_logging_calls.py` | Fails on a root-logger lookup or a direct `sys.stdout`/`sys.stderr` write outside the helper |
| `tests/speech_contract.py` | `SpeechProviderContract`, the suite every adapter must pass |
| `tests/test_speech_import_boundary.py` | Fails when a vendor speech SDK or `websockets` is imported outside `adapters/`, or a module that handles session content imports logging or storage |
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

## Logging

Log only through `cst_session/content_free_log.py` (POLICY DAT-1, DAT-7): `log_event("event_name", **fields)`, or `log_error("event_name", exc, code="stable_code", **fields)` in an error path. Only allow-listed, well-typed fields are written, and errors carry the exception class and stable code only. Never log a turn, a persona reply, a transcript, a name, an email or a token. The full field list is in the module docstring and `services/accounts/README.md`. The module also holds `ContentFreeErrors`, the ASGI middleware that answers an unhandled error with the generic 500 (or a 1011 websocket close) and logs it by class only. Ruff's `T20` and `LOG015` rules and `tests/test_logging_calls.py` reject `print`, the root logger (including `logging.root`) any use of the std streams outside the helper, and `os.write`. Importing `logging`, `traceback` or `warnings` is allowed only in the files on that test's allow-list, each with its reason; today that is `cst_session/speech/adapters/deepgram_transport.py`, which silences the websockets client.

Do not edit this copy. Change the canonical file in `services/accounts/cst_accounts/`, then copy it here in the same PR.

## Commands

```sh
uv sync --python 3.12
uv run pytest
uv run ruff check .
uv run mypy .
```
