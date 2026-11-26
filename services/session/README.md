# Session service

Holds the practice-session logic (ARCHITECTURE §3). So far it contains the replaceable speech
provider interface from #64, the Deepgram bake-off adapter from #101 and the completed-session
handoff contract from #66. #31 added the text-session API: signed stateless session state,
persona turns through Gemini Enterprise Agent Platform, and an end that builds the handoff. The
service keeps no session content: the whole conversation travels in the signed `state` token.

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
| `cst_session/api.py` | `create_app`: `/health`, `POST /v1/sessions`, `/v1/sessions/turns` and `/v1/sessions/end`, the approval guard, the fixed error codes, and `RequestLimits` (no query string, 1 MiB body cap) |
| `cst_session/main.py` | `Settings` and `app_factory`, which refuses a bad key, origin or persona setting before creating any cloud client |
| `cst_session/identity/` | The token and approval check, copied verbatim from `services/accounts` (`tests/test_identity_copy.py` fails on drift). Reads only |
| `cst_session/lifecycle.py` | `Sessions`: start, turn and end, the time limit, the 60 s end grace and the handoff |
| `cst_session/state.py` | `StateCodec`: the HMAC-signed session state, its caps and the key decoder |
| `cst_session/persona/port.py` | `PersonaPort`, `PersonaUnavailable` and its fixed failure codes |
| `cst_session/persona/agent_platform.py` | The Agent Platform REST adapter: `us` endpoint only, a typed three-key request, ADC tokens, a 20 s deadline, no retries |
| `cst_session/grading.py` | `GraderPort` and `UnavailableGrader`. Every session ends `unscored` until #68 |
| `cst_session/scenarios/prompts/` | One vetted, fictional persona prompt per scenario, and `manifest.toml` with each prompt's version and SHA-256 (#67, `prompts/README.md`) |
| `harness/` | The dev-only persona harness (#67): `scripts/*.toml` synthetic counselor scripts, `checks.py` deterministic checks and `run.py`. Not in the image; see "Live persona checks (owner-run)" |
| `tests/test_harness_script.py`, `tests/test_harness_checks.py`, `tests/test_harness_run.py` | The script loader, every check anchor and its false positives, and the runner with a fake persona |
| `tests/live/test_live_personas.py` | Marked `live`: every script against the real model. Skipped by the default `uv run pytest` |
| `cst_session/content_free_log.py` | The content-free logging helper. A byte-identical copy of the accounts service's canonical module; see "Logging" |
| `tests/test_content_free_log_copies.py` | Fails when this copy drifts from `services/accounts/cst_accounts/content_free_log.py` |
| `tests/test_logging_calls.py` | Fails on a root-logger lookup or a direct `sys.stdout`/`sys.stderr` write outside the helper |
| `tests/test_scenario_write_paths.py` | Fails when any service or the harness declares a non-read route for scenarios, or the scenarios package or the harness writes a file |
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

Log only through `cst_session/content_free_log.py` (POLICY DAT-1, DAT-7): `log_event("event_name", **fields)`, or `log_error("event_name", exc, code="stable_code", **fields)` in an error path. Only allow-listed, well-typed fields are written, and errors carry the exception class and stable code only. Never log a turn, a persona reply, a transcript, a name, an email or a token. The full field list is in the module docstring and `services/accounts/README.md`. The module also holds `ContentFreeErrors`, the ASGI middleware that answers an unhandled error with the generic 500 (or a 1011 websocket close) and logs it by class only. Ruff's `T20` and `LOG015` rules and `tests/test_logging_calls.py` reject `print`, the root logger (including `logging.root`) any use of the std streams outside the helper, and `os.write`. Importing `logging`, `traceback` or `warnings` is allowed only in the files on that test's allow-list, each with its reason; today that is `cst_session/main.py`, which raises the httpx and httpcore log level, and `cst_session/speech/adapters/deepgram_transport.py`, which silences the websockets client.

Do not edit this copy. Change the canonical file in `services/accounts/cst_accounts/`, then copy it here in the same PR.

## Commands

```sh
uv sync --python 3.12
uv run pytest
uv run ruff check .
uv run mypy .
```

`uv run pytest` skips tests marked `live` (`addopts` in `pyproject.toml`).

## Running

The container runs `uvicorn cst_session.main:app_factory --factory --no-access-log` on port 8080.
Uvicorn's access log is off because request lines are not written through the content-free helper.
Startup reads these variables and stops if any is missing or not allowed:

| Variable | Meaning |
|---|---|
| `CST_PROJECT_ID` | The GCP project, for Identity Platform, Firestore and the persona call |
| `CST_PERSONA_MODEL` | The approved persona model, `gemini-3.8-flash` (OD-2; Terraform pins it) |
| `CST_AGENT_PLATFORM_LOCATION` | Must be `us`. `global` and every other value stop startup (ARCHITECTURE §6) |
| `CST_STATE_SIGNING_KEY` | Base64url text that decodes to exactly 32 bytes, from Secret Manager (`infra/session-grading/bootstrap_signing_key.py`) |
| `CST_ALLOWED_ORIGINS` | A JSON list of exact origins. `*` and `null` stop startup |

Regenerate `requirements.txt` after changing dependencies, from the repo root:
`uv export --project services/session --no-dev --no-emit-project --format requirements-txt --output-file services/session/requirements.txt`.

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

## Live persona checks (owner-run)

The harness runs the four synthetic counselor scripts in `harness/scripts/` through the real
lifecycle and the real persona model, then checks every reply: the client stays in character and on
the scenario, the routine and resistant clients raise no risk, and the crisis client hints at risk
early, answers a direct question, never names a method or means and keeps talking after a
disclosure (#67). Only the owner runs it, on their own machine.

Prerequisites:

- The Google Cloud CLI in an absolute `PATH` directory (relative entries are skipped), logged in
  with `gcloud auth login` as an account with access to the dev project. The harness asks `gcloud`
  for an access token, holds it in memory only and never prints it. A `gcloud` that takes more than
  15 seconds is killed along with its child processes. It needs no Application Default Credentials.
- The dev project only. The project comes from `infra/environments/development.json`. The model is
  always the `persona_model` pin in `infra/session-grading/main.tf`: `CST_PERSONA_MODEL` may only
  repeat it. The location comes from `CST_AGENT_PLATFORM_LOCATION` or else the pin. A missing or
  disallowed setting, including another model or `global`, stops the harness with exit code 2
  before any call.
- Synthetic scripts only. Never put a real client, name or case in a script (PA-3).

From `services/session`:

```sh
uv run python -m harness.run --repeat 3
uv run pytest -m live
```

`--scenario SCRIPT_ID` (repeatable) runs only `routine_intake`, `resistant_client`, `crisis_risk`
or `crisis_risk_missed_cues`. `--repeat` takes 1 to 10 and defaults to 3.

What the output shows: for each script, a header line with the script, its scenario, the prompt
version, the model, the location, the UTC time and the repeat count. Then one line per check,
`PASS`, `FAIL` or `INFO`, with the runs it passed out of the total and summed counts. `INFO` lines
are report-only and never fail a run. In `crisis_risk_missed_cues`, `on_scenario` is report-only
(`report_only = true` in its script): that counselor pulls the client off topic on purpose, and its
safety checks still gate it. A scenario's own script can't set it. A run that couldn't finish, for example
`FAIL unavailable(persona_timeout)` or `FAIL start_refused(scenario_unavailable)`, gets its own
line. `not_blocked` fails when the model's safety filter refused a turn. The exit code is 0 only
when every gating check passed on every repeat. The report never holds a reply, a prompt or a
script turn, and the lifecycle's content-free log lines go to stderr.

Never commit live output. Paste the check lines, never replies, into the PR that changes a prompt
(`cst_session/scenarios/prompts/README.md`).
