# Verification: Content-free logging helper (#63)

QA run 2026-11-23 on `feature/63-content-free-logging` (uncommitted working tree, base origin/dev db68e91).
Native Windows, uv, Python 3.12. All test data is synthetic (`SYNTHETIC-TURN: I feel hopeless`,
`student-a`, `student-a@example.com`).

## Acceptance criteria

| AC | Test(s) that prove it | Command | Result | Evidence |
|---|---|---|---|---|
| AC1: a non-allow-listed field (`transcript`, `text`) never emits its value | `services/accounts/tests/test_content_free_log.py::test_a_field_outside_the_allow_list_never_emits_its_value[transcript,text,body,email,name]`; `::test_a_wrong_typed_or_malformed_value_is_dropped` (17 cases, including the turn text passed as `session_id`); `::test_the_helper_cannot_be_used_to_set_reserved_keys`; `::test_an_invalid_event_name_is_replaced_and_never_emitted`. The same module runs in session: `services/{accounts,session}/tests/test_content_free_log_copies.py::test_every_copy_matches_the_accounts_copy_byte_for_byte` | `uv run --frozen pytest -v tests/test_content_free_log.py` (accounts); `uv run --frozen pytest -v tests/test_content_free_log_copies.py` (both) | PASS | 36/36 passed (accounts), 2/2 copy tests in each service. Mutation M1 makes 23 of them fail, and M5 makes the copy test fail in both services |
| AC2: an exception whose message contains a synthetic turn logs no turn text | `services/accounts/tests/test_accounts.py::test_unhandled_error_returns_the_generic_envelope_and_logs_only_its_class` (TestClient, `raise_server_exceptions` on); `::test_unhandled_error_never_reaches_the_uvicorn_traceback_logger` (real uvicorn, debug level, caplog at DEBUG); `::test_a_failing_request_never_logs_or_echoes_its_body` (**added by QA**: turn sent in a POST body through real uvicorn, and the provider error echoes it); `test_content_free_log.py::test_an_error_after_the_response_started*` (moved there in fix round 1); `test_accounts.py::test_a_crashing_deletion_sweep_logs_only_its_class_and_fails_the_job`; `test_content_free_log.py::test_an_error_logs_only_the_class_name_and_stable_code`, `::test_an_error_ignores_caller_supplied_class_and_chained_causes` | `uv run --frozen pytest -v tests/test_accounts.py -k "unhandled or failing_request or after_the_response or crashing"` and `-k an_error` on `test_content_free_log.py` (accounts) | PASS | 5/5 and 2/2 passed. Response, stdout, stderr and caplog contain no turn text, no `Traceback` and no `Exception in ASGI application`, and the only log line is `{"severity":"ERROR","event":"unhandled_error","error_class":"ValueError","error_code":"internal_error","status_code":500}`. Mutations M2a, M2b and M2c each fail them |
| AC3: request and response body logging off at the gateway and Cloud Run | `services/accounts/tests/test_body_logging_off.py` (6 tests: gateway template has no logging keys; Terraform has no body or verbose logging; the Cloud Run services `accounts`, `session` and `grading` do not override command/args or add LOG/DEBUG env; the deletion job runs the sweep, not uvicorn; every uvicorn `CMD` has `--no-access-log`; the deploy workflow changes only the image) | `uv run --frozen pytest -v tests/test_body_logging_off.py` (accounts) | PASS | 6/6 passed. Mutations M3a, M3b and M3c each fail the matching test |
| AC4: a repository check flags `print` or root-logger calls in service handlers | Ruff `T20` + `LOG015` in `services/{accounts,session}/pyproject.toml`; `services/{accounts,session}/tests/test_logging_calls.py::test_service_packages_log_only_through_the_helper` (AST check for `getLogger()`/`getLogger("")`/`getLogger("root")` and direct `sys.stdout`/`sys.stderr` writes), plus self-tests `::test_the_check_fails_on_a_bypass` (7) and `::test_the_check_allows_*` | `uv run --frozen ruff check .` and `uv run --frozen pytest -v tests/test_logging_calls.py` (both) | PASS | Clean on the real code, 12/12 in each service. Mutations M4a–M4e show `T201`, `LOG015` and AST failures in both services |

**Acceptance: 4/4 proven.**

## CI checks (the commands `.github/workflows/ci.yml` runs)

| Service | `uv sync --locked --python 3.12` | `uv run --frozen pytest` | `uv run --frozen ruff check .` | `uv run --frozen mypy .` |
|---|---|---|---|---|
| services/accounts | OK | **202 passed, 5 skipped** after fix round 2 (104 at QA time) (5 skips = `test_store_emulator.py`, Firestore emulator not running; pre-existing and unrelated), 1 warning (Starlette httpx deprecation, pre-existing) | All checks passed | Success, 15 files |
| services/session | OK | **199 passed** after fix round 2 (156 at QA time) | All checks passed | Success, 21 files |

Before QA's added test, accounts was 103 passed and 5 skipped. The 5 tests that start a real uvicorn server
were run 5 times in a row with no flakes. The added test passes `ruff format --check`. The project
records no coverage tooling (no pytest-cov), so coverage is n/a.

## Mutation checks (each mutation was temporary and reverted)

The script backed up each file, applied one mutation, ran the AC tests and restored the original
bytes, asserting a byte-for-byte match. Afterwards, `git diff -- services | md5sum` matched the
pre-mutation hash (`148d75f1…`) and every untracked file under `services/` matched its pre-run md5.
`git diff -- infra services/accounts/Dockerfile` was empty.

| ID | Mutation | Command | Result |
|---|---|---|---|
| M1 (AC1) | `content_free_log._entry`: `clean = _allowed(key, value)` → `clean = value` (allow-list off) | pytest `test_content_free_log.py` | 23 failed / 13 passed, including all 5 `outside_the_allow_list[...]` and `reserved_keys` |
| M2a (AC2) | `api.create_app`: remove `app.add_middleware(ContentFreeErrors)` | pytest `test_accounts.py -k "unhandled or failing_request or after_the_response or crashing"` | 3 failed: `uvicorn.error … Exception in ASGI application` was logged (envelope, real-uvicorn and new POST-body tests) |
| M2b (AC2) | `log_error` adds `entry["detail"] = str(exc)` | same, plus `test_content_free_log.py` | 5 failed (accounts) + 2 failed (helper) |
| M2c (AC2) | catch-all calls `traceback.print_exc()` after logging | same | 4 failed |
| M3a (AC3) | `services/accounts/Dockerfile` drops `"--no-access-log"` | pytest `test_body_logging_off.py` | 1 failed: `test_every_uvicorn_container_command_disables_the_access_log` |
| M3b (AC3) | `infra/gateway.yaml.template` adds `log_request_body: true` | same | 1 failed: `test_the_gateway_config_has_no_logging_settings` |
| M3c (AC3) | `infra/session-grading/main.tf` grading container adds `args = ["--log-level", "debug"]` | same | 2 failed: `terraform_sets_no_body_or_verbose_logging`, `cloud_run_services_keep_the_image_command…` |
| M4a (AC4) | `print('health')` in the accounts `/health` handler | `ruff check .` (accounts) | exit 1, `T201 print found` |
| M4b (AC4) | `logging.info('health')` in the same handler | `ruff check .` (accounts) | exit 1, `LOG015 info() call on root logger` |
| M4c (AC4) | `logging.getLogger().warning('health')` in the same handler | pytest `test_logging_calls.py` (accounts) | 1 failed: `test_service_packages_log_only_through_the_helper` |
| M4d (AC4) | `sys.stderr.write("x")` in `cst_session/__init__.py` | pytest `test_logging_calls.py` (session) | 1 failed |
| M4e (AC4) | `print("x")` in `cst_session/__init__.py` | `ruff check .` (session) | exit 1, `T201` |
| M5 (FR-7) | one comment line added to `cst_session/content_free_log.py` | pytest `test_content_free_log_copies.py` (both) | 1 failed in each service: `test_every_copy_matches_the_accounts_copy_byte_for_byte` |

## Gap closed by QA

- `services/accounts/tests/test_accounts.py::test_a_failing_request_never_logs_or_echoes_its_body` (and
  the `InputEchoingAuth` fake). Until now the AC2 evidence took its turn text from a store error on a GET.
  This test sends the synthetic turn as a POST body to a real uvicorn server at debug log level. The
  provider fake raises an exception that echoes the body. The test asserts a generic 500, no turn text
  in the response, stdout, stderr or any captured log record (uvicorn, httpx and httpcore at DEBUG), and
  exactly one content-free log line. M2a, M2b and M2c each make it fail. No production code was changed.

## Notes and residual risks (not defects)

- `ContentFreeErrors` is the innermost middleware. An exception raised inside the outer `no_cache`
  `@app.middleware("http")` or `CORSMiddleware` would still reach Starlette's `ServerErrorMiddleware`,
  and uvicorn would log its traceback. Both are fixed, non-content code today, so this is low risk. Keep
  new outer middleware free of request data.
- The AST check cannot see a logger name built at run time, or a named logger's `.info(text)` with
  content. The module docstring says so, and review covers it.
- `services/session` has no HTTP app yet, so FR-4 and AC2 apply to accounts only. Session gets the helper,
  the drift test and the AC4 checks.
- The repo `.gitignore` does not list `specs/*/demo/`, which the pr-demo skill's bootstrap expects. Do not
  commit the GIF or WebM in the feature PR. They are published to `pr-media`.

## Demo

- `specs/063-content-free-logging/demo/063-content-free-logging.gif`: 16.6 s, 1280 px, 10 fps, 7.9 MB (7,874,386 bytes)
- `specs/063-content-free-logging/demo/063-content-free-logging.webm`: full quality, 1.4 MB
- Recorder: `specs/063-content-free-logging/demo-recording.py`, Python Playwright 1.58.0, following the
  `specs/004-access-accounts/demo-recording.py` precedent so the repo gains no `@playwright/test`
  dependency. It runs the real AC commands in both services, asserts exit 0, and replays only the
  per-test and summary lines, so no local paths appear. Scenes: AC1 (accounts allow-list tests plus the
  session copy test), AC2 (5 error-path tests plus 2 helper error tests), AC3 (6 body-logging tests), and
  AC4 (AST check in both services plus `ruff --select T20,LOG015` in both). QA opened frames 1, 2, 4, 6
  and 8. The captions match their criteria, every line is PASSED, and the frames contain only synthetic data.

## After fix round 1 (lead re-run, 2026-11-23)
The security review's hardening fixes (per-field id shapes, import allow-list, catch-all moved into
the copied module with a websocket path, started-branch code, count cap, multi-line CMD parsing) added
tests in both services. All checks were re-run on the fixed tree: accounts 175 passed / 5 skipped,
session 180 passed, ruff, `ruff format --check` and mypy clean in both, and the copies are byte-identical.
The AC test names above are unchanged. The started-branch test moved from `test_accounts.py`
to `test_content_free_log.py`. The demo was re-recorded on this tree.

## After fix round 2 (lead re-run, 2026-11-23)
Exception groups, the exact-path stream exemption, `os.write`, and nested `sh -c` parsing. Re-run on
the final tree: accounts 202 passed / 5 skipped, session 199 passed, ruff, format and mypy clean in
both, copies byte-identical. The demo was re-recorded on this tree.

## After the scenario-id fix (lead re-run, 2026-11-23)
`scenario_id` now accepts exactly the three catalogue ids in `rubric/anchor-spec.v1.json`, found
while starting #27. The final tree: accounts 204 passed / 5 skipped, session 199 passed, ruff,
format and mypy clean, and the copies are byte-identical.
