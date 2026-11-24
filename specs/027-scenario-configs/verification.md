# Verification: Three vetted scenario configurations (#27)

QA run 2026-11-23 on `feature/27-scenario-configs` at b8df11e (base origin/dev becffd3), plus QA's added
test file. Native Windows, uv, Python 3.12. All data is the synthetic, vetted config wording in
`services/session/cst_session/scenarios/configs/`.

## Acceptance criteria

| AC | Test(s) that prove it | Command | Result | Evidence |
|---|---|---|---|---|
| AC1: exactly three configurations load and pass schema validation | `services/session/tests/test_scenarios.py::test_exactly_the_three_vetted_scenarios_load_in_library_order`, `::test_the_scenario_ids_match_the_rubric_anchor_spec`, `::test_every_scenario_carries_the_preparation_fields`, `::test_only_the_crisis_scenario_is_crisis_and_it_requires_opt_in`, `::test_a_malformed_configuration_fails_loading` (24 cases: missing, unknown and wrong-typed keys, bad version, time limit 0/61/float/bool/string, control and zero-width characters, opt-in rules), `::test_a_file_that_is_not_utf8_fails_loading`, `::test_a_fourth_scenario_fails_loading`, `::test_a_missing_scenario_fails_loading`; **added by QA:** `tests/test_scenario_config_edges.py` (CRLF, BOM, array/table in a text field) | `uv run --frozen pytest -v tests/test_scenarios.py tests/test_scenario_config_edges.py` (session) | PASS | 6/6 load tests and 31/31 rejection tests pass. Mutations M1a, M1b, M1c, E1 and E2 each fail them |
| AC2: the time limit is read from config and is 10 minutes for each scenario | `test_scenarios.py::test_the_time_limit_is_10_minutes_for_every_scenario`, `::test_the_time_limit_is_read_from_config` (a copy set to 15 loads as 15, the others stay at 10) | `uv run --frozen pytest -v tests/test_scenarios.py -k time_limit_is` (session) | PASS | 2/2. The real catalogue prints `time_limit_minutes=10` for all three ids. Mutation M2 (hard-code 10) fails `test_the_time_limit_is_read_from_config` |
| AC3: a release flag turned off hides the scenario from the library and blocks it from starting (proved at the shared `library()`/`startable()` seam, owner decision 2026-11-23) | `test_scenarios.py::test_a_release_flag_off_hides_the_scenario_and_blocks_its_start[routine_intake, resistant_client, crisis_risk]`, `::test_held_back_and_unknown_scenarios_fail_the_same_way`, `::test_every_released_scenario_can_start`, `::test_an_unknown_scenario_cannot_start` (4) | `uv run --frozen pytest -v tests/test_scenarios.py -k "release_flag_off or every_released or held_back_and_unknown or unknown_scenario"` (session) | PASS | All pass, including the crisis config with `released = false`. Mutations M3a, M3b and M3c each fail 3 or 4 of them |
| AC4: no API path creates or edits a scenario | `services/session/tests/test_scenario_write_paths.py` (6: an AST route scan of every `services/*/cst_*` package, a check that the scenarios package never writes a file, and self-tests of 9 write-route shapes and 3 allowed reads); `test_scenarios.py::test_a_loaded_scenario_cannot_be_changed`, `::test_the_catalogue_offers_only_reads`, `::test_the_scenarios_package_exports_no_write_function` | `uv run --frozen pytest -v tests/test_scenario_write_paths.py` and `-k "cannot_be_changed or only_reads or no_write_function"` (session) | PASS | 6/6 and 3/3. Mutations M4a–M4d each fail the matching scan test, including a POST route added to `services/accounts/cst_accounts/api.py` |
| FR-8 (carried from #63): the logging helper's `scenario_id` accepts exactly the three ids | `services/accounts/tests/test_content_free_log.py::test_each_catalogue_scenario_id_is_kept` (3), `::test_an_id_outside_its_exact_shape_is_dropped` (6 scenario_id cases), `::test_allowed_identifiers_and_counts_are_kept`; `services/session/tests/test_scenarios.py::test_every_scenario_id_and_version_is_kept_by_the_logging_helper`; `services/session/tests/test_content_free_log_copies.py` | `uv run --frozen pytest -v tests/test_content_free_log.py` (accounts), `uv run --frozen pytest` (session) | PASS | 82/82 in accounts. Mutations M5a–M5c fail 6, 2 and 1 tests |

**Acceptance: 4/4 proven, plus FR-8.**

## Checks

| Service | `uv run --frozen pytest -q` | `ruff check .` | `ruff format --check .` | `mypy .` |
|---|---|---|---|---|
| services/session | **258 passed** (252 before QA, plus 6 added) | All checks passed | 27 files already formatted | Success, 26 source files |
| services/accounts | **204 passed, 5 skipped** (the `test_store_emulator.py` Firestore emulator tests, pre-existing), 1 warning (Starlette httpx deprecation, pre-existing) | All checks passed | 16 files already formatted | Success, 15 source files |

The session suite also passes (258) with every scenario `.toml`, `.py` and test file converted to CRLF, as a
`core.autocrlf=true` checkout writes them. The project has no coverage tooling, so coverage is n/a.

## Mutation checks (each one temporary; tree restored byte-for-byte, checked by SHA-256)

| # | Mutation | Tests that failed |
|---|---|---|
| M1a | Remove the unknown-key check | `test_a_malformed_configuration_fails_loading[...notes = "x"...-unknown]` |
| M1b | Accept a superset of files (`set(expected) <= set(found)`) | `test_a_fourth_scenario_fails_loading` |
| M1c | Ignore `.toml` files that aren't one of the three ids | `test_a_fourth_scenario_fails_loading` |
| M2 | `time_limit_minutes=10` hard-coded | `test_the_time_limit_is_read_from_config` |
| M3a | `library()` ignores `released` | `test_a_release_flag_off_hides_the_scenario_and_blocks_its_start` ×3 |
| M3b | `startable()` ignores `released` | the same ×3, plus `test_held_back_and_unknown_scenarios_fail_the_same_way` |
| M3c | The loader forces `released=True` | the same 4 |
| M4a | New `cst_session/scenario_admin.py` with `@app.post("/v1/scenarios")` | `test_no_service_declares_a_route_that_writes_a_scenario` |
| M4b | `@app.post("/v1/scenarios")` appended to `cst_accounts/api.py` | `test_no_service_declares_a_route_that_writes_a_scenario` |
| M4c | `app.add_api_route("/v1/scenarios/{scenario_id}", f, methods=["PUT"])` in session | `test_no_service_declares_a_route_that_writes_a_scenario` |
| M4d | The loader calls `.write_text()` | `test_the_scenarios_package_never_writes_a_file` |
| M5a | Accounts helper `scenario_id` back to the hyphen-slug regex | 6 in `test_content_free_log.py` (3 `each_catalogue_scenario_id_is_kept`, `allowed_identifiers_and_counts_are_kept`, 2 `exact_shape` cases) |
| M5b | Session copy back to the slug regex | `test_every_copy_matches_the_accounts_copy_byte_for_byte`, `test_every_scenario_id_and_version_is_kept_by_the_logging_helper` |
| M5c | Both copies back to the slug regex | `test_every_scenario_id_and_version_is_kept_by_the_logging_helper` |
| E1 | The loader decodes `utf-8-sig` (accepts a BOM) | `test_a_byte_order_mark_fails_loading_with_the_file_named` (QA) |
| E2 | `_text` coerces with `str(value)` | 4 array/table tests (QA); the existing `title = 3` case also catches it |
| E3 | The loader rejects any CR byte | `test_crlf_configs_load_exactly_like_lf_configs` (QA) |

## Edge cases probed

| Case | Behaviour | Tested before QA? |
|---|---|---|
| UTF-8 BOM prefix | `CatalogueError: <file>: not valid UTF-8 TOML` (fails closed at startup) | No, added |
| CRLF line endings (Windows `autocrlf` checkout) | Loads identically to LF | No, added |
| Array, inline table, dotted key or `[table]` header in a text field | `CatalogueError: <file>: <key> must be one trimmed line...` | Only `title = 3`; added |
| An extra `[meta]` table | `CatalogueError: unknown ['meta']` | Covered by the unknown-key case |
| Crisis config with `released = false` | Loads, hidden from `library()`, `startable()` raises, opt-in still enforced | Yes (AC3 parametrized over all three ids) |
| Duplicate key, lone-CR file | `CatalogueError ... not valid UTF-8 TOML` | Not needed (tomllib) |
| U+2028/U+2029 inside a text field | **Loads.** `_text` rejects category `C*` only, and these are `Zl`/`Zp`, so a "one line" field can hold a line or paragraph separator | No. Finding F1 below |
| `routine_intake.toml.bak` or `extra.TOML` in `configs/` | Ignored, so neither is loaded. Harmless because it can't add a scenario | n/a |

## Findings

- **F1 (Low, production code):** `services/session/cst_session/scenarios/catalogue.py` `_text`, the
  `unicodedata.category(char).startswith("C")` check, lets U+2028 LINE SEPARATOR and U+2029 PARAGRAPH SEPARATOR
  through, although the error message promises "one trimmed line". All configs are reviewed commits, so the
  risk is low. Fix: also reject `Zl` and `Zp`, and add a case to `test_a_malformed_configuration_fails_loading`.
  QA did not add a failing test, because the fix is in production code.
  **Fixed by the lead after QA:** `_breaks_the_line` also rejects `Zl`/`Zp`, and two new
  `test_a_malformed_configuration_fails_loading` cases (U+2028, U+2029) fail without the fix and pass with it.
  Session: 260 passed, and ruff, format and mypy are clean. The demo was re-recorded on the final tree.
- **F2 (Info):** `.gitignore` does not list `specs/*/demo/`, so `specs/027-scenario-configs/demo/` shows as
  untracked, as `specs/063-content-free-logging/demo/` already does. Don't commit it. The media goes to
  `pr-media`.

## Demo

- `specs/027-scenario-configs/demo/027-scenario-configs.gif`: 18.2 s, 1280 px, 10 fps, 6.5 MB (6,507,379 bytes)
- `specs/027-scenario-configs/demo/027-scenario-configs.webm`: full quality
- Recorder: `specs/027-scenario-configs/demo-recording.py` (Python Playwright 1.58.0, the #63 precedent). It
  runs the real commands, asserts they pass, then replays their output in five captioned scenes: AC1, AC2 (the
  real catalogue's printout plus tests), AC3, AC4 and FR-8. QA checked the frames for each scene: the captions
  match the criteria, every line is PASSED, and no local paths, names or credentials appear.

```
uv run --no-project --python 3.12 --with playwright==1.58.0 python specs/027-scenario-configs/demo-recording.py <OUT_DIR>
python ~/.claude/skills/pr-demo/scripts/to_gif.py specs/027-scenario-configs/demo/027-scenario-configs.gif <OUT_DIR>/*.webm --keep-video specs/027-scenario-configs/demo/027-scenario-configs.webm
```
