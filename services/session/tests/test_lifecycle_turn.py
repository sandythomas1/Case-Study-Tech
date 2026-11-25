"""Session turns: verification order, the time limit and the turn cap (T5, T9, FR-4, FR-5).

Each turn verifies the MAC, then the owner, then the scenario and version, then
the time on the server clock, before the persona is called. The time is checked
again when the reply arrives, so every signed turn starts before the limit.
"""

import json
from typing import Any

import pytest

from cst_session.lifecycle import FUTURE_START_TOLERANCE_MS, InvalidTurn
from cst_session.persona import PersonaFailure, PersonaUnavailable
from cst_session.state import (
    MAX_STATE_TURNS,
    Rejection,
    SessionState,
    StateRejected,
    StateTooLarge,
    StateTurn,
)
from tests.lifecycle_fakes import (
    LIMIT_MS,
    OTHER_OWNER,
    OWNER,
    T0,
    FakePersona,
    Harness,
    harness,
    run,
    started,
    take_turns,
    with_release,
    with_version,
)

STUDENT_TEXT = "Hi, I'm a counseling student. What brings you in today?"


def turn(h: Harness, token: str, text: str = STUDENT_TEXT, owner: str = OWNER) -> Any:
    return run(h.sessions.turn(owner_uid=owner, state=token, text=text))


def refused(
    h: Harness, token: str, text: str = STUDENT_TEXT, owner: str = OWNER
) -> StateRejected:
    with pytest.raises(StateRejected) as caught:
        turn(h, token, text, owner)
    error = caught.value
    assert error.__cause__ is None
    assert error.__context__ is None or error.__suppress_context__
    return error


def resign(h: Harness, token: str, **changes: Any) -> str:
    """Re-sign a verified state with ``changes``, as a key holder could."""
    fields = h.codec.verify(token).model_dump()
    fields.update(changes)
    return h.codec.sign(SessionState.model_validate(fields))


def events(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


# The happy path


def test_t5_a_turn_appends_the_student_and_client_turns_and_re_signs() -> None:
    h = harness()
    token = started(h)
    h.clock.at(1_500)
    h.persona.advance_ms = 700

    result = turn(h, token)
    state = h.codec.verify(result.state)

    assert result.reply == h.persona.reply_text
    assert [(t.speaker, t.text, t.at_ms) for t in state.turns] == [
        ("student", STUDENT_TEXT, 1_500),
        ("client", h.persona.reply_text, 2_200),
    ]
    assert result.remaining_ms == LIMIT_MS - 2_200
    assert state.model_dump(exclude={"turns"}) == h.codec.verify(token).model_dump(
        exclude={"turns"}
    )


def test_t5_the_persona_gets_the_verified_scenario_prompt_and_ordered_history() -> None:
    h = harness()
    token = take_turns(h, started(h, "resistant_client"), 2)

    turn(h, token, "Third student turn.")

    call = h.persona.calls[-1]
    assert call.system_prompt == h.prompts.for_scenario("resistant_client")
    assert [(m.speaker, m.text) for m in call.history] == [
        ("student", "Student turn 0."),
        ("client", h.persona.reply_text),
        ("student", "Student turn 1."),
        ("client", h.persona.reply_text),
        ("student", "Third student turn."),
    ]


def test_t6_the_system_prompt_is_identical_on_every_turn() -> None:
    h = harness()
    take_turns(h, started(h, "crisis_risk"), 5)

    prompts = {call.system_prompt for call in h.persona.calls}
    assert prompts == {h.prompts.for_scenario("crisis_risk")}
    assert all(STUDENT_TEXT not in prompt for prompt in prompts)


@pytest.mark.parametrize("scenario_id", ["routine_intake", "resistant_client"])
def test_t10_the_crisis_prompt_is_never_sent_for_another_scenario(
    scenario_id: str,
) -> None:
    h = harness()
    take_turns(h, started(h, scenario_id), 3)

    crisis = h.prompts.for_scenario("crisis_risk")
    assert all(call.system_prompt != crisis for call in h.persona.calls)


def test_t5_session_id_and_start_are_stable_over_ten_turns() -> None:
    h = harness()
    token = started(h)
    first = h.codec.verify(token)

    last = h.codec.verify(take_turns(h, token, 10))

    assert last.session_id == first.session_id
    assert last.started_at_ms == first.started_at_ms == T0
    assert len(last.turns) == 20


def test_t5_a_session_keeps_its_id_through_every_turn() -> None:
    h = harness()
    token = started(h)
    session_id = h.codec.verify(token).session_id

    for _ in range(10):
        token = take_turns(h, token, 1)
        assert h.codec.verify(token).session_id == session_id


def test_t5_turn_times_never_go_backwards_when_the_clock_does() -> None:
    h = harness()
    token = take_turns(h, started(h), 1, step_ms=5_000)
    h.clock.at(4_000)  # another instance, slightly behind

    state = h.codec.verify(turn(h, token).state)

    times = [t.at_ms for t in state.turns]
    assert times == sorted(times)
    assert times[2] == times[1] == 5_000


def test_t5_a_turn_logs_the_session_and_persona_latency_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    h = harness()
    token = started(h)
    capsys.readouterr()
    h.persona.advance_ms = 1_234

    turn(h, token)

    session_id = h.codec.verify(token).session_id
    assert events(capsys) == [
        {
            "severity": "INFO",
            "message": "session_turn",
            "event": "session_turn",
            "session_id": session_id,
            "duration_ms": 1_234,
        }
    ]


# The time limit (SES-5)


def test_t5_a_turn_one_millisecond_before_the_limit_is_accepted() -> None:
    h = harness()
    token = started(h)
    h.clock.at(LIMIT_MS - 1)
    h.persona.advance_ms = 0

    result = turn(h, token)

    assert h.codec.verify(result.state).turns[-1].at_ms == LIMIT_MS - 1
    assert result.remaining_ms == 1


def test_t5_a_turn_at_the_limit_is_refused_without_a_persona_call(
    capsys: pytest.CaptureFixture[str],
) -> None:
    h = harness()
    token = started(h)
    capsys.readouterr()
    h.clock.at(LIMIT_MS)

    error = refused(h, token)

    assert error.reason is Rejection.TIME_LIMIT
    assert error.code == "session_time_limit"
    assert h.persona.calls == []
    assert [e["event"] for e in events(capsys)] == ["state_rejected_time_limit"]


def test_t5_a_reply_that_arrives_at_the_limit_is_refused_with_no_state() -> None:
    h = harness()
    token = started(h)
    h.clock.at(LIMIT_MS - 100)
    h.persona.advance_ms = 100

    error = refused(h, token)

    assert error.code == "session_time_limit"
    assert len(h.persona.calls) == 1


def test_t5_every_signed_turn_starts_before_the_limit() -> None:
    h = harness()
    token = take_turns(h, started(h), 9, step_ms=60_000)

    assert all(t.at_ms < LIMIT_MS for t in h.codec.verify(token).turns)
    h.clock.at(LIMIT_MS)
    assert refused(h, token).code == "session_time_limit"


def test_t5_a_start_more_than_five_seconds_ahead_is_state_invalid() -> None:
    h = harness()
    ahead = resign(h, started(h), started_at_ms=T0 + FUTURE_START_TOLERANCE_MS + 1)

    error = refused(h, ahead)

    assert FUTURE_START_TOLERANCE_MS == 5_000
    assert error.code == "state_invalid"
    assert h.persona.calls == []


def test_t5_a_start_up_to_five_seconds_ahead_is_clock_skew_and_accepted() -> None:
    h = harness()
    ahead = resign(h, started(h), started_at_ms=T0 + FUTURE_START_TOLERANCE_MS)

    state = h.codec.verify(turn(h, ahead).state)

    assert state.turns[0].at_ms == 0


# Ownership and scenario binding


def test_t5_a_state_from_another_student_is_refused_without_a_persona_call(
    capsys: pytest.CaptureFixture[str],
) -> None:
    h = harness()
    token = started(h)
    capsys.readouterr()

    error = refused(h, token, owner=OTHER_OWNER)

    assert error.reason is Rejection.FOREIGN
    assert error.code == "state_invalid"
    assert h.persona.calls == []
    logged = events(capsys)
    assert [e["event"] for e in logged] == ["state_rejected_foreign"]
    assert OWNER not in str(logged) and OTHER_OWNER not in str(logged)


def test_t5_a_scenario_version_mismatch_is_state_invalid() -> None:
    h = harness()
    token = started(h)
    redeployed = harness(catalogue=with_version(h.catalogue, "routine_intake", "1.0.1"))

    error = refused(redeployed, token)

    assert error.reason is Rejection.SCENARIO
    assert error.code == "state_invalid"
    assert redeployed.persona.calls == []


def test_t5_a_scenario_unreleased_mid_session_is_state_invalid() -> None:
    h = harness()
    token = started(h)
    held_back = harness(catalogue=with_release(h.catalogue, "routine_intake", False))

    error = refused(held_back, token)

    assert error.reason is Rejection.SCENARIO
    assert held_back.persona.calls == []


@pytest.mark.parametrize(
    ("scenario_id", "crisis_opt_in"),
    [("crisis_risk", False), ("routine_intake", True)],
)
def test_t10_a_state_whose_opt_in_does_not_fit_its_scenario_is_state_invalid(
    scenario_id: str, crisis_opt_in: bool
) -> None:
    h = harness()
    token = resign(h, started(h, scenario_id), crisis_opt_in=crisis_opt_in)

    assert refused(h, token).reason is Rejection.SCENARIO
    assert h.persona.calls == []


def test_t1_a_tampered_state_is_refused_before_anything_else(
    capsys: pytest.CaptureFixture[str],
) -> None:
    h = harness()
    token = started(h)
    capsys.readouterr()
    tampered = token[:-2] + ("AA" if token[-2:] != "AA" else "BA")

    error = refused(h, tampered, owner=OTHER_OWNER)

    assert error.reason is Rejection.INVALID
    assert h.persona.calls == []
    assert events(capsys) == [
        {
            "severity": "WARNING",
            "message": "state_rejected_invalid",
            "event": "state_rejected_invalid",
        }
    ]


# The student's text (T6)


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("", id="empty"),
        pytest.param("   \n\t", id="blank"),
        pytest.param("x" * 2001, id="too-long"),
        pytest.param("hello\x00", id="nul"),
        pytest.param("hello‮", id="bidi-override"),
        pytest.param("﻿hello", id="byte-order-mark"),
    ],
)
def test_t6_an_invalid_turn_is_refused_without_a_persona_call(text: str) -> None:
    h = harness()
    token = started(h)

    with pytest.raises(InvalidTurn) as caught:
        turn(h, token, text)

    assert str(caught.value) == "invalid_turn"
    assert caught.value.__context__ is None or caught.value.__suppress_context__
    assert h.persona.calls == []


def test_t6_a_turn_of_2000_characters_is_accepted() -> None:
    h = harness()

    result = turn(h, started(h), "y" * 2000)

    assert h.codec.verify(result.state).turns[0].text == "y" * 2000


# Persona failures end the attempt with no state (FR-7)


@pytest.mark.parametrize("failure", list(PersonaFailure))
def test_a_persona_failure_returns_no_state_and_logs_its_code(
    failure: PersonaFailure, capsys: pytest.CaptureFixture[str]
) -> None:
    h = harness(persona=FakePersona(failure=failure))
    token = started(h)
    capsys.readouterr()

    with pytest.raises(PersonaUnavailable) as caught:
        turn(h, token)

    assert caught.value.code is failure
    logged = events(capsys)
    assert [e["event"] for e in logged] == ["persona_failed"]
    assert logged[0]["error_code"] == failure.value
    assert logged[0]["status_code"] == 503
    assert set(logged[0]) <= {
        "severity",
        "message",
        "event",
        "error_class",
        "error_code",
        "status_code",
        "duration_ms",
        "session_id",
    }


@pytest.mark.parametrize(
    "reply",
    [
        pytest.param("", id="empty"),
        pytest.param("  \n ", id="blank"),
        pytest.param("z" * 2001, id="too-long"),
        pytest.param("ok⁦", id="bidi-isolate"),
        pytest.param("ok\x07", id="control"),
    ],
)
def test_t6_a_reply_that_fails_turn_text_is_a_persona_failure(
    reply: str, capsys: pytest.CaptureFixture[str]
) -> None:
    h = harness(persona=FakePersona(reply_text=reply))
    token = started(h)
    capsys.readouterr()

    with pytest.raises(PersonaUnavailable) as caught:
        turn(h, token)

    assert caught.value.code is PersonaFailure.BAD_REPLY
    assert caught.value.__context__ is None or caught.value.__suppress_context__
    assert [e["event"] for e in events(capsys)] == ["persona_failed"]


# The turn and size caps (T9)


def state_with(h: Harness, token: str, count: int, text: str = "Synthetic.") -> str:
    speakers = ("student", "client")
    turns = [
        StateTurn(speaker=speakers[i % 2], text=text, at_ms=i)  # type: ignore[arg-type]
        for i in range(count)
    ]
    return resign(h, token, turns=[t.model_dump() for t in turns])


def fits(h: Harness, token: str, count: int, text: str) -> bool:
    try:
        state_with(h, token, count, text)
    except StateTooLarge:
        return False
    return True


def test_t9_the_last_turn_under_the_cap_is_accepted() -> None:
    h = harness()
    token = state_with(h, started(h), MAX_STATE_TURNS - 2)

    state = h.codec.verify(turn(h, token).state)

    assert len(state.turns) == MAX_STATE_TURNS


@pytest.mark.parametrize("count", [MAX_STATE_TURNS - 1, MAX_STATE_TURNS])
def test_t9_turn_limit_no_persona_call(
    count: int, capsys: pytest.CaptureFixture[str]
) -> None:
    h = harness()
    token = state_with(h, started(h), count)
    capsys.readouterr()

    error = refused(h, token)

    assert error.reason is Rejection.TURN_LIMIT
    assert error.code == "turn_limit_reached"
    assert h.persona.calls == []
    assert [e["event"] for e in events(capsys)] == ["state_rejected_turn_limit"]


def test_t9_a_turn_whose_state_would_be_over_the_size_cap_gets_turn_limit() -> None:
    wide = "語" * 2000
    h = harness(persona=FakePersona(reply_text=wide))
    token = started(h)
    count = 2
    while fits(h, token, count + 2, wide):
        count += 2
    near_cap = state_with(h, token, count, wide)

    error = refused(h, near_cap, wide)

    assert error.code == "turn_limit_reached"
    assert len(h.persona.calls) == 1
    assert len(h.codec.verify(near_cap).turns) == count
