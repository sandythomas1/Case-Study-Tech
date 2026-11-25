# Threat model: session service (#31)

> Security agent, 2026-11-25, design time. The plan cites mitigations by ID. Every "Test:" line is required in
> the #31 suite. Sources: spec.md, ARCHITECTURE AD-1/2, §4, §7, §8, POLICY DAT/SES/ACC/AGT, the accounts guard,
> `cst_session` handoff/log/catalogue, the gateway template, `infra/session-grading/main.tf`, governance settings 4–7.

## Assets
- **A1 Conversation content**: turns, replies, the transcript in the state (DAT-1/7). **A2 State-signing key**
  (`CST_STATE_SIGNING_KEY`). **A3 Signed-state integrity**: UID, scenario id+version, session id, `started_at`,
  turns, conduct count, opt-in, save choice. **A4 Session SA token**: model predict, project-wide Firestore point
  reads, `firebaseauth.users.get`, the signing secret, grader invoke. **A5** Approval gate. **A6** Handoff
  integrity. **A7** Model spend and availability.

## Trust boundaries and entry points
- B1 device → gateway (untrusted; returns the state). B2 gateway → Cloud Run (invoker = gateway SA; the token is
  in `X-Forwarded-Authorization`). B3 → `aiplatform.us.rep.googleapis.com` with the SA token. B4 → Firestore and
  Identity Platform. B5 → grader port (in-process; HTTP in #68). B6 stdout/stderr → Logging and Error Reporting.
  B7 Secret Manager → env var.
- Entry points: `POST /v1/sessions`, `/turns` and `/end`; unauthenticated `GET /health` (the gateway's
  `/v1/sessions/health` is CONSTANT_ADDRESS to `/health`); `OPTIONS` preflights (`security: []`, sent to the
  backend); FastAPI's `/openapi.json`, `/docs` and `/redoc`; startup settings.

## Threats and required mitigations (most severe first)

**T1 HIGH — Forgery or tampering of the signed state.** A MAC over a re-serialized object, an `alg` field, an `==`
compare, or parsing before the MAC lets a student fabricate replies, move `started_at`, flip opt-in or save choice.
- Format `v1.<b64url(payload)>.<b64url(tag)>`, `tag = HMAC-SHA256(key, b"cst.session_state.v1." + payload_b64_ascii)`.
  The MAC covers the transmitted bytes, so canonicalization doesn't matter. No algorithm or key field. Stdlib
  `hmac`/`hashlib` only: no JWT/JOSE, no pickle, no compression.
- Order: length cap (T9) → exactly 3 parts with prefix `v1` → strict b64url (no padding) → `hmac.compare_digest`
  → only then `json.loads` (unique keys, no NaN, as in `handoff/validation.py`) → strict pydantic (`extra="forbid"`,
  `strict`, `hide_input_in_errors`, `repr=False` on text and UID). Any failure → `state_invalid`. A new state is
  built only from a verified state plus server fields. Never `model_construct` or `model_copy(update=)` on client data.
- Test: a bit flip per segment, a truncated or empty tag, a swapped payload, another key's tag, a `v2`/`none`
  prefix, extra or missing parts, padded or non-canonical b64, and duplicate keys under a valid test MAC all give
  `state_invalid`. Spies show no `json.loads` or pydantic call on a MAC failure and that `compare_digest` is used.

**T2 HIGH — A weaker identity-check copy, or an unguarded route (Spoofing/EoP).**
- Copy `bearer`, `_claims` (`check_revoked=True`, `google.com` provider, UID ≤128 without `/`, SDK error → 503),
  `eligible` (deletion marker) and `approved` (access read per request, no cache, malformed → 503) unchanged.
  The UID comes from the token only: no body `uid`, and `X-Apigateway-Api-Userinfo` is never trusted. Firestore
  reads are only `account_deletions/{uid}` and `access/{uid}`, because the SA can read any document by path.
- The guard runs before state verification and any model call: no oracle and no cost for unapproved callers.
- `app.state.approval_guard` plus the copied route-inventory test: allow-list `{("GET","/health")}`, websocket
  routes counted, any Mount or raw route fails, and `create_app` has no gate flag or env read (copy `test_no_setting_turns_the_gate_off`).
- Test: on each of the 3 routes, a missing, forged or revoked token → 401; pending, denied or missing → 403
  `access_not_approved`; a deletion marker → 403 `account_deletion_pending`; a store outage → 503. Every case has 0
  persona-port calls and no state in the response. A revoke between turns makes the next turn fail.

**T3 HIGH — A1 leaks through errors and logs.** FastAPI's default 422 echoes `input`, meaning the turn and the
state. Leaks also come from pydantic errors, `HTTPException` detail, httpx errors holding the model's error body,
startup tracebacks (Error Reporting reads stderr) and uvicorn access logs.
- Copy from accounts: the `RequestValidationError` → fixed 400 handler, `ContentFreeErrors` innermost,
  no-store/nosniff, `--no-access-log` in the CMD (checked by `test_body_logging_off.py`).
- Error bodies come from a closed set of constant codes. No `str(exc)`, `response.text` or model error body goes
  anywhere. Map `ValidationError`/`HandoffRejected` at the boundary. httpx/httpcore stay at WARNING. No
  BackgroundTasks holding content. `Settings` uses `hide_input_in_errors` and `SecretStr`. Query strings → 400.
  Logs carry `session_id`/`scenario_*` only, never the UID.
- Test (canary sweep): a canary turn through success, an extra-field 400, an oversize body, bad/expired/foreign
  state, a model 500 echoing it, a model timeout, a handler `RuntimeError(canary)` and a port raising
  `ValueError(canary)`. The canary is absent from capsys, caplog at DEBUG and every non-200 body.

**T4 HIGH — SSRF or token exfiltration on the model call, or a governance bypass.** `cst-deploy` can edit env
vars, so a bad `CST_AGENT_PLATFORM_LOCATION` or `CST_PERSONA_MODEL` could send the token and content elsewhere or to `global`.
- The host comes from the closed map `{"us": "https://aiplatform.us.rep.googleapis.com"}`. Anything else
  (`global`, empty, unset) stops startup, with no default. Model `^gemini-[a-z0-9.-]{1,48}$`, project
  `^[a-z][a-z0-9-]{4,28}[a-z0-9]$`, fixed path `/v1/projects/{p}/locations/us/publishers/google/models/{m}:generateContent`.
- httpx: `follow_redirects=False`, `trust_env=False` (ignores `HTTPS_PROXY`), TLS verify on, timeout under the
  30 s gateway deadline (for example 20 s), response cap (for example 256 KiB). google-auth ADC with the
  `cloud-platform` scope. The token is never logged.
- The body is a typed model with only `contents`, `systemInstruction`, `generationConfig` and `safetySettings`:
  no tools, `toolConfig`, `cachedContent`, `store` or `sessionResumption`, and no Interactions or Live API (settings 4–7).
- Test: startup refuses `global`, `us-central1.evil.test`, `us/..`, empty, unset, and a model containing `/:?#`.
  The fake transport sees the exact URL. A 302 → persona failure. A recursive key scan of every request finds none
  of `tools googleSearch googleMaps store sessionResumption cachedContent`.

**T5 HIGH — Time-limit bypass, replay, reuse beyond AD-2.**
- The server clock (injected) sets `started_at`, `session_id` (uuid4) and `scenario.version` at start, and every
  re-sign copies them unchanged. The server computes `at_ms`, `duration_ms` and `ended_by`, never the body.
- A turn is rejected at `now ≥ started_at + limit`, the limit read from `startable(state.scenario_id)` (SES-5). End
  is accepted until `limit + G`, a fixed grace the plan sets (for example 60 s), so a time-limit end works.
  `started_at > now + 5 s` → `state_invalid`. `owner_uid != token uid` → `state_foreign`. Expiry and foreign codes
  come only after the MAC. Every turn and end re-checks `startable()` and the loaded version; a mismatch → reject.
- AD-2 covers undo and forking from an older state. It does not cover resetting the clock, splicing states,
  changing scenario or opt-in, or grading a session twice (needs #68 create-only on `session_id`; see L2-1).
- Test: a turn at limit−1 ms is accepted and at limit rejected; end at `limit+G−1` accepted and at `+G` rejected; a
  future `started_at` is rejected; `started_at` and `session_id` are stable over 10 turns; a body
  `ended_by`/`at_ms`/`duration_ms` → 400; user B with user A's state → `state_foreign` and no model call.

**T6 MEDIUM — Prompt injection from student turns (and into the grader through replies).**
- The interim prompt goes only in `systemInstruction`; turns are `role:user` and replies `role:model`, never
  templated into the system text. With no tools, an injection can't act.
- Student text must pass `TurnText` (else 400 `invalid_turn`, state unchanged). Unicode tags (U+E0000–E007F) and
  every `Cf` except ZWJ/ZWNJ are stripped from the copy sent to the model.
- The reply is untrusted. Take text parts only, with `maxOutputTokens`. A `functionCall`, no candidate, a safety
  block, an empty reply or one failing `TurnText` is a persona failure (FR-7). The state is signed, not
  encrypted, so it holds no prompt and no server-only data.
- Test: an "ignore previous instructions" turn appears only in a `user` part, and the system text is
  byte-identical on every turn; tag characters never reach the request; a reply with `functionCall`, 2001
  characters, a bidi control or empty text ends the attempt unscored.

**T7 MEDIUM — A partial or unvalidated handoff reaches the grader port (RC-09, SCO-1/3).**
- End builds `CompletedSession` only from a verified, unexpired, owned state, and the port gets only what
  `validate_handoff` returned: `status="completed"`, `warnings=0`, and `crisis={"opted_in":true}` only for
  `crisis_risk`. A persona failure returns a terminal `session_ended_unscored` with no new state. No signed state
  ends on an unanswered student turn. Until #68 the port reports unavailable → an unscored ending.
- Test: the port spy receives the `validate_handoff` return object itself (`is`). It gets 0 calls for an invalid,
  expired or foreign state, for zero turns, and after a persona failure or timeout.

**T8 MEDIUM — Signing-key format, handling and rotation.** VERIFIED: `bootstrap_signing_key.py` stores **32 raw
random bytes** (the base64 is only the API encoding), and Terraform injects them as an **env var**. SUSPECTED: a
NUL truncates the key and non-UTF-8 bytes pass through surrogateescape, so a naive `.encode()` yields a
different or shorter key (L2-2).
- Startup decodes the key one documented way and requires exactly 32 bytes, else it fails with a fixed message
  (no bytes, no length). There is no default, tests inject the key through `create_app`, and it is used only
  for state MACs. `latest` means rotation drops in-flight states (accepted, lost-content path); no dual-key
  support. `inject_state_signing_key` defaults to false, so a #31 deploy needs the owner's flip, and without the
  key startup fails.
- Test: a missing, 31-byte, 33-byte or undecodable key stops startup. A canary key appears in no output.

**T9 MEDIUM — DoS and cost amplification (A7).** The state can reach megabytes (500 × 2000 characters). Every turn
resends the history (quadratic tokens). Capacity is 2 instances × 20 concurrency × 512 MiB, and start is free and parallel.
- An ASGI body cap runs before parsing, on Content-Length and the streamed count (for example 1 MiB → 413). The
  state has a `max_length`. A turn cap in the signed state sits well under 500 (the plan sets it), with an
  optional minimum interval. Endpoints are sync `def` (threadpool), as in accounts, so blocking I/O never stalls the loop.
- Test: oversized and chunked bodies → 413 before JSON parsing; the turn past the cap → `turn_limit` with no model call (L2-3).

**T10 MEDIUM — Start input, SES-2, scenario binding.** `scenario_id` is one of the 3 ids; strict bools
`crisis_opt_in` and `save_transcript`; `extra="forbid"`. `ScenarioUnavailable` gives one code for unknown and
unreleased. `requires_opt_in` without `true` → `opt_in_required`. The prompt is chosen only from the verified
state's scenario and opt-in.
- Test: crisis without opt-in, or with the string `"true"`, is refused; a non-crisis start with opt-in gives
  `crisis` null; unreleased answers like unknown; the crisis prompt is never sent for another state.

## Owner decisions needed
- **L2-1 (AC2 vs AD-1/AD-2).** "Further turns are rejected after manual end" can't be enforced statelessly: the
  pre-end state stays valid until `limit+G`. (a, recommended) Treat it as AD-2 scope, bounded by expiry and #68's
  create-only write on `session_id`. (b) A content-free `ended_sessions/{session_id}` marker: a new store item
  and one extra read per turn.
- **L2-2 (key encoding).** (a, recommended) The bootstrap stores base64url text and is re-run; the service decodes
  strictly to 32 bytes. (b) A secret file volume, an infra change. (c) Keep the raw bytes and accept startup
  failure on unlucky bytes.
- **L2-3 (abuse/cost).** Without state there is no per-UID rate limit. (a, recommended) Accept it for the MVP,
  approved users only, with the T9 caps and a billing alert. (b) A gateway quota. (c) A Firestore counter.
- No L3. The design persists no content and exposes no secret.

## LOW (one line each)
- The service serves `/health`, because the gateway uses CONSTANT_ADDRESS; FR-1's `/v1/sessions/health` is gateway-side only. Health is static: no model, Firestore or key info.
- `docs_url`, `redoc_url` and `openapi_url` are None. CORS copies accounts (exact origins, no `*`/`null`/regex, no credentials), and startup refuses `*`.
- The UID shapes differ: accounts accepts ≤128 characters without `/`, the handoff only `[A-Za-z0-9]`. A mismatch fails closed (unscored).
- Forks and parallel turns from one state are within AD-2. The plan documents them.
- New dependencies are pinned in `uv.lock` and checked with `pip-audit`, with no GenAI SDK. `CST_AGENT_PLATFORM_LOCATION` needs #138 applied before deploy.

## Audit (2026-11-25)

> Security agent, review time. Scope: the working tree against `dev` on `feature/31-session-service`, uncommitted.
> Owner decisions: L2-1 (a), L2-2 (a), L2-3 (a), and the student speaks first. This is static review only. `pip-audit`
> and `gitleaks` are not installed, so neither ran. Paths are under `services/session/` unless they say otherwise.

| Control | Status | Evidence (file:line) |
|---|---|---|
| T1 format, order, compare_digest | MET | `cst_session/state.py:174-189`: cap, fullmatch, `compare_digest`, then the strict decode and parse (`:206-237`). Tests: `tests/test_state_codec.py:140-284` |
| T2 guard copy, inventory, ordering | MET | `cst_session/identity/firebase.py:20-45` and `store.py:50-63` are verbatim, with point reads only. The guard is at `cst_session/api.py:262-295` and every route uses `Depends(approved)` at `:303-335`. Tests: `tests/test_identity_copy.py:93`, `tests/test_session_access.py:63-212` |
| T3 no echo, no content in logs | MET | `api.py:206-211` (fixed 400), `:187` (innermost wrapper), `:105-107` (query string), `main.py:29,35-47`, `Dockerfile:8` `--no-access-log`, `agent_platform.py:241-242` (a failed body is never read), `lifecycle.py:302-323`. Tests: `tests/test_session_no_content.py:86-122` |
| T4 closed host, client hardening, body keys | MET | `cst_session/persona/agent_platform.py:35-42,93-108,111-139,191-197,235-250`. The adapter sends no `safetySettings`, a subset of the allow-list. Tests: `tests/test_agent_platform.py:139-210`, `tests/test_session_main.py:82-97` |
| T5 server clock, limit, grace, binding | MET | `lifecycle.py:183,197-199,221-225,255-274`. A foreign state returns `state_invalid` (`state.py:86-93`), which is stricter than planned. Tests: `tests/test_lifecycle_turn.py:186-302`, `tests/test_lifecycle_end.py:242-292`. Gap: no `/end` test for extra `ended_by`/`duration_ms` (the code refuses them through `api.py:45,62`) |
| T6 role separation, stripping, reply checks | MET | `agent_platform.py:130` (`maxOutputTokens`), `:142-170`, `:253-299`; `lifecycle.py:326-330`. Tests: `tests/test_agent_platform.py:220-307`, `tests/test_lifecycle_turn.py:107,347-408` |
| T7 validated handoff only | MET | `lifecycle.py:214-244` (the port gets the `validate_handoff` object at `:235`), `cst_session/grading.py`. Tests: `tests/test_lifecycle_end.py:67-204` |
| T8 / L2-2 key encoding | MET | Service: `state.py:60,141-148`, `main.py:53`. Script: `infra/session-grading/bootstrap_signing_key.py:31-46`. Runbook: `docs/runbooks/session-grading-deploy.md:67-68`. Tests: `tests/test_state_key.py`, `tests/test_bootstrap_signing_key.py`, `tests/test_session_main.py:62` |
| T9 body cap, state cap, turn cap | MET | `api.py:89-137`, `state.py:55-56,164-172`, `lifecycle.py:185`. Tests: `tests/test_session_api.py:290-313`, `tests/test_state_codec.py:305-336`, `tests/test_lifecycle_turn.py:443-468` |
| T9 sync `def` endpoints | PARTIAL | The handlers are `async def` (`api.py:304,321,332`). The guard is sync, so it runs in the threadpool, and the ADC refresh uses `asyncio.to_thread` (`agent_platform.py:208`), so no blocking I/O runs on the loop. State verification of up to 1 MB of CPU work still runs on the loop |
| T10 start input, opt-in, prompt binding | MET | `api.py:48-53`, `lifecycle.py:137-173,265-274`. Tests: `tests/test_lifecycle_start.py:52-163`, `tests/test_session_api.py:154-165`, `tests/test_lifecycle_turn.py:117,302` |
| L2-1 post-end reuse recorded | MET | `docs/POLICY.md:235`. The once-per-session grading rule depends on #68 |
| L2-3 caps | MET | 200 turns, 1 MB state, `maxOutputTokens` 400, a 20 s deadline and the time limit (as above) |
| L2-3 billing alert | MISSING | No budget or billing alert exists in `infra/` or `docs/runbooks/session-grading-deploy.md` |
| Student speaks first | MET | `lifecycle.py:137-173` makes no model call. Test: `tests/test_lifecycle_start.py:79` |
| LOW: static `/health`, docs off, CORS | MET | `api.py:297-299`, `:183`, `:168-195` |
| LOW: UID shape mismatch fails closed | MET | `lifecycle.py:235-237` returns `not_gradable` |
| LOW: dependencies pinned, no GenAI SDK | PARTIAL | The deps are pinned and hashed in `uv.lock` and `requirements.txt` (`pyproject.toml` diff), with no GenAI SDK. `pip-audit` did not run |
| LOW: #138 rename applied before deploy | PARTIAL | `infra/session-grading/main.tf:237` still sets `CST_VERTEX_LOCATION`, but the service requires `CST_AGENT_PLATFORM_LOCATION` (`main.py:40`). Startup fails closed until #138 lands (`tests/test_session_main.py:97`) |
