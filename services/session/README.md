# Session service

Holds the practice-session logic (ARCHITECTURE §3). So far it contains the replaceable speech
provider interface from #64, the Deepgram bake-off adapter from #101 and the completed-session
handoff contract from #66. The HTTP layer, signed state and persona turns come with #31.

## Layout

| Path | What it is |
|---|---|
| `cst_session/speech/interface.py` | The `SpeechProvider` protocol, transcript events and the audio format contract |
| `cst_session/speech/errors.py` | Typed errors: provider unavailable, timeout, unsupported audio |
| `cst_session/speech/fake.py` | `FakeSpeechProvider`, which plays scripted responses and simulates latency and each error |
| `cst_session/speech/adapters/` | Vendor adapters. The only place a vendor speech SDK or `websockets` may be imported (`tests/test_speech_import_boundary.py`) |
| `cst_session/speech/adapters/deepgram.py` | `DeepgramSpeechProvider`: Flux speech-to-text and Aura-2 text-to-speech, a #20 bake-off candidate (#101). Synthetic data only, see `docs/decisions/speech-deepgram.md` |
| `cst_session/speech/adapters/deepgram_transport.py` | The adapter's network transport, over `websockets` and `httpx` |
| `cst_session/handoff/contract.py` | The completed-session handoff models, version 1.0.0. The payload the grader accepts (#66, `handoff/README.md`) |
| `cst_session/handoff/validation.py` | `parse_handoff` and `validate_handoff`: accept a completed session or raise `HandoffRejected` with one fixed reason, logging content-free. `encode_handoff` writes the body the session service sends |
| `cst_session/handoff/export.py` | Writes `handoff/completed-session.v1.schema.json`. Run `uv run python -m cst_session.handoff.export` after changing the models |
| `tests/test_handoff_contract.py`, `tests/test_handoff_logging.py`, `tests/test_handoff_schema.py` | Run every fixture in `handoff/fixtures/v1/`, prove validation logs no turn text or UID, and fail when the committed schema is stale |
| `cst_session/content_free_log.py` | The content-free logging helper. A byte-identical copy of the accounts service's canonical module; see "Logging" |
| `tests/test_content_free_log_copies.py` | Fails when this copy drifts from `services/accounts/cst_accounts/content_free_log.py` |
| `tests/test_logging_calls.py` | Fails on a root-logger lookup or a direct `sys.stdout`/`sys.stderr` write outside the helper |
| `tests/test_scenario_write_paths.py` | Fails when any service declares a non-read route for scenarios, or the scenarios package writes a file |
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

## Scenarios

The library and preparation screens read `Catalogue.library()`. Session start must call
`Catalogue.startable(scenario_id)` and refuse on `ScenarioUnavailable`, which is raised the same way
for an unknown id and an unreleased one, so a scenario held back under CD-3 can't be probed. `startable()`
checks only the release flag. Session start must also refuse a scenario with `requires_opt_in`
unless the student's explicit opt-in arrives with the request, checked on the server (SES-2). Load
the catalogue once at startup: a malformed config raises `CatalogueError` and stops the service.
The time limit comes from `time_limit_minutes`, which is 10 for every scenario (PA-5). The owner
approves the release flags (POLICY §1). The ids match `rubric/anchor-spec.v1.json`, and the
logging helper accepts only these three as `scenario_id`.
