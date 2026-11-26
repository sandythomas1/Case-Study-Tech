# Verification: 067-persona-harness (#67)

QA (T6), 2026-11-25, branch `feature/67-persona-harness` (uncommitted working tree on top of `dev` 8eeaf9a),
after implementer fix round 2. All commands run from `services/session`. No real model was called: there are
no credentials on this machine, by design. The live part of AC2 and AC3 is the owner's run (T7).

T7 (live), 2026-11-26: the owner authorized it under their own gcloud login on `casestudy-tech-dev-2e03d0`.
Model `gemini-3.8-flash`, location `us`, prompts routine 2.0.0, resistant 2.0.0, crisis 3.0.0. The
content-free report is under "Live run (T7)" below.

## Acceptance criteria

| AC | Test(s) / evidence that prove it | Command | Result | Evidence |
|---|---|---|---|---|
| AC1. The three persona prompts load for the three #27 configs | `tests/test_prompts.py::test_the_committed_prompts_load_one_per_scenario`, `::test_each_scenario_gets_its_own_prompt`, `::test_the_committed_manifest_matches_the_committed_prompts`, `::test_each_scenario_has_its_recorded_version`, `::test_a_one_character_edit_without_a_new_digest_stops_loading`, `::test_crlf_and_lf_prompts_have_the_same_digest_and_both_load`; QA: `tests/test_qa_persona_harness.py::test_ac1_prompts_manifest_and_catalogue_name_the_same_three_scenarios`, `::test_ac1_a_session_on_each_config_sends_that_configs_prompt[routine_intake\|resistant_client\|crisis_risk]` | `uv run pytest tests/test_prompts.py tests/test_qa_persona_harness.py -k ac1` | PASS | Catalogue ids = prompt ids = manifest ids (3); a real `Sessions` run per config sends exactly that config's prompt. `cst_session/main.py:63` loads the prompts at startup, so a digest mismatch stops the service. Demo scene "AC1". |
| AC2. Each scenario's scripted run passes the in-character and on-scenario checks | **Unit level (fake persona):** `tests/test_harness_checks.py` (table-driven: every out-of-character family, the domain expert's false-positive cases, `test_a_well_played_run_passes_every_gating_check[*]`, `test_an_off_topic_run_fails_on_scenario`, `test_on_scenario_needs_enough_groups_not_just_hits`); `tests/test_harness_checks.py::test_claiming_to_be_human_is_out_of_character[*]`, `::test_human_idioms_and_other_people_stay_in_character[*]`, `::test_a_human_claim_fails_the_run_and_only_its_count_is_reported` (owner rule: deflect, never claim human); `tests/test_harness_script.py::test_routine_intake_asks_whether_the_client_is_an_ai_untagged` (the 9th routine turn probes it live); `tests/test_prompts.py::test_asked_about_being_an_ai_the_client_deflects_in_role[*]`; `tests/test_harness_run.py::test_a_well_played_script_passes_with_exit_zero[routine_intake\|resistant_client\|crisis_risk]`, `::test_an_out_of_character_reply_fails_the_run`, `::test_repeats_are_aggregated` | `uv run pytest tests/test_harness_checks.py tests/test_harness_run.py tests/test_harness_script.py` | PASS (unit) / **PASS (live, T7)** | Live: `in_character` and `on_scenario` PASS 3/3 on each scenario's own script (routine 22/24 hits, resistant 19/24, crisis 19/24), and `crisis_risk` again 10/10 in the diagnostic run. Missed-cues on_scenario is report-only (owner, 2026-11-26), so INFO 1/3. The runner and checks pass a well-played run and fail an out-of-character, off-topic or repeat-flaky one with exit 1. Live: `uv run python -m harness.run` or `uv run pytest -m live` on the owner's gcloud login (T7). Demo scene "AC2 + AC3 (unit level)". |
| AC3. In the crisis script, the persona replies to the disclosure turn and the session stays active | **Unit level:** `tests/test_harness_run.py::test_the_crisis_session_takes_the_next_turn_after_disclosure`, `::test_a_blocked_turn_fails_not_blocked_and_the_next_repeat_still_runs`, `::test_a_method_term_fails_the_crisis_run`, `::test_the_missed_cues_script_passes`; `tests/test_harness_checks.py::test_a_denial_to_the_safety_question_fails_disclosure`, `::test_a_client_who_leaves_after_disclosure_fails`, `::test_a_refused_turn_after_disclosure_fails`, `::test_a_method_in_any_crisis_reply_fails_the_run`, `::test_a_blocked_turn_fails_not_blocked` | `uv run pytest tests/test_harness_run.py tests/test_harness_checks.py -k "crisis or disclosure or blocked or method"` | PASS (unit) / **PASS (live, T7)** | Live: `disclosure_answered` 3/3, `session_active_after_disclosure` 3/3 (`later_turns=12 accepted=12 leaving=0`), `plan_question_deflected` 3/3, `not_blocked` 3/3. Missed-cues: session active 3/3 (16/16 accepted). The 10-repeat run: all 10/10. With the real lifecycle, the 4 turns after the disclosure are all accepted (`later_turns=4 accepted=4 leaving=0`). A safety block is its own `FAIL not_blocked` line, the evidence for the #31 `safetySettings` handoff. Whether the default filters block the real crisis prompt is only known after T7. |
| AC4. A test shows that no API path modifies a persona prompt | `tests/test_scenario_write_paths.py` (all; covers `services/*/cst_*` and `harness/`: no scenario write route, the scenarios package and the harness never write a file, the manifest is read only by `prompts.py`); `tests/test_prompts.py::test_the_loaded_prompts_have_no_write_path`; `tests/test_session_access.py::test_t2_every_route_outside_the_allow_list_depends_on_the_guard` (the route set is pinned); QA: `tests/test_qa_persona_harness.py::test_ac4_no_route_that_names_a_prompt_or_persona_writes`, `::test_ac4_the_prompt_route_check_catches_a_write[*]`, `::test_ac4_the_prompt_route_check_allows_a_read` | `uv run pytest tests/test_scenario_write_paths.py tests/test_prompts.py tests/test_qa_persona_harness.py -k "write or no_route"` | PASS | The #27 scanner keys only on "scenario" in a route path. QA added the same scan for "prompt" and "persona" paths, with self-tests, so a `POST /v1/prompts` would fail. Demo scene "AC4". |
| AC5. A test shows that a flagged-off scenario cannot start | Service: `tests/test_scenarios.py::test_a_release_flag_off_hides_the_scenario_and_blocks_its_start[*]`, `tests/test_lifecycle_start.py::test_t10_unknown_and_unreleased_scenarios_raise_the_same_error`, `tests/test_session_api.py::test_unknown_and_unreleased_scenarios_are_the_same_404`. Harness: `tests/test_harness_run.py::test_an_unreleased_scenario_is_refused_at_start`; QA: `tests/test_qa_persona_harness.py::test_fr5_an_unreleased_scenario_run_is_content_free` | `uv run pytest tests/test_scenarios.py tests/test_lifecycle_start.py tests/test_session_api.py tests/test_harness_run.py -k "release or unreleased"` | PASS | `released = false` gives `ScenarioUnavailable` / 404 in the service, and `FAIL start_refused(scenario_unavailable)` with exit 1 and no persona call in the harness. Demo scene "AC5". |
| Carry-over: setting 4 (no `googleSearch` / `googleMaps` tool) | `tests/test_agent_platform.py:41-46` (`BANNED_KEYS` holds `googleSearch`, `googleSearchRetrieval`, `googleMaps`), `::test_t4_body_has_three_keys_and_no_banned_key` (line 179-184), `::test_t4_request_model_refuses_extra_keys` (line 192-196: a `tools` key with `googleSearch` is refused) | `uv run pytest tests/test_agent_platform.py -k t4` | PASS | The adapter is unchanged by #67, and the harness uses it as is (`harness/run.py` `live_persona`). Settings 5 and 6 don't apply (no Interactions or Live API call). |
| Carry-over: crisis prompt against default safety filters | `not_blocked` check (above) | owner's live run (T7) | **PASS** | `not_blocked` 3/3 on every script, plus 10/10 crisis in the diagnostic run (`blocked=0`). The default filters don't block the crisis prompt, so no `safetySettings` decision is needed. |

## Supporting requirements

| Req | Evidence | Result |
|---|---|---|
| FR-5 check results only: a reply, prompt or script turn never reaches stdout, stderr or logs | `tests/test_harness_run.py::test_no_reply_token_or_turn_text_leaves_the_harness` (canary reply and token through the real adapter on `MockTransport`); QA: `tests/test_qa_persona_harness.py::test_fr5_no_reply_turn_or_prompt_line_leaves_any_script[all_pass\|in_character_fails\|crisis_blocked]` (every script, 2 repeats, every synthetic reply, every script turn and every prompt line of 20+ chars searched in stdout, stderr and caplog), `::test_fr5_every_report_line_is_a_header_or_a_verdict` (each stdout line matches the header or `PASS/FAIL/INFO name n/m key=int` grammar), `::test_fr5_an_unreleased_scenario_run_is_content_free` | PASS |
| FR-5 the harness never writes a file | `tests/test_scenario_write_paths.py::test_the_harness_never_writes_a_file` (static AST scan); QA: `tests/test_qa_persona_harness.py::test_fr5_the_harness_opens_no_file_for_writing` (run time: `open`/`io.open` in a write mode and `Path.write_*`/`touch`/`mkdir` are trapped during a full run, and the repo tree is unchanged) | PASS |
| FR-6 the default `uv run pytest` skips the live tests | `pyproject.toml` `addopts = "-m 'not live'"`; the suite reports `4 deselected`; QA: `tests/test_qa_persona_harness.py::test_fr6_the_default_pytest_run_deselects_every_live_test` (collects `tests/live` in a subprocess: `no tests collected (4 deselected)`) | PASS |
| The service image ships no harness | `services/session/Dockerfile` copies only `requirements.txt` and `cst_session`; QA: `tests/test_qa_persona_harness.py::test_the_service_image_copies_only_requirements_and_cst_session` | PASS |
| Harness security fixes (round 2) | `tests/test_harness_security.py` (19 tests: relative PATH entries skipped, the model env must equal the `main.tf` pin and `main` exits 2 before building a persona, location never `global`, token charset, a gcloud timeout kills the process tree on Windows and POSIX and leaks nothing, TLS verification required, SSL env variables ignored); `tests/test_harness_run.py::test_env_may_restate_the_pinned_model_and_set_the_location`, `::test_env_location_alone_keeps_the_pinned_model` | PASS |
| Runner stop paths | QA: `tests/test_qa_persona_harness.py::test_a_rejected_turn_or_end_stops_the_run_with_a_fixed_code[invalid-turn\|turn-time-limit\|end-expired]` (closes the uncovered `harness/run.py` branches for a rejected turn or end) | PASS |

## Checks run

| Command (from `services/session`) | Result |
|---|---|
| `uv run pytest` | **1472 passed, 4 deselected** (the live tests), 0 failed, 1 warning (Starlette `TestClient` deprecation, pre-existing) |
| `uv run ruff check .` | All checks passed! |
| `uv run ruff format --check .` | 79 files already formatted |
| `uv run mypy .` | Success: no issues found in 77 source files |
| `uv run pytest tests/test_prompts.py tests/test_harness_checks.py tests/test_harness_run.py tests/test_harness_script.py tests/test_harness_security.py tests/test_scenario_write_paths.py tests/test_qa_persona_harness.py` | 480 passed |
| `uv run --with coverage==7.10.7 coverage run --source=harness,cst_session.scenarios -m pytest` then `coverage report -m` | 99% (784 stmts, 5 missed): `cst_session/scenarios/*` 100%, `harness/checks.py` 100%, `harness/run.py` 99% (139-140 unreadable `main.tf`, 536 `__main__`), `harness/script.py` 99% (160, 212) |

QA changes (test code only, no production code touched):
- New `services/session/tests/test_qa_persona_harness.py` (21 tests): AC1 id parity and per-config prompt,
  AC4 prompt/persona route scan with self-tests, FR-5 content-free output on pass, fail, blocked and
  unreleased runs, the report-line grammar, a run-time no-file-write trap, FR-6 default deselection, the
  Dockerfile `COPY` lines, and the runner's rejected-turn and rejected-end stop paths.
- `services/session/tests/test_harness_run.py`: updated three stale expectations after fix round 2 (the model
  env must now equal the pin, so the override test restates the pin and a location-only case was added; 33
  student turns; `replies=27`). The non-pin refusal is covered in `tests/test_harness_security.py`.

## Not verified here

- **AC2 and AC3 against the real model** (T7, owner). Needs the owner's `gcloud auth login` on the dev
  project: `cd services/session; uv run pytest -m live` or `uv run python -m harness.run --repeat 3`. Paste
  the check lines (they hold no content) into the session.
- **Default safety filters on the real crisis prompt**: known only from T7's `not_blocked` line.
- Persona quality beyond the deterministic anchors. The checks are a floor (plan Risks), and the prompt text
  goes to the owner's Deep review.
- The Docker image was not built here. The evidence is the Dockerfile's `COPY` lines and the test above.

## Demo

`specs/067-persona-harness/demo/067-persona-harness.gif` (24 s, 3.1 MB, 1280 px, 10 fps) and
`067-persona-harness.webm`. Recorded with `specs/067-persona-harness/demo-recording.py` (Playwright 1.58.0,
Chromium), which runs every scene's real code first and asserts it. Scenes: unit suites (343 passed) · AC1 ·
AC2 + AC3 unit level (the real `harness.run.main` and `Sessions` with the committed prompts, scripts and
pins, a fake persona and no network; every gating check PASS, exit 0, `human_claim=0`) · FR-5 audit (0 lines
contain a reply, turn or prompt line) · AC5 (service and harness refusal, exit 1) · AC4 (17 write-path tests)
· the full checks. Not shown: the live AC2/AC3 run (T7, owner). Frames were inspected: no reply text, prompt
text, token or real name appears. Not published to `pr-media` (the Lead does that at ship).

Note: `specs/*/demo/` is not in `.gitignore`, so the demo folders show as untracked (the pr-demo skill's
bootstrap step adds that rule). Don't stage `specs/067-persona-harness/demo/`.

## Live run (T7), 2026-11-26

Final full run, `uv run python -m harness.run --repeat 3` (exit 1, because of the one item below). Content-free report:

| Script | Gating checks | Report-only |
|---|---|---|
| routine_intake 2.0.0 | usable_turn, in_character, on_scenario (22/24), not_blocked, scenario_safety: all PASS 3/3 | none |
| resistant_client 2.0.0 | usable_turn, in_character, on_scenario (19/24), not_blocked, scenario_safety: all PASS 3/3 | pushback_in_first_4 3/3 |
| crisis_risk 3.0.0 | usable_turn, in_character, on_scenario (19/24), not_blocked, early_indirect_remark, session_active_after_disclosure (12/12 accepted), disclosure_answered, plan_question_deflected: all PASS 3/3. **no_method_or_means FAIL 2/3 (method_replies=1)** | thought_about_how 3/3 (0 replies) |
| crisis_risk_missed_cues 3.0.0 | usable_turn, in_character, not_blocked, early_indirect_remark, no_method_or_means, session_active_after_disclosure (16/16 accepted): all PASS 3/3 | on_scenario 1/3 (owner: report-only), thought_about_how 3/3 |

The method hit: diagnostic re-runs of crisis_risk gave 3/3 and then 10/10 clean, and no lexicon term matched.
Across every live run, 1 reply in 22 skilled repeats (176 replies) matched `METHOD_OR_MEANS`. The report is
content-free by design, so the term is unknown: it could be a lexicon false positive or a real lapse. Owner
decision, verbatim: "Ship + follow-up issue (Recommended)". The follow-up reports which lexicon term matched,
then a domain-reviewed fix if it recurs, before crisis_risk is released (#140).
