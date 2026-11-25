"""T3: no conversation content or UID reaches a log or an error body (FR-8, AC3).

A canary string rides every place a student or the persona can put text: turn
text, the reply, rejected bodies, oversized bodies and an unexpected error. It
may only come back in a 200 body, where it belongs.
"""

import logging
from typing import Any

import pytest

from cst_session.api import MAX_BODY_BYTES
from cst_session.persona import PersonaFailure
from tests.api_fakes import TOKEN, Api, api
from tests.lifecycle_fakes import LIMIT_MS, OWNER, FakePersona

CANARY = "CANARY-5eb1-conversation-text"


class CanaryFailure(FakePersona):
    """Fails the way an adapter would, after seeing the canary text."""

    async def reply(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)  # type: ignore[arg-type]
        raise RuntimeError(CANARY)


def every_path(target: Api) -> list[Any]:
    """Drive the success path and each failure path with canary text."""
    responses = []
    state = target.start().json()["state"]
    first = target.turn(state, f"My friend {CANARY} said hello.")
    responses.append(first)
    state = first.json()["state"]
    responses.append(target.turn(state, CANARY * 200))  # invalid_turn
    responses.append(target.turn(state, f"{CANARY}\x00"))  # invalid_turn
    responses.append(
        target.post("/v1/sessions/turns", {"state": state, "text": 5, CANARY: CANARY})
    )
    responses.append(
        target.post("/v1/sessions", {"scenario_id": CANARY, "extra": CANARY})
    )
    responses.append(
        target.post("/v1/sessions/turns", {"state": f"v1.{CANARY}.x", "text": CANARY})
    )
    responses.append(target.post("/v1/sessions/end", {"state": f"{CANARY}.{CANARY}"}))
    responses.append(
        target.post(
            "/v1/sessions/turns",
            {"state": CANARY * (MAX_BODY_BYTES // 20), "text": "x"},
        )
    )
    responses.append(target.client.post(f"/v1/sessions/turns?q={CANARY}", json={}))
    responses.append(target.turn(state, CANARY, token=CANARY))  # 401
    responses.append(target.end(state))
    return responses


@pytest.fixture
def captured(
    caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> Any:
    caplog.set_level(logging.DEBUG)
    # The test client's own request log, which main.py raises to WARNING in
    # production (tests/test_session_main.py pins that).
    for name in ("httpx", "httpcore"):
        caplog.set_level(logging.WARNING, logger=name)

    def text() -> str:
        out, err = capsys.readouterr()
        return out + err + caplog.text

    return text


def assert_clean(responses: list[Any], logs: str) -> None:
    assert CANARY not in logs
    assert OWNER not in logs
    assert TOKEN not in logs
    for response in responses:
        if response.status_code != 200:
            assert CANARY not in response.text, response.status_code


def test_t3_canary_never_logged_or_echoed_on_any_path(captured: Any) -> None:
    target = api(FakePersona(reply_text=f"My cousin {CANARY} worries me."))
    responses = every_path(target)
    statuses = sorted({r.status_code for r in responses})
    assert statuses == [200, 400, 401, 409, 413]
    assert_clean(responses, captured())


@pytest.mark.parametrize("failure", list(PersonaFailure))
def test_t3_persona_failures_carry_no_content(
    captured: Any, failure: PersonaFailure
) -> None:
    target = api(FakePersona(failure=failure))
    state = target.start().json()["state"]
    response = target.turn(state, f"I think {CANARY} is upset.")
    assert response.status_code == 503
    assert_clean([response], captured())


def test_t3_unexpected_error_carries_no_content(captured: Any) -> None:
    target = api(CanaryFailure())
    state = target.start().json()["state"]
    response = target.turn(state, f"I think {CANARY} is upset.")
    assert response.status_code == 500
    assert_clean([response], captured())


def test_t3_time_limit_and_expiry_carry_no_content(captured: Any) -> None:
    target = api()
    state = target.turn(target.start().json()["state"], CANARY).json()["state"]
    target.h.clock.now += LIMIT_MS * 3
    responses = [target.turn(state, CANARY), target.end(state)]
    assert [r.status_code for r in responses] == [409, 409]
    assert_clean(responses, captured())


def test_t3_the_access_store_sees_only_point_reads_by_the_verified_uid() -> None:
    target = api()
    every_path(target)
    assert target.store.reads
    assert {method for method, _ in target.store.reads} == {"pending", "access_state"}
    assert {uid for _, uid in target.store.reads} == {OWNER}
