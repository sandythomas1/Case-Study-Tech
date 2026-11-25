# Plan: Session service for lifecycle, persona turns and time limits (#31)

> **Phase:** Plan · **Status:** draft · **Date:** 2026-11-25
> Derived from `spec.md` (clarified) and `threat-model.md`, whose mitigations are cited by ID (T1–T10).
> **Owner decided 2026-11-25** marks a former working assumption that the owner accepted (see spec.md). The plan makes no
> gateway, Terraform or `.github/` change. The one change outside `services/session` is the
> bootstrap key-encoding fix (L2-2).

## Summary

FastAPI adds three guarded routes and `/health` to `services/session`. Every response carries a
state that the server signs with HMAC-SHA256 and the client holds (AD-1). Before any work, each
turn and end verifies the MAC, then the owner UID, then the scenario, then the time on the server
clock.

A turn sends the verified history through a persona port. Its production adapter calls REST
`generateContent` on the Gemini Enterprise Agent Platform `us` endpoint over httpx with ADC.

End builds the #66 handoff, runs `validate_handoff` and gives the result to a grader port. Until
#68, that port always reports grading unavailable, so every ending is unscored.

The identity guard is copied verbatim from accounts, with a drift test that fails if the copy
changes. Nothing is stored, and logging goes only through `content_free_log`.

## Architecture

```
app ─► API Gateway (JWT) ─► session (Cloud Run, private)
        api.py: body cap → no-query → approved guard (copied) → handler
          └► lifecycle.py ── state.py (sign/verify) ── Catalogue + prompts
               ├► PersonaPort ── AgentPlatformPersona (httpx + google-auth) → aiplatform.us.rep.googleapis.com
               └► GraderPort  ── UnavailableGrader (until #68)
        identity/ (copied): Firebase verify + Firestore point reads
```

Layers follow ARCHITECTURE §5:

- **Domain:** `state.py`, `lifecycle.py`, `persona/port.py`, `grading.py` and
  `scenarios/prompts.py`. They import only the stdlib, pydantic and other domain modules. An
  import-boundary test bans fastapi, starlette, httpx, `google.*` and firebase_admin from them.
- **Adapters:** `persona/agent_platform.py` and `identity/*`.
- **Wiring:** `main.py`.

Handlers are `async def`. The copied guard dependencies stay sync `def`, so their I/O runs in the
threadpool and never blocks the event loop (T9). The persona call is async, so it can be bounded by
`asyncio.timeout`.

| Module (`services/session/cst_session/`) | Responsibility |
|---|---|
| `state.py` | `SessionState` v1, `StateCodec(key)` `sign()`/`verify()`, `StateRejected(reason)`, `decode_signing_key()` |
| `lifecycle.py` | `Sessions.start/turn/end`, time rules, handoff build, `Clock` protocol |
| `scenarios/prompts.py`, `scenarios/prompts/<id>.txt` | strict read-only loader + 3 interim prompts |
| `persona/port.py` | `PersonaPort`, `PersonaReply`, `PersonaUnavailable(code)` |
| `persona/agent_platform.py` | REST adapter: endpoint map, request allow-list, reply checks |
| `grading.py` | `GraderPort`, `GradingUnavailable`, `UnavailableGrader` |
| `identity/{domain,firebase,store}.py` | copied identity check, revocation, deletion marker, access record |
| `api.py` | `create_app(...)`, middleware, routes, error map, `app.state.approval_guard` |
| `main.py` | `Settings`, `app_factory()`, httpx and httpcore loggers at WARNING (T3) |

## Stack & Dependencies

- **Runtime:** Python 3.12, FastAPI and uvicorn, the same as accounts, so no ADR.
- **Storage:** no data store. The service only reads `access/{uid}` and `account_deletions/{uid}`.
- **New dependencies:** `fastapi`, `uvicorn[standard]`, `pydantic-settings` and `firebase-admin`
  at the accounts floors, plus `google-auth[requests]`. The `requests` extra is already in the
  tree through firebase-admin. Firestore is used transitively, as in accounts. No GenAI,
  aiplatform or JWT library is added (T1, T4).
- **Lock and audit:** run `uv lock`, and run `pip-audit` in CI.
- **Packaging:** `Dockerfile` and `requirements.txt` are copied from accounts, and the container
  runs `uvicorn cst_session.main:app_factory --factory … --no-access-log` (T3).
- **Follow-up:** adding the image build to `deploy.yml` is a `.github/` change, so the owner
  reviews it separately.

## Deployment Target

- **Platform:** the GCP dev project (CLAUDE.md), using the existing `infra/session-grading`.
- **Cloud Run `session`:** 180 s timeout, concurrency 20, at most 2 instances, 512 MiB, private to
  the gateway SA.
- **Owner steps (AG-9):** set `inject_state_signing_key = true` and roll out the image.
- **Environment:**
  - `CST_PROJECT_ID` and `CST_PERSONA_MODEL`.
  - `CST_AGENT_PLATFORM_LOCATION`, renamed by PR #138. **#31 must not merge before #138.** It has
    no default, so a missing or unknown value stops startup (T4).
  - `CST_ALLOWED_ORIGINS`, a JSON list.
  - `CST_STATE_SIGNING_KEY`.
  - `CST_GRADING_*` stays unused until #68.
- **Skill:** `skills/gcp_architecture.md`.

## Data Model: the signed state (contract v1)

**Token (T1).** `v1.<payload_b64>.<tag_b64>`, with both parts in unpadded base64url and
`tag = HMAC-SHA256(key, b"cst.session_state.v1." + payload_b64_ascii)`.

- The MAC covers the exact bytes sent. Canonical encoding exists only so tests are deterministic.
- There is no `alg`, no `kid` and no compression.
- A future v2 makes old states `state_invalid`, which sends the app down the lost-content path.
  That is acceptable for sessions of at most 10 minutes.

The payload is `json.dumps(model_dump(mode="json"), ensure_ascii=False, separators=(",",":"),
sort_keys=True, allow_nan=False)` encoded as UTF-8. The model is strict, with `extra="forbid"`.
`owner_uid` and turn text are `repr=False`.

| Field | Rule |
|---|---|
| `session_id` | uuid4, lowercase. Set at start and never changed |
| `owner_uid` | Verified token UID, 1–128 characters |
| `scenario_id`, `scenario_version` | Taken from `Catalogue.startable()` at start |
| `started_at_ms` | Server epoch ms. Never read from a request |
| `modality` | `"text"` (Literal) |
| `crisis_opt_in` | True only if the scenario `requires_opt_in` and the student opted in |
| `save_transcript` | The student's start choice |
| `conduct_warnings` | int 0–1, always 0 here (#33) |
| `turns` | `[{speaker: "student"\|"client", text: TurnText, at_ms: int ≥ 0}]`, at most `MAX_STATE_TURNS` |

**Size caps (T9).**

- `MAX_STATE_TURNS = 200`, which is 100 exchanges, well under the handoff's 500.
- `MAX_STATE_CHARS = 1_000_000`.
- The ASGI body cap is 1 MiB. It checks `Content-Length` and counts streamed bytes, and returns
  413 before anything is parsed.
- Invariant: **the server never signs a state it could not accept back.** A turn whose new token
  would be over the cap gets `turn_limit_reached` and no new state, so the previous state still
  fits in an end request.

**Key (T8, L2-2, owner decided 2026-11-25).**

- `CST_STATE_SIGNING_KEY` is unpadded base64url text, 43 characters from `[A-Za-z0-9_-]`.
- It must decode strictly to exactly 32 bytes and re-encode to the same text. Otherwise startup
  stops with a fixed message that shows neither the value nor its length.
- `infra/session-grading/bootstrap_signing_key.py` will store
  `base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=")` as text. The owner re-runs it
  before turning injection on.
- There is one key at a time, so a rotation drops in-flight sessions.

**Verification order (T1, T5).** Each step runs only if the previous one passed.

1. Check `max_length`, then a full match on `^v1\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]{43}$`. Nothing is
   decoded at this step.
2. Recompute the HMAC over the domain prefix and `payload_b64`, decode the tag strictly, and
   compare with `hmac.compare_digest`. A mismatch gives `state_invalid`.
3. Decode the payload strictly. Parse it with `json.loads` using the unique-key and no-constant
   hooks from `handoff/validation.py`, then validate it with the strict model. Any failure gives
   `state_invalid`.
4. Check that `owner_uid` equals the token UID. A mismatch returns `state_invalid` and logs
   `state_rejected_foreign`.
5. `Catalogue.startable(scenario_id)` must succeed, and its `version` must equal
   `scenario_version`. Otherwise `state_invalid`.
6. Apply the time rules. A `started_at_ms` later than now + 5 s is `state_invalid`.

New states are built only from a verified state plus server-computed fields. Client data never
goes through `model_construct` or `model_copy(update=)`.

## Time-limit semantics (SES-5, T5)

- **Clock:** only the server clock counts, through an injected `Clock`. Skew between instances is
  at NTP level, so milliseconds. `elapsed = max(0, now − started_at_ms)`, and
  `L = time_limit_minutes × 60,000` from the catalogue.
- **Turn:** rejected with 409 `session_time_limit` if `elapsed ≥ L`. The check runs again after
  the persona replies, and a late reply is refused the same way with no state. So every signed
  turn has `at_ms < L`.
- **End:** accepted while `elapsed < L + END_GRACE_MS`, with the grace set to 60,000. After that it
  returns 409 `session_expired`. `ended_by` is `time_limit` if `elapsed ≥ L`, and `student`
  otherwise. `duration_ms = min(elapsed, L)`.
- **`at_ms`:** never decreases. A student turn gets `max(elapsed, last.at_ms)`, and a client turn
  gets `max(elapsed_after_reply, student.at_ms)`.
- **`remaining_ms`:** every 200 carries `max(0, L − elapsed)`.

## Who speaks first (L2-4, owner decided 2026-11-25)

The student opens, so start makes no model call and returns a state with no turns. Four things
support this:

- FR-2.
- Rubric `SP-1`, "Opens with role and purpose", whose negative example is "Student, first turn".
- All three #66 fixtures open with a student turn at `at_ms: 0`.
- The start route keeps the 15 s default gateway deadline, which is too short for a model call.

Against this, SDD Figure 5 shows "Client · turn 1". A client greeting can be added later without
changing the format.

## Persona call (FR-5, governance settings 4–7, T4, T6)

- **Endpoint (T4):**
  - Closed map `{"us": "https://aiplatform.us.rep.googleapis.com"}`. Any other location, including
    `global`, stops startup.
  - Path `/v1/projects/{p}/locations/us/publishers/google/models/{m}:generateContent`.
  - Model must match `^gemini-[a-z0-9.-]{1,48}$` and project `^[a-z][a-z0-9-]{4,28}[a-z0-9]$`.
- **Transport (T4):** one `httpx.AsyncClient(follow_redirects=False, trust_env=False)`, TLS
  verified, with a 256 KiB read cap. ADC comes from `google.auth.default(scopes=[cloud-platform])`.
  The token is refreshed in a thread under a lock, only when invalid, and is never logged.
- **Request (T4, T6):** a typed model with three keys only:
  - `systemInstruction`: the scenario prompt, the same every turn.
  - `contents`: student turns as `user` and client turns as `model`.
  - `generationConfig`: `candidateCount 1`, `maxOutputTokens 400`, `temperature 0.8`.

  There are no `tools`, `toolConfig`, `cachedContent`, `store`, `sessionResumption` or
  `safetySettings`. The copy sent to the model strips tag characters (U+E0000–E007F) and other
  `Cf` characters except ZWJ and ZWNJ. The state keeps the original text.
- **Reply (T6):** accept a candidate with `finishReason` `STOP` or `MAX_TOKENS`, and take the
  trimmed join of its non-`thought` text parts. Refuse a `functionCall` part, an empty reply, a
  block, or text that fails `TurnText`.
- **Deadline:** `PERSONA_DEADLINE_S = 20`, applied with `asyncio.timeout` around the token refresh
  and the call. That leaves about 10 s of the 30 s gateway deadline for the guard, verification
  and signing. No retries. A test asserts `PERSONA_DEADLINE_S + 8 ≤ 30`.
- **Failure (FR-7, AC4):** all of the above, plus a timeout, a transport error, HTTP ≥ 300
  (including redirects), an auth error or bad JSON, raises `PersonaUnavailable(code)`.
  - Codes: `persona_timeout`, `_unreachable`, `_http_error`, `_auth`, `_bad_response`,
    `_blocked`, `_bad_reply`.
  - The upstream body is never read.
  - The API returns 503 `persona_unavailable` with no state, and the attempt is over.

## Interim persona prompts

Each scenario gets one synthetic prompt of at most 1,500 characters at
`scenarios/prompts/{routine_intake,resistant_client,crisis_risk}.txt`. Each prompt:

- keeps the persona in role as the client;
- never coaches, scores or hints (SES-7);
- keeps replies short;
- keeps going after a crisis disclosure (SES-8).

A `README` marks the prompts as interim until #67 replaces them. The loader works like
`load_catalogue`: exactly the three ids, UTF-8, non-empty and within the cap, loaded once at
startup. Any failure raises `PromptError`, and nothing writes files.

## API Contract

Requests are strict JSON with `extra="forbid"`. Errors use `{"detail": "<code>"}`.

- **Copied guard bodies:** unchanged from accounts: 401 `"Sign in again."`, 403
  `access_not_approved` or `account_deletion_pending`, and 503 `"Service temporarily
  unavailable."`.
- **Bad input:** any query string or validation failure returns 400 `invalid_request` and echoes
  nothing (T3). An oversized body returns 413 `request_too_large`.
- **No docs:** `docs_url`, `redoc_url` and `openapi_url` are all `None`.
- **Headers:** every response sets `Cache-Control: no-store` and `nosniff`.

| Service path | Request | 200 | Route errors |
|---|---|---|---|
| `GET /health` | none | `{"status":"ok"}` | unguarded |
| `POST /v1/sessions` | `scenario_id` (`^[a-z_]{1,64}$`), `crisis_opt_in`, `save_transcript` (bools), `modality: "text"` | `session_id`, `state`, `time_limit_ms`, `remaining_ms` | 404 `scenario_unavailable` (same for unknown and unreleased); 403 `opt_in_required` |
| `POST /v1/sessions/turns` | `state` (≤ `MAX_STATE_CHARS`), `text` | `reply`, `state`, `remaining_ms` | 400 `invalid_turn`; 409 `state_invalid`, `session_time_limit`, `turn_limit_reached`; 503 `persona_unavailable` |
| `POST /v1/sessions/end` | `state` | `outcome: "unscored"`, `reason` (`grading_unavailable`, `empty_session` or `not_gradable`), `ended_by` | 409 `state_invalid`, `session_expired` |

**Health path:** the service serves `/health`. FR-1's `/v1/sessions/health` is the gateway path,
which the gateway maps to `/health` with `CONSTANT_ADDRESS`.

**App handling (#32):**

| Code | App action |
|---|---|
| `session_time_limit`, `turn_limit_reached` | call end |
| `state_invalid`, `session_expired` | lost-content path (flow 8) |
| `persona_unavailable` | unscored ending (REC-4) |

#68 adds `outcome: "graded"` without breaking this contract. No request carries a UID (T2).

**End flow (FR-6, T7):**

1. Verify the state.
2. With zero turns, return `empty_session` and build no handoff.
3. Otherwise build the `CompletedSession`:
   - `status: "completed"` and conduct warnings 0;
   - crisis `{"opted_in": true}` only for `crisis_risk`;
   - student turns with `input: "text"` and uncertain and conduct_warning false;
   - indexes 1..n.
4. Run `validate_handoff`. `HandoffRejected` returns `not_gradable`, failing closed.
5. The port receives exactly the object it returned. `GradingUnavailable` returns
   `grading_unavailable`. The service never scores.

## Security & Privacy (threat-model.md)

- **T1:** the token format and verification order above, using stdlib `hmac` and `hashlib` only.
- **T2:**
  - `bearer`, `_claims`/`verify`, `pending`, `access_state`, `_stored_state` and
    `storage_operation` are copied verbatim into `identity/`. `test_identity_copy.py` compares
    their ASTs with the accounts sources.
  - The chain `bearer → token_owner → signed_in → approved` runs before any state or model work.
    Behavior tests are copied from `test_access.py`.
  - The route inventory allows only `{("GET","/health")}`. Websocket routes count, and any Mount
    or raw route fails.
  - `create_app` has no gate flag and reads no env.
- **T3:**
  - The copied 400 handler, with `ContentFreeErrors` innermost.
  - No-store headers, `--no-access-log`, and a closed set of codes.
  - `session_id` is logged only after the MAC passes, and the UID is never logged.
  - `Settings` uses `hide_input_in_errors` and `SecretStr`.
- **T4:** the endpoint map and patterns, no redirects, `trust_env=False`, and a request-key
  allow-list.
- **T5:** server clock only, the verification order, and identity fields copied unchanged.
- **T6:** the prompt goes only in `systemInstruction`, plus the strip step and the reply rules.
- **T7:** the end flow. A persona failure returns no state, so the server never signs a state that
  ends unanswered.
- **T8:** the key rules above. The key has no default and is used only for state MACs.
- **T9:** the body cap and both state caps. An oversize state is never signed.
- **T10:** a strict start body, one 404 for all unavailable scenarios, and the prompt taken only
  from the verified scenario.
- **CORS:** as accounts. Exact origins only; `*` and `null` are refused at startup; no credentials.
- **Accepted under AD-2:** forking an older state and sending parallel turns (see L2-1).

## Observability

All logging goes through `content_free_log`, with no new fields:

| Event | Fields |
|---|---|
| `session_started` | session_id, scenario_id, scenario_version |
| `session_turn` | session_id, duration_ms (persona latency) |
| `persona_failed` | `log_error`: code, status_code, duration_ms |
| `state_rejected_{invalid,foreign,scenario,time_limit,expired,turn_limit}` | WARNING |
| `session_ended_{student,time_limit}` | duration_ms |
| `grading_unavailable` | WARNING |

Logs never carry a UID, text, state or token. Metrics and alerts are an infra follow-up.

## Testing Strategy

Tests make no network calls. They use fake identity, store, persona and clock, plus a spy grader.
Each test name carries the threat ID it covers, for example `test_t1_*`.

- **Unit:** codec, time rules, caps, handoff build, prompts and key decoding.
- **Adapter:** `httpx.MockTransport`.
- **API:** `TestClient`.

| AC | Proof |
|---|---|
| AC1 | The persona spy gets the scenario prompt as `systemInstruction` and the ordered history as `contents`. The reply returns with a new state that verifies. The adapter test pins the exact URL and body. An optional synthetic smoke test is run by the owner |
| AC2 | A turn at L−1 ms is accepted and one at L is rejected. A late reply is rejected. An end after L records `time_limit`, and one at L+G returns `session_expired`. The end response has no state. A named test pins the L2-1 behavior |
| AC3 | A canary session runs through success and every failure path. No canary appears in stdout, stderr, caplog at DEBUG or any error body. The store fake sees only point reads. The existing logging, import-boundary and write-path tests pass |
| AC4 | Every persona failure returns 503 with no state and 0 grader calls. End returns only `unscored`. The port receives the `validate_handoff` object itself (`is`) |
| Carry-over | The route inventory, including websocket routes, matches the guard by identity. There is no speech route, and #64's fail-closed rule is noted for #43 |

## Risks & Trade-offs

**Risks**

- **Merging before #138:** startup fails closed. The Lead sequences #138 first, and the PR says so.
- **Thinking tokens:** they can exhaust `maxOutputTokens`, leaving an empty reply and an unscored
  ending. Mitigations: short prompts, a 400 cap, and an owner smoke test. #67 tunes this.
- **Crisis replies:** default safety filters may block them, which fails closed and ends the
  session unscored. #67 owns this. Changing `safetySettings` needs the owner.
- **AST drift test:** it misses the closures inside accounts' `create_app`. Copied behavior tests
  cover them.

**Trade-offs**

- **Signed, not encrypted:** a student can read their own transcript, which the app already holds
  (§7). This saves a second key.
- **No key ID and no dual keys:** a rotation loses at most 10 minutes of sessions.
- **One client code for every persona failure:** the cause appears only in logs.
- **`startable()` and version checked on every turn:** a flag flip or a redeploy ends live
  sessions as lost content. CD-3 wins.

## Owner decisions (L2, 2026-11-25)

- **L2-1 (owner decided 2026-11-25):** AC2 after a manual end is accepted as AD-2 scope.
  - End returns no state. A client that kept the pre-end state can still send turns until L and
    end again until L + G.
  - #68's create-only write keyed on `session_id` blocks a second score.
  - If accepted, the POLICY §10 AD-2 row is widened.
  - An `ended_sessions/{id}` marker was rejected: it adds a store and a write path.
- **L2-2 (owner decided 2026-11-25):** the key is stored as base64url text, the bootstrap is re-run, and the
  service decodes strictly to exactly 32 bytes.
- **L2-3 (owner decided 2026-11-25):** no per-UID rate limit for the MVP. Bounded by the T9 caps,
  2 instances × 20 concurrency, and an owner-set billing alert.
- **L2-4 (owner decided 2026-11-25):** the student speaks first.

**Skills consulted:** `system_design`, `software_architecture`, `security`, `gcp_architecture`,
`testing`.
