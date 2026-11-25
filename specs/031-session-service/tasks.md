# Tasks: Session service for lifecycle, persona turns and time limits (#31)

> **Phase:** Tasks · **Status:** done · **Date:** 2026-11-25
> These tasks come from `plan.md`. Paths are relative to `services/session/` unless they start at
> the repo root. Each test that proves a threat control has the threat ID in its name
> (`test_t1_*` … `test_t10_*`). L2-1, L2-2 and L2-3 were working assumptions; the owner accepted them on 2026-11-25 (see spec.md).
> #31 merges only after PR #138.

## Legend
- `[ ]` todo · `[~]` in progress · `[x]` done
- **(dep: N)** marks a dependency, and **[P]** means the task can run in parallel (its files are disjoint from the others).
- **Owners:** `@implementer` or `@qa`. Each task cites the FR, AC and threat ID it covers, plus the plan sections it needs.

## Batch 1: domain (no framework or vendor imports)

- [x] 1. Add the dependencies to `pyproject.toml`: fastapi, uvicorn[standard], pydantic-settings,
  firebase-admin (accounts floors) and google-auth[requests]. Then run `uv lock`. Done when
  `uv sync` succeeds and nothing else is added (FR-5). @implementer · plan: Stack & Dependencies
- [x] 2. **T8 key decoding.** Write `decode_signing_key()` in `cst_session/state.py`: unpadded
  base64url, 43 characters, strict decode to exactly 32 bytes, round-trip equal, and a fixed error
  message. Add `tests/test_state_key.py::test_t8_*` for padded, standard-alphabet, 31/33-byte,
  NUL, whitespace and non-ASCII inputs. Also assert the message never contains the value
  (FR-3). (dep: 1) @implementer · plan: Data Model (Key)
- [x] 3. **T8 bootstrap.** In `infra/session-grading/bootstrap_signing_key.py` (repo root), store
  `urlsafe_b64encode(token_bytes(32)).rstrip(b"=")` as secret text. Add a unit test that the output
  decodes through `decode_signing_key`. Add one line to `docs/runbooks/session-grading-deploy.md`
  saying to re-run it before injection (L2-2, owner decided 2026-11-25). [P] @implementer · plan: Data Model (Key)
- [x] 4. **T1 codec.** Add `SessionState` v1 and `StateCodec.sign()/verify()` to `state.py`, with
  the token format, domain-separated HMAC and verification steps 1–3. Add
  `tests/test_state_codec.py::test_t1_*` for each tamper case (bit flip in the payload, tag or
  prefix; wrong version; padding; a non-alphabet character; a truncated part; extra or duplicate
  keys; NaN). Add a spy test showing that `json.loads` and model validation are never called on a
  MAC failure, and assert that `compare_digest` is used (FR-3, FR-4). (dep: 2)
  @implementer · plan: Data Model
- [x] 5. **T9 caps in the codec.** Add `MAX_STATE_TURNS = 200` and `MAX_STATE_CHARS`, and make
  `sign()` refuse an oversize result. Add `test_t9_*`: a state at the cap verifies, and one over
  the cap is never signed (FR-4). (dep: 4) @implementer · plan: Data Model (Size caps)
- [x] 6. **Ports.** Add `persona/port.py` (`PersonaPort`, `PersonaReply`,
  `PersonaUnavailable(code)` with fixed messages) and `grading.py` (`GraderPort`,
  `GradingUnavailable`, `UnavailableGrader`). Done when mypy is clean (FR-5, FR-6). [P]
  @implementer · plan: Architecture
- [x] 7. **Interim prompts.** Add `scenarios/prompts.py` (a strict loader that raises
  `PromptError`), three synthetic `.txt` prompts of at most 1,500 characters each, and a README
  marking them interim. Add tests for a missing or extra file, an empty file, oversize, non-UTF-8,
  and no write path. Extend the `test_scenario_write_paths.py` scope to cover the loader
  (FR-5, AC1). [P] @implementer · plan: Interim persona prompts
- [x] 8. **T5 and T10 lifecycle: start.** In `lifecycle.py`, add `Clock` and `Sessions.start`:
  `startable()`, the opt-in rule, a uuid4 session id, the server `started_at_ms`, and no turns.
  Add `test_t10_*`: unknown and unreleased scenarios raise the same error, opt-in is required for
  `crisis_risk`, and `crisis_opt_in` is false elsewhere (FR-2). (dep: 4, 6, 7)
  @implementer · plan: Data Model, Who speaks first, API Contract
- [x] 9. **T5 lifecycle: turn.** Add `Sessions.turn`: verification steps 4–6 (owner, scenario and
  version, future start), the time check before and after the persona call, non-decreasing
  `at_ms`, and the turn and size limit. The persona receives the prompt for the verified
  scenario. Add `test_t5_*` with a fake clock covering L−1/L, a late reply, a foreign UID, a
  version mismatch, an unreleased scenario mid-session, and `started_at` more than 5 s in the
  future. Add `test_t9_turn_limit_no_persona_call` (FR-4, FR-5, AC1, AC2). (dep: 8)
  @implementer · plan: Time-limit semantics, Data Model (Verification order)
- [x] 10. **T7 lifecycle: end.** Add `Sessions.end`: the grace window, `ended_by`, `duration_ms`,
  `empty_session`, the `CompletedSession` build, `validate_handoff`, `not_gradable`, and a
  port call with the returned object. Add `test_t7_*`: the port receives the same object (`is`),
  crisis is only set for `crisis_risk`, zero turns or an invalid state make 0 port calls, and the
  result is never `graded`. Add `test_t5_end_grace` at L+G−1 and L+G (FR-6, AC2, AC4). (dep: 9)
  @implementer · plan: API Contract (End flow), Time-limit semantics
- [x] 11. **Domain import boundary.** Add `tests/test_domain_import_boundary.py`: the domain
  modules import no fastapi, starlette, httpx, `google.*` or firebase_admin. Add the new content
  modules to `CONTENT_HANDLING_MODULES` in `test_speech_import_boundary.py`, and extend
  `test_logging_calls.py` so only `content_free_log` is used (FR-8, AC3). (dep: 10)
  @implementer · plan: Architecture, Observability

## Batch 2: adapters, HTTP and packaging

- [x] 12. **T2 identity copy.** Copy `bearer`, `_claims`/`verify`, `pending`, `access_state`,
  `_stored_state`, `storage_operation` and their exceptions verbatim into `identity/`. Add
  `tests/test_identity_copy.py::test_t2_copy_matches_accounts`, which compares ASTs with
  `services/accounts/cst_accounts/{firebase,store,domain}.py` (FR-1). (dep: 11)
  @implementer · plan: Security & Privacy (T2)
- [x] 13. **T4 and T6 persona adapter.** Add `persona/agent_platform.py`: the closed host map, the
  model and project patterns, the fixed path, an AsyncClient with no redirects and
  `trust_env=False`, a 256 KiB cap, ADC refresh under a lock, a typed body with three keys,
  stripping Cf and tag characters, the reply acceptance rules, a 20 s `asyncio.timeout`, and the
  failure codes (FR-5, FR-7). (dep: 11) [P] @implementer · plan: Persona call
- [x] 14. **T4 and T6 adapter tests.** Write `tests/test_agent_platform.py` with MockTransport:
  - `test_t4_*`: exact URL, no `global`, a recursive key scan of the body finds no tools,
    googleSearch, googleMaps, store, sessionResumption or cachedContent, and a 302 is a failure.
  - `test_t6_*`: the prompt appears only in `systemInstruction`, roles are mapped, tag characters
    are stripped, and functionCall, block, empty and invalid replies fail.
  - Timeout and the deadline budget assertion.
  - A canary in an upstream error body never surfaces.

  (FR-5, FR-7, AC1, AC4). (dep: 13) @implementer · plan: Persona call
- [x] 15. **API app.** Write `api.py` `create_app(...)` with:
  - routes `/health`, `POST /v1/sessions`, `/v1/sessions/turns` and `/v1/sessions/end`;
  - the copied guard chain and `app.state.approval_guard`;
  - `docs_url`, `redoc_url` and `openapi_url` set to None;
  - the error map and response bodies from the plan.

  No route decorator string may contain "scenario" (FR-1, FR-2, FR-4). (dep: 10, 12) @implementer
  · plan: API Contract, Security & Privacy
- [x] 16. **T3 and T9 middleware.** Add:
  - ContentFreeErrors (innermost);
  - the copied 400 validation handler;
  - no-store and nosniff headers;
  - query-string rejection;
  - the ASGI body cap (413 before parsing, chunked too);
  - CORS copied from accounts, refusing `*` and `null`.

  (FR-8, AC3). (dep: 15) @implementer · plan: API Contract, Security & Privacy (T3, T9)
- [x] 17. **T2 guard and inventory tests.** In `tests/test_session_access.py`, add `test_t2_*`:
  - the matrix copied from accounts `test_access.py`: 401, both 403s and 503;
  - a persona spy with 0 calls on every rejection;
  - a revoke between turns;
  - the route inventory with allow-list `{("GET","/health")}`, which counts websocket routes and
    fails on a Mount;
  - no gate flag or env.

  (FR-1, carry-over #72). (dep: 16) @implementer · plan: Security & Privacy (T2)
- [x] 18. **API flow tests.** In `tests/test_session_api.py`, cover:
  - start → turn → turn → end with fakes;
  - every route error code;
  - `test_t10_start_body_strict`, for extra keys and non-bool values;
  - `test_t9_body_cap_413`;
  - `test_t1_tampered_state_409`;
  - `test_t5_foreign_state_409`;
  - a persona failure returning 503 with no state;
  - an end response with no state.

  (FR-2–FR-7, AC1, AC2, AC4). (dep: 16) @implementer · plan: API Contract, Testing Strategy
- [x] 19. **T3 canary sweep.** In `tests/test_session_no_content.py::test_t3_*`, run canary text
  through the success path and every failure path. Assert the canary never appears in capsys,
  caplog at DEBUG or any non-200 body. Assert the access-store fake sees only point reads and no
  UID is logged (FR-8, AC3). (dep: 18) @implementer · plan: Security & Privacy (T3), Observability
- [x] 20. **Wiring and packaging.** Add:
  - `main.py`: `Settings` with the `CST_` prefix, `hide_input_in_errors`, `SecretStr`,
    `CST_AGENT_PLATFORM_LOCATION`, and `app_factory()`;
  - `Dockerfile` and `requirements.txt`, copied from accounts with `--no-access-log`;
  - a README update.

  Write `test_t8_startup_fails_without_key` and `test_t4_startup_fails_on_global_or_missing_location`.
  Done when `uv run pytest`, `ruff` and `mypy` all pass (FR-3, FR-5). (dep: 13, 16) @implementer
  · plan: Deployment Target, Stack & Dependencies

## Verification (maps 1:1 to spec acceptance criteria)

- [x] 21. **AC1.** Show the persona spy and adapter tests for each scenario. Include a transcript
  of one synthetic text session against fakes, recorded for the PR demo (an API transcript GIF).
  (dep: 20) @qa · plan: Testing Strategy
- [x] 22. **AC2.** Show the time-limit, late-reply, manual-end and grace tests passing, and the
  named L2-1 test that pins the behavior after end (owner decided 2026-11-25). (dep: 20) @qa · plan: Time-limit
  semantics, Working assumptions
- [x] 23. **AC3.** Show the canary sweep, logging-call, import-boundary and write-path test output.
  Grep the diff to confirm no Firestore writes and no new log fields. (dep: 20) @qa · plan:
  Observability, Security & Privacy
- [x] 24. **AC4.** Show that each persona failure code gives 503 with no state, that 0 grader calls
  are made, and that end is only `unscored`. (dep: 20) @qa · plan: Persona call, API Contract
- [x] 25. **Carry-overs.** Show the route-inventory output, including websocket routes. Note in the
  PR that there is no speech route and that the #64 fail-closed rule applies to #43. Confirm the
  PR body states the #138 merge dependency. (dep: 20) @qa · plan: Security & Privacy (T2)
