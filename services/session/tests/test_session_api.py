"""The session HTTP contract, against fakes (FR-2 to FR-7, AC1, AC2, AC4).

Each route's success body and every route error code from the plan's API
Contract, plus the request limits and response headers (T9, T10).
"""

from collections.abc import Iterator
from typing import Any

import pytest

from cst_session.api import MAX_BODY_BYTES, create_app
from cst_session.lifecycle import END_GRACE_MS
from cst_session.persona import PersonaFailure
from cst_session.state import MAX_STATE_CHARS, MAX_STATE_TURNS, SessionState, StateCodec
from tests.api_fakes import ORIGIN, TOKEN, FakeAuth, FakeStore, api
from tests.lifecycle_fakes import LIMIT_MS, FakePersona, Harness, with_release
from tests.state_fixtures import OTHER_KEY

START = {
    "scenario_id": "routine_intake",
    "crisis_opt_in": False,
    "save_transcript": False,
    "modality": "text",
}
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def resign(h: Harness, token: str, **changes: Any) -> str:
    fields = h.codec.verify(token).model_dump()
    fields.update(changes)
    return h.codec.sign(SessionState.model_validate(fields))


def with_turns(h: Harness, token: str, count: int) -> str:
    speakers = ("student", "client")
    turns = [
        {"speaker": speakers[i % 2], "text": "Synthetic.", "at_ms": i}
        for i in range(count)
    ]
    return resign(h, token, turns=turns)


def assert_headers(response: Any) -> None:
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


# --- the happy path -------------------------------------------------------------


def test_start_turn_turn_end_flow() -> None:
    target = api(FakePersona(reply_text="Work has been piling up."))
    started = target.start()
    assert started.status_code == 200
    body = started.json()
    assert set(body) == {"session_id", "state", "time_limit_ms", "remaining_ms"}
    assert body["time_limit_ms"] == LIMIT_MS == body["remaining_ms"]

    target.h.clock.now += 1_000
    first = target.turn(body["state"], "What brings you in?")
    assert first.status_code == 200
    assert first.json()["reply"] == "Work has been piling up."
    assert set(first.json()) == {"reply", "state", "remaining_ms"}
    assert first.json()["remaining_ms"] == LIMIT_MS - 1_000

    target.h.clock.now += 1_000
    second = target.turn(first.json()["state"], "How long has that been going on?")
    assert second.status_code == 200
    assert len(target.persona.calls) == 2
    assert [m.speaker for m in target.persona.calls[1].history] == [
        "student",
        "client",
        "student",
    ]

    ended = target.end(second.json()["state"])
    assert ended.status_code == 200
    assert ended.json() == {
        "outcome": "unscored",
        "reason": "grading_unavailable",
        "ended_by": "student",
    }
    assert len(target.h.grader.received) == 1
    for response in (started, first, second, ended):
        assert_headers(response)


def test_end_with_no_turns_is_an_empty_session_with_no_state() -> None:
    target = api()
    ended = target.end(target.start().json()["state"])
    assert ended.status_code == 200
    assert ended.json() == {
        "outcome": "unscored",
        "reason": "empty_session",
        "ended_by": "student",
    }
    assert target.h.grader.received == []


def test_end_after_the_limit_inside_the_grace_is_ended_by_time_limit() -> None:
    target = api()
    state = target.turn(target.start().json()["state"]).json()["state"]
    target.h.clock.now += LIMIT_MS + END_GRACE_MS - 1
    ended = target.end(state)
    assert ended.status_code == 200
    assert ended.json()["ended_by"] == "time_limit"
    assert "state" not in ended.json()


def test_health() -> None:
    response = api().client.get("/health")
    assert response.json() == {"status": "ok"}
    assert_headers(response)


# --- route error codes ----------------------------------------------------------


def test_unknown_and_unreleased_scenarios_are_the_same_404() -> None:
    unknown = api().start("free_chat")
    held = api(catalogue=with_release(api().h.catalogue, "resistant_client", False))
    unreleased = held.start("resistant_client")
    for response in (unknown, unreleased):
        assert response.status_code == 404
        assert response.json() == {"detail": "scenario_unavailable"}


def test_crisis_scenario_without_opt_in_is_403() -> None:
    response = api().start("crisis_risk")
    assert response.status_code == 403
    assert response.json() == {"detail": "opt_in_required"}
    ok = api().start("crisis_risk", crisis_opt_in=True)
    assert ok.status_code == 200


@pytest.mark.parametrize(
    "change",
    [
        {"extra": 1},
        {"owner_uid": "synthUid002"},
        {"uid": "synthUid002"},
        {"crisis_opt_in": "false"},
        {"crisis_opt_in": 0},
        {"save_transcript": None},
        {"save_transcript": "true"},
        {"modality": "voice"},
        {"scenario_id": "Routine_Intake"},
        {"scenario_id": "routine-intake"},
        {"scenario_id": "a" * 65},
        {"scenario_id": 7},
    ],
)
def test_t10_start_body_strict(change: dict[str, Any]) -> None:
    target = api()
    response = target.post("/v1/sessions", {**START, **change})
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid_request"}
    assert_headers(response)


@pytest.mark.parametrize("missing", sorted(START))
def test_t10_start_body_needs_every_field(missing: str) -> None:
    body = {k: v for k, v in START.items() if k != missing}
    assert api().post("/v1/sessions", body).json() == {"detail": "invalid_request"}


@pytest.mark.parametrize(
    "body",
    [
        {"state": "x"},
        {"text": "hello"},
        {"state": "x", "text": 5},
        {"state": 5, "text": "hello"},
        {"state": "", "text": "hello"},
        {"state": "x", "text": "hello", "owner_uid": "synthUid002"},
        ["state", "text"],
        "state",
    ],
)
def test_turn_body_strict(body: object) -> None:
    response = api().post("/v1/sessions/turns", body)
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid_request"}


@pytest.mark.parametrize(
    "extra",
    [
        {"ended_by": "time_limit"},
        {"ended_by": "student"},
        {"at_ms": 0},
        {"duration_ms": 1},
        {"duration_ms": 600_000, "ended_by": "student"},
        {"owner_uid": "synthUid002"},
    ],
)
def test_t7_end_body_strict(extra: dict[str, Any]) -> None:
    # End timing comes only from the server clock and the verified state, so a
    # client-supplied ending field is refused before anything is verified.
    target = api()
    state = target.turn(target.start().json()["state"]).json()["state"]
    response = target.post("/v1/sessions/end", {"state": state, **extra})
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid_request"}
    assert target.h.grader.received == []
    assert_headers(response)


def test_non_json_body_is_400() -> None:
    target = api()
    response = target.client.post(
        "/v1/sessions", content=b"scenario_id=routine_intake", headers=AUTH
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid_request"}


@pytest.mark.parametrize("text", ["", "   ", "x" * 2001, "a\x00b"])
def test_an_invalid_turn_is_400_without_a_persona_call(text: str) -> None:
    target = api()
    response = target.turn(target.start().json()["state"], text)
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid_turn"}
    assert target.persona.calls == []


def test_t1_tampered_state_409() -> None:
    target = api()
    state = target.start().json()["state"]
    tampered = state[:-2] + ("AA" if state[-2:] != "AA" else "BA")
    for response in (target.turn(tampered), target.end(tampered)):
        assert response.status_code == 409
        assert response.json() == {"detail": "state_invalid"}
    assert target.persona.calls == []


def test_t1_state_signed_with_another_key_is_409() -> None:
    target = api()
    verified = target.h.codec.verify(target.start().json()["state"])
    forged = StateCodec(OTHER_KEY).sign(verified)
    assert target.turn(forged).json() == {"detail": "state_invalid"}


def test_t5_foreign_state_409() -> None:
    target = api()
    state = target.start().json()["state"]
    target.auth.tokens["synthetic-id-token-9"] = "synthUid009"
    target.store.access["synthUid009"] = target.store.access["synthUid001"]
    for response in (
        target.turn(state, token="synthetic-id-token-9"),
        target.end(state, token="synthetic-id-token-9"),
    ):
        assert response.status_code == 409
        assert response.json() == {"detail": "state_invalid"}
    assert target.persona.calls == [] and target.h.grader.received == []


def test_a_turn_at_the_time_limit_is_409() -> None:
    target = api()
    state = target.start().json()["state"]
    target.h.clock.now += LIMIT_MS
    response = target.turn(state)
    assert response.status_code == 409
    assert response.json() == {"detail": "session_time_limit"}
    assert target.persona.calls == []


def test_a_turn_at_the_turn_limit_is_409() -> None:
    target = api()
    state = with_turns(target.h, target.start().json()["state"], MAX_STATE_TURNS)
    response = target.turn(state)
    assert response.status_code == 409
    assert response.json() == {"detail": "turn_limit_reached"}
    assert target.persona.calls == []


def test_an_end_after_the_grace_is_session_expired() -> None:
    target = api()
    state = target.start().json()["state"]
    target.h.clock.now += LIMIT_MS + END_GRACE_MS
    response = target.end(state)
    assert response.status_code == 409
    assert response.json() == {"detail": "session_expired"}


@pytest.mark.parametrize("code", list(PersonaFailure))
def test_a_persona_failure_is_503_with_no_state(code: PersonaFailure) -> None:
    target = api(FakePersona(failure=code))
    response = target.turn(target.start().json()["state"])
    assert response.status_code == 503
    assert response.json() == {"detail": "persona_unavailable"}
    assert_headers(response)
    assert target.h.grader.received == []


# --- limits, headers, CORS, unexpected errors -----------------------------------


@pytest.mark.parametrize("path", ["/health", "/v1/sessions", "/v1/sessions/turns"])
def test_a_query_string_is_400(path: str) -> None:
    target = api()
    if path == "/health":
        response = target.client.get(f"{path}?debug=1")
    else:
        response = target.client.post(f"{path}?owner_uid=x", json=START, headers=AUTH)
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid_request"}
    assert_headers(response)
    assert target.store.reads == []


def test_t9_body_cap_413() -> None:
    target = api()
    big = {"state": "x" * MAX_BODY_BYTES, "text": "hello"}
    response = target.post("/v1/sessions/turns", big)
    assert response.status_code == 413
    assert response.json() == {"detail": "request_too_large"}
    assert_headers(response)
    assert target.store.reads == [] and target.auth.verified == []


def test_t9_chunked_body_over_the_cap_is_413() -> None:
    target = api()

    def chunks() -> Iterator[bytes]:
        for _ in range(MAX_BODY_BYTES // 65_536 + 2):
            yield b"x" * 65_536

    response = target.client.post("/v1/sessions/turns", content=chunks(), headers=AUTH)
    assert response.status_code == 413
    assert response.json() == {"detail": "request_too_large"}
    assert target.auth.verified == []


def test_t9_a_max_size_state_fits_under_the_body_cap() -> None:
    assert MAX_STATE_CHARS + 2_000 * 4 + 64 < MAX_BODY_BYTES
    target = api()
    response = target.post(
        "/v1/sessions/turns", {"state": "x" * MAX_STATE_CHARS, "text": "hi"}
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "state_invalid"}


def test_an_invalid_content_length_is_400() -> None:
    target = api()
    response = target.client.post(
        "/v1/sessions",
        content=b"{}",
        headers={**AUTH, "Content-Type": "application/json", "Content-Length": "abc"},
    )
    assert response.status_code == 400


def test_an_unexpected_error_is_a_content_free_500_with_headers() -> None:
    class Broken(FakePersona):
        async def reply(self, **_: Any) -> Any:
            raise RuntimeError("CANARY-unexpected-detail")

    target = api(Broken())
    response = target.turn(target.start().json()["state"])
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}
    assert "CANARY" not in response.text
    assert_headers(response)


def test_cors_allows_only_the_configured_origin_without_credentials() -> None:
    target = api()
    preflight = {"Access-Control-Request-Method": "POST"}
    allowed = target.client.options(
        "/v1/sessions", headers={"Origin": ORIGIN, **preflight}
    )
    assert allowed.headers["access-control-allow-origin"] == ORIGIN
    assert "access-control-allow-credentials" not in allowed.headers
    other = target.client.options(
        "/v1/sessions", headers={"Origin": "https://evil.example.test", **preflight}
    )
    assert "access-control-allow-origin" not in other.headers


@pytest.mark.parametrize("origins", [("*",), ("null",), (ORIGIN, "*")])
def test_cors_refuses_wildcard_and_null_origins(origins: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="CST_ALLOWED_ORIGINS"):
        create_app(FakeAuth(), FakeStore(), api().h.sessions, origins)


def test_docs_and_openapi_are_off() -> None:
    client = api().client
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_session_routes_accept_post_only(method: str) -> None:
    client = api().client
    for path in ("/v1/sessions", "/v1/sessions/turns", "/v1/sessions/end"):
        assert client.request(method, path, headers=AUTH).status_code == 405
