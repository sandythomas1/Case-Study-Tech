# Verification: 031-session-service (Issue #31)

QA run on 2026-11-25. Branch `feature/31-session-service`, uncommitted on base `dev`. Every command runs
from `services/session`. No real Google or Firebase credentials were used, and nothing reached Agent
Platform: the real `AgentPlatformPersona` ran over `httpx.MockTransport`.

QA added `tests/test_qa_acceptance.py`, which has 48 tests. It wires the real `create_app`, the real
`Sessions`, the real `AgentPlatformPersona` and `UnavailableGrader`, and the real `StateCodec`, catalogue
and prompts. Only these are faked:

- the clock
- the token minter
- the transport
- the identity and access store, except in the real-guard tests, which use the real `FirebaseIdentity`
  and `FirestoreAccess` over read-only fakes

QA also added `test_t7_end_body_strict` (6 cases) to `tests/test_session_api.py`, as the security
audit asked.

## Acceptance criteria

| AC | Proven by | Command | Result | Evidence |
|---|---|---|---|---|
| **AC1** The simulated client replies within the selected scenario | Three tests in `test_qa_acceptance.py`. `test_ac1_the_client_replies_within_each_selected_scenario[routine_intake, resistant_client, crisis_risk]` checks the reply in each scenario. `test_ac1_each_scenario_sends_its_own_prompt_and_no_other` checks the systemInstruction is that scenario's prompt only. `test_ac1_the_second_turn_carries_the_ordered_history` checks the history order. The existing lifecycle and API tests also cover this. | `uv run pytest tests/test_qa_acceptance.py -k ac1` | PASS | 5 passed. Demo scene 1 sends real HTTP to uvicorn. The model call goes to `aiplatform.us.rep.googleapis.com/.../gemini-3.8-flash:generateContent` with body keys `contents, generationConfig, systemInstruction`. The prompt is the selected scenario's file. A crisis start without opt-in gets 403 `opt_in_required`; with opt-in it gets a reply. |
| **AC2** The time limit and manual end | `test_ac2_a_session_at_the_limit_rejects_turns_and_ends_by_time_limit` and `test_ac2_manual_end_returns_no_state_to_continue_from`. `test_l2_1_a_pre_end_state_keeps_working_only_until_the_limit_under_ad_2` is the named L2-1 test task 22 asked for; it was missing, and QA added it. | `uv run pytest tests/test_qa_acceptance.py -k "ac2 or l2_1"` | PASS | 3 passed. Demo scene 2: a turn at 10:00 gets 409 `session_time_limit`. End then gets 200 with `ended_by: time_limit`, outcome `unscored`. End after the 1:00 grace gets 409 `session_expired`. A manual end gets 200 `student` with no state. A kept pre-end copy still takes turns until 10:00, then gets 409. The owner accepted this as L2-1 (AD-2). |
| **AC3** No conversation content is stored or logged, and access is point reads only | `test_ac3_a_whole_session_makes_only_point_reads_on_the_real_access_store`: the real `FirestoreAccess` sits over a fake that raises on anything except `collection().document().get()`. `test_ac3_the_real_access_store_refuses_a_pending_account` also uses the real store. The existing `test_session_no_content.py` canary tests and `test_logging_calls.py` cover logging. | `uv run pytest tests/test_qa_acceptance.py -k ac3`, then `uv run pytest tests/test_session_no_content.py tests/test_logging_calls.py` | PASS | 2 passed, then 76 passed. For the first test, the access log is exactly 3 × [`get account_deletions/<uid>`, `get access/<uid>`]. Demo scene 4 checks all 21 service JSON lines and 9 Python-logging lines. It searched them for the student turns, replies, prompts, UID, both tokens and every state, and found 0 lines with any of them. Fields used: `duration_ms, error_class, error_code, event, message, scenario_id, scenario_version, session_id, severity, status_code`. A grep audit found no Firestore writes in `cst_session`. `content_free_log.py` is unchanged against `origin/dev`. |
| **AC4** A model failure gives an unscored ending, not a partial score | `test_ac4_every_model_failure_is_503_with_no_state_and_no_grading` runs 11 cases: bad_json, blocked, connect_error, deadline, empty_reply, function_call, http_403, http_429, http_500, read_timeout and redirect. Each case asserts 503 `persona_unavailable`, no state, 0 grader calls, the matching `persona_failed` `error_code`, and that the turn text is not in the logs. `test_ac4_no_ending_carries_a_score_even_after_a_full_session` and `test_ac4_a_failed_turn_is_never_signed_into_any_state` cover the rest. | `uv run pytest tests/test_qa_acceptance.py -k ac4` | PASS | 13 passed. Demo scene 3 injects a hang past the 1.5 s deadline, an upstream 503 and a blocked reply. Each gets 503 `persona_unavailable` with no state, and the grader port gets 0 calls. The logs show `persona_timeout`, `persona_http_error` (503) and `persona_blocked`. |
| **Carry-over: the approved guard on every route** (route inventory, including websocket routes) | `test_session_access.py` (all of it), including `test_t2_every_route_outside_the_allow_list_depends_on_the_guard`, `test_t2_inventory_counts_websocket_routes` and `test_t2_inventory_fails_on_a_mount`. In `test_qa_acceptance.py`, the real-guard tests use the real `FirebaseIdentity` (with `check_revoked=True`) and the real `FirestoreAccess`: `test_carryover_the_real_guard_admits_an_approved_google_account`, `..._rejects_a_bad_token_with_401[5]`, `..._rejects_non_google_or_bad_uid_claims[6]`, `test_carryover_an_identity_outage_is_503_never_approval`, `test_carryover_a_malformed_access_record_fails_closed[5]`, `test_carryover_the_real_store_refuses_missing_denied_and_deleting_accounts[3]` and `test_carryover_a_firestore_outage_is_503_never_approval`. | `uv run pytest tests/test_session_access.py`, then `uv run pytest tests/test_qa_acceptance.py -k "carryover_the_real or carryover_an_identity or carryover_a_malformed or carryover_the_real_store or carryover_a_firestore"` | PASS | 48 passed, then 22 passed. Only `/health` is unguarded. Coverage rose from 30% to 100% on `identity/firebase.py` and from 70% to 88% on `identity/store.py`. Demo scene 5 shows the inventory tests. |
| **Carry-over: speech wiring fails closed** (the #64 rule, recorded for #43) | `test_speech_import_boundary.py`. In `test_qa_acceptance.py`: `test_carryover_the_running_app_imports_no_speech_code` (a subprocess imports `cst_session.main` and finds no `cst_session.speech*` modules), `test_carryover_a_voice_start_fails_closed` (`modality: "voice"` gets 400 `invalid_request`) and `test_carryover_no_route_takes_audio_or_a_websocket`. | `uv run pytest tests/test_speech_import_boundary.py tests/test_qa_acceptance.py -k "speech or voice or no_route or import"` | PASS | 27 passed. No route takes audio, and there are no websocket routes. Both `modality` and `SessionState.modality` are `Literal["text"]`. |

**6/6 criteria proven.**

### Security audit addition

| Check | Test | Command | Result |
|---|---|---|---|
| A body sent to `/v1/sessions/end` with a client-supplied `ended_by`, `at_ms`, `duration_ms` or `owner_uid` gets 400 `invalid_request`, and the grader is never called | `test_session_api.py::test_t7_end_body_strict` (6 cases) | `uv run pytest tests/test_session_api.py -k end_body_strict` | PASS: 6 passed |

## Checks

| Command | Result |
|---|---|
| `uv run pytest` | 1018 passed, 1 warning. The baseline before QA was 964 passed. |
| `uv run ruff check .` | All checks passed! |
| `uv run ruff format --check .` | 68 files already formatted |
| `uv run mypy .` | Success: no issues found in 66 source files |
| `uv run --with pytest-cov==6.0.0 pytest --cov=cst_session` | 97% total coverage. `api.py` 98%, `lifecycle.py` 99%, `main.py` 85%, `identity/firebase.py` 100%, `identity/store.py` 88%. |

## Mutation check

QA ran each mutant in a throwaway copy of the service, outside the repo. `test_qa_acceptance.py` killed
all 8 of them:

| # | Mutant | Killed |
|---|---|---|
| M1 | Every scenario sends the routine_intake prompt | yes |
| M2 | The limit check changes from `>=` to `>` | yes |
| M3 | A write is added to the access store | yes |
| M4 | A persona failure is swallowed, so the turn returns 200 | yes |
| M5 | An empty session is handed to the grader | yes |
| M6 | The end grace is removed | yes |
| M7 | The roles in the history are swapped | yes |
| M8 | `api.py` imports speech code | yes |

## Defects and observations

No defects block #31.

**Observation (residual risk, the same stateless class as L2-1).** A 503 `persona_unavailable` returns
no state, but the client still holds the signed state from before the failure. If the client then calls
`/v1/sessions/end` with that state, the server hands a completed attempt to the grader port.

- **Repro:** start a session, take one good turn (state S), then make the next turn fail with 503. Call
  `end(S)`, and the grader receives 1 handoff.
- **Where:** `cst_session/lifecycle.py:214-244`. `end` cannot know that a turn failed.
- **Effect today:** none, because the grader is `UnavailableGrader`, so the ending is unscored.
- **Risk once #68 lands:** it could score an attempt that a failure ended (RC-09/SCO-3).
- **Follow-up:** #32 must not call end after `persona_unavailable`, and #68 should weigh it. There is no
  #31 code change.

## Demo

- **Files:** `specs/031-session-service/demo/031-session-service.gif` (7.6 MB, 25.7 s, 1280 px, 8 fps)
  and `031-session-service.webm`.
- **Recorded by:** `specs/031-session-service/demo-recording.py`.
- **How:** the script runs the real app under uvicorn on 127.0.0.1 and sends real HTTP calls. It uses a
  synthetic account, a synthetic model over MockTransport, and a demo clock that fast-forwards.
- **Scenes, in order:**
  1. AC1: start, then a reply
  2. AC2: the time limit, expiry and a manual end
  3. AC4: model failures end unscored
  4. AC3: the content-free log audit
  5. The guard and speech carry-overs
  6. The checks
- **Frames checked:** QA extracted frames at 1 every 4 s and read them. Frames 1–6 come from the first
  take. Frame 5 was re-read in the final take; the only change between takes is the scene 5 command
  label.
  - **Secrets:** none. Signed states show as `v1.<signed state, N chars>`. No token or UID value appears
    in any frame.
  - **Names:** none. Session IDs are random UUIDs, and the replies are synthetic.
  - **Local paths:** none.
- Not published to `pr-media`.
