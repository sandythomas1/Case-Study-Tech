# Verification: #66 completed-session handoff contract

QA run on 2026-11-23, branch `feature/66-handoff-contract`, working tree (nothing committed).
Commands run in `services/session` unless noted.

## Acceptance criteria

| AC | Proven by | Command | Result | Evidence |
|---|---|---|---|---|
| AC1. Validation accepts the completed fixtures | `test_completed_fixtures_are_accepted[*]` (3), `test_parsing_the_raw_body_gives_the_same_session[*]` (3), `test_per_turn_reliability_flags_reach_the_grader`, `test_there_is_a_fixture_per_scenario_and_per_rejection_reason` | `uv run pytest tests/test_handoff_contract.py` | PASS | All three accepted fixtures (`routine_intake` text, `resistant_client` voice, `crisis_risk` voice) parse through `parse_handoff` from raw bytes. Independently checked against the committed JSON Schema with `jsonschema` 4.23.0 (Draft 2020-12): all three are schema-valid. Demo scene 1. |
| AC1. Rejects incomplete, content-lost, conduct-ended and wrong-version | `test_rejected_fixtures_fail_with_their_reason[*]` (8), `test_a_status_reason_wins_even_when_the_rest_is_broken[*]` (3), `test_a_wrong_version_wins_over_a_broken_body`, `test_a_missing_or_unknown_version_is_a_version_mismatch[*]` (5), `test_a_rejection_carries_only_its_reason[*]` (8) | same | PASS | Each rejected fixture gives exactly its file-name reason: `incomplete`, `content_lost`, `ended_for_conduct`, `version_mismatch` and four `malformed--*` cases. Demo scene 2. |
| AC2. Validating a payload emits no turn text | `test_validating_a_fixture_logs_no_turn_text_or_owner_uid[*]` (11), `test_an_accepted_session_logs_one_content_free_event[*]` (3), `test_a_rejection_logs_its_reason_and_the_session_id_only[*]` (8), **new** `test_a_malformed_session_logs_no_turn_text_or_owner_uid[*]` (38), **new** `test_a_body_that_cannot_be_decoded_logs_only_the_reason`, plus the repr and error-echo tests | `uv run pytest tests/test_handoff_logging.py` | PASS (65) | Every log line is exactly `{severity, message, event, session_id[, duration_ms]}`. Mutation check: adding `print(payload)` to `_reject` in `validation.py` made 56 of 65 logging tests fail, and the file was restored (sha256 `81ee90da…` before and after). A 20,000-case fuzz found 0 log lines with turn text or owner UID (probes below). Demo scene 3. |
| AC3. A test generates the JSON Schema and it matches the committed copy | `test_the_committed_schema_matches_the_models`, `test_the_schema_file_is_plain_ascii_json` and 4 structural schema tests | `uv run pytest tests/test_handoff_schema.py` | PASS (6) | Mutation check: setting `MAX_TURN_CHARACTERS = 2500` in `contract.py` made `test_the_committed_schema_matches_the_models` and `test_the_schema_file_is_plain_ascii_json` fail ("…schema.json is stale. Run `uv run python -m cst_session.handoff.export`…"). The file was restored from a backup (sha256 `1c871bb7…` before and after), and the 6 tests pass again. The demo repeats this in a throwaway copy (scene 4). The committed schema passes `Draft202012Validator.check_schema`. |

## Checks

| Command | Result |
|---|---|
| `uv run pytest` | 432 passed, 0 failed, 0 skipped, after both fix rounds (QA's own run was 372: 333 before QA plus 39 new QA tests) |
| `uv run pytest tests/test_handoff_*.py` | 231 passed (contract 133, logging 78, schema 20) |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 30 files already formatted |
| `uv run mypy .` | Success: no issues found in 29 source files |
| `python scripts/ci/check_synthetic_fixtures.py` (repo root) | Passed: 336 tracked files, 0 allowlisted. It reads only *tracked* files, so the untracked `handoff/` files were also run through its `classify()` directly: no finding for any of them. |
| Coverage (`uv run --with pytest-cov==6.0.0 pytest --cov=cst_session.handoff --cov-branch`, ephemeral, not added to the lock) | `contract.py` 100%, `validation.py` 100%, `__init__.py` 100%, `export.py` 77% (only `main()` and the `__main__` guard, which write the file). Total 98%. |

## Adversarial probes

Scratch scripts, run in the session environment. None changed production code.

| Probe | Outcome |
|---|---|
| Consistency breaks that pass the JSON Schema (`malformed--crisis-flags-missing`, `--speech-turn-in-text-session`, `--turn-gap`) | Schema-valid under `jsonschema`, rejected `malformed` by the validator, as designed. Cross-field rules live only in the pydantic validators, so a consumer must call `validate_handoff`, not only the schema. |
| Type coercion: `"1"`/`1.0`/`True` for ints, `0`/`"false"` for bools, `10**30`, scenario as string, turns as dict, `crisis: false` | All `malformed` (strict mode holds). `"1.0.0 "` gives `version_mismatch`. `"completed "` and `"CONTENT_LOST"` give `malformed`. |
| Unicode in text: lone surrogate (escaped and raw bytes), DEL, VT, FF, C1 `\x85`, NBSP-only, U+2028-only, U+3000-only | All `malformed`. |
| Unicode in text: 2,000 astral emoji (accepted), 2,001 (rejected), combining marks, RTL override, U+FFFF, trailing newline | Accepted or rejected as the length rule says. Length counts code points, the same in pydantic, Python and JSON Schema. |
| Unicode in ids: Arabic-Indic digits in `owner_uid` and `scenario.version`, fullwidth letters, UUID with a trailing `\n` | All `malformed`. A trailing newline doesn't slip past `$`. |
| Text that is only U+200B (zero-width space) or only U+FEFF (BOM) | **Accepted.** See finding F2. |
| Duplicate keys: top-level (tested), nested inside a turn | `malformed`. |
| Depth: 500, 990, 5,000 and 100,000 nested arrays; a 5,000-digit integer; `NaN`/`Infinity`; `1e400` | All `malformed`. There was no crash or `RecursionError` escape. |
| Size: 500 turns x 2,000 characters | ASCII: 1.05 MB, accepted. `é` without escaping: 2.05 MB, accepted. `é` escaped (`json.dumps` default): 6.0 MB; CJK: 3.0 MB; emoji: 4.0 MB. The last three are **rejected `malformed`** although `validate_handoff` accepts the same dict. See finding F1. |
| Encodings: UTF-16 body, UTF-8 BOM prefix | Both **accepted** (`json.loads` detects the encoding from bytes). See finding F3. |
| Random fuzz: 20,000 mutations of the 11 fixtures (seeded), 10% truncated | 0 crashes (every outcome was `HandoffRejected` or an accept), 0 log lines with turn text or owner UID, exactly one well-formed log line per call. Outcomes: 13,451 malformed, 2,019 version_mismatch, 1,500 ended_for_conduct, 1,496 incomplete, 1,458 content_lost, 76 accepted (all benign edits, such as replacing text with other valid text). |
| Concurrency: 4,000 `parse_handoff` calls on 16 threads | 4,000 log lines, all valid JSON, none interleaved. 1,092 accepted, matching the expected count. |
| Shape the contract allows: a session with only client turns, crisis in text mode, all turns at `at_ms` 0 with `duration_ms` 0 | Accepted. Text mode for crisis is allowed (POLICY ETH-4 keeps text mode usable). A completed session where the student never spoke is an open product question (F4). |

## Findings

| # | Severity | Where | Finding |
|---|---|---|---|
| F1 | Low | `services/session/cst_session/handoff/validation.py:31` (`MAX_BODY_BYTES`) and `contract.py:34-35` | The 2 MiB body cap is smaller than the largest payload the schema allows. A schema-valid session of 500 turns x 2,000 non-ASCII characters is 3 to 6 MB and gets `malformed` from `parse_handoff`, while `validate_handoff` accepts the same dict. Realistic sessions are far below the cap: an hour of talk is about 60 KB. Fix one side, either a cap derived from the limits or tighter limits, and document it in `handoff/README.md`. |
| F2 | Low | `contract.py:41` (`_TEXT_PATTERN`) | "At least one non-space character" lets through invisible-only text: U+200B is accepted by both the validator and the JSON Schema, and U+FEFF is accepted by the validator but rejected by an ECMA-regex schema consumer (ECMA `\s` includes U+FEFF; Rust/Python `\s` does not). That makes a small validator/schema divergence. Consider excluding format characters (Cf) or listing them in the pattern. |
| F3 | Info | `validation.py:63` | `parse_handoff` accepts UTF-16/32 bodies and a UTF-8 BOM, because `json.loads(bytes)` auto-detects the encoding. That's harmless, but stricter than "plain JSON" would need `body.decode("utf-8")` first. |
| F4 | Info (product question) | `contract.py` `_consistent` | A `completed` session with no student turn is accepted. Whether the grader should ever see one is for the owner or #35. It is not covered by any AC. |

None of these blocks an acceptance criterion. Lead dispositions (see `review.md`): F1 fixed with a 5 MiB cap, `encode_handoff` and a worst-case test. F2 fixed: bidi controls and the BOM are forbidden, an invisible character can't be the visible one, and a schema-agreement test covers it. F3 fixed with a strict UTF-8 decode. F4 deferred to #35.

## Added after QA (lead fix rounds)

- Owner decision "Add save_transcript now (Recommended)": `test_the_save_choice_reaches_the_grader`, `test_a_session_marked_dont_save_is_still_graded`, `test_the_save_choice_is_a_required_boolean`, the missing, string, number and null cases in `MALFORMED_CHANGES`, and `rejected/malformed--save-choice-missing.json`.
- Encoding and size: `test_a_body_that_is_not_plain_utf8_is_malformed`, `test_an_encoded_session_parses_back_to_itself`, `test_the_largest_valid_session_fits_the_body_cap` (ASCII, Latin, CJK, emoji) and `test_the_encoder_writes_raw_utf8`.
- Text: `test_the_schema_text_pattern_agrees_with_the_validator` (including tag characters and the England flag), `test_joiners_and_marks_are_allowed_beside_visible_text`, and the bidi, BOM and invisible-only cases in `MALFORMED_CHANGES`.
- `test_the_session_id_is_bounded_in_length`.

## Tests added by QA

`services/session/tests/test_handoff_logging.py`:
- `test_a_malformed_session_logs_no_turn_text_or_owner_uid` (38 cases, one per `MALFORMED_CHANGES` entry). AC2 was only checked on the 11 fixtures. This covers every malformed-path mutation, including text with control characters.
- `test_a_body_that_cannot_be_decoded_logs_only_the_reason`. A truncated body logs only the reason, with no session ID and no content.

## Demo

`specs/066-handoff-contract/demo/066-handoff-contract.gif` (7.3 MB, 1280 px, 10 fps) and
`066-handoff-contract.webm` (2.0 MB), re-recorded on the final tree (12 fixtures, 432 tests) by `specs/066-handoff-contract/demo-recording.py`.
Scenes:
1. AC1, accepted fixtures.
2. AC1, each rejection reason.
3. AC2, all 12 logged lines and the zero leak count.
4. AC3, the schema in sync, then stale after a model change in a throwaway copy.
5. The full suite, lint, format, mypy and the fixture check.

Frames from every scene were inspected. They show synthetic data only and no local paths.
The demo isn't committed. `specs/*/demo/` isn't in `.gitignore` here, and committing the `.webm`
would trip `check_synthetic_fixtures.py` (video extension), so the media goes to `pr-media` only.
