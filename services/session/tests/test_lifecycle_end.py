"""Session end: the grace window, the handoff build and the grader port (T7, T5, FR-6).

End verifies the state like a turn, builds the completed session only from the
verified state, runs ``validate_handoff``, and gives the grader port exactly the
object it returned. The service never scores, so the outcome is always unscored.
"""

import json
from typing import Any

import pytest

import cst_session.lifecycle as lifecycle
from cst_session.handoff import CompletedSession, validate_handoff
from cst_session.handoff.contract import StudentTurn
from cst_session.lifecycle import END_GRACE_MS, Ended
from cst_session.state import Rejection, SessionState, StateRejected
from tests.lifecycle_fakes import (
    LIMIT_MS,
    OTHER_OWNER,
    OWNER,
    Harness,
    harness,
    run,
    started,
    take_turns,
)


def end(h: Harness, token: str, owner: str = OWNER) -> Ended:
    return run(h.sessions.end(owner_uid=owner, state=token))


def refused(h: Harness, token: str, owner: str = OWNER) -> StateRejected:
    with pytest.raises(StateRejected) as caught:
        end(h, token, owner)
    return caught.value


def resign(h: Harness, token: str, **changes: Any) -> str:
    fields = h.codec.verify(token).model_dump()
    fields.update(changes)
    return h.codec.sign(SessionState.model_validate(fields))


def events(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


@pytest.fixture
def validated(monkeypatch: pytest.MonkeyPatch) -> list[CompletedSession]:
    """Every object ``validate_handoff`` returned during the test."""
    returned: list[CompletedSession] = []

    def spy(payload: object) -> CompletedSession:
        session = validate_handoff(payload)
        returned.append(session)
        return session

    monkeypatch.setattr(lifecycle, "validate_handoff", spy)
    return returned


# The port and the handoff (T7)


def test_t7_the_port_receives_the_same_object_validate_handoff_returned(
    validated: list[CompletedSession],
) -> None:
    h = harness()
    token = take_turns(h, started(h), 3)

    result = end(h, token)

    assert len(validated) == 1
    assert len(h.grader.received) == 1
    assert h.grader.received[0] is validated[0]
    assert result == Ended("grading_unavailable", "student")
    assert result.outcome == "unscored"


def test_t7_the_handoff_is_built_from_the_verified_state() -> None:
    h = harness()
    token = take_turns(h, started(h, save_transcript=False), 2, step_ms=2_000)
    state = h.codec.verify(token)
    h.clock.at(9_000)

    end(h, token)

    session = h.grader.received[0]
    assert session.session_id == state.session_id
    assert session.owner_uid == OWNER
    assert (session.scenario.id, session.scenario.version) == (
        "routine_intake",
        "1.0.0",
    )
    assert session.modality == "text"
    assert session.status == "completed"
    assert session.ended_by == "student"
    assert session.duration_ms == 9_000
    assert session.conduct.warnings == 0
    assert session.crisis is None
    assert session.save_transcript is False
    assert [turn.index for turn in session.turns] == [1, 2, 3, 4]
    assert [(t.speaker, t.text, t.at_ms) for t in session.turns] == [
        (t.speaker, t.text, t.at_ms) for t in state.turns
    ]
    students = [t for t in session.turns if isinstance(t, StudentTurn)]
    assert len(students) == 2
    assert all(
        (t.input, t.uncertain_recognition, t.conduct_warning) == ("text", False, False)
        for t in students
    )


def test_t7_crisis_is_set_only_for_the_crisis_scenario() -> None:
    for scenario_id, expected in [
        ("crisis_risk", True),
        ("routine_intake", False),
        ("resistant_client", False),
    ]:
        h = harness()
        end(h, take_turns(h, started(h, scenario_id), 1))

        crisis = h.grader.received[0].crisis
        assert (crisis is not None and crisis.opted_in) is expected, scenario_id


def test_t7_zero_turns_is_an_empty_session_with_no_handoff(
    validated: list[CompletedSession], capsys: pytest.CaptureFixture[str]
) -> None:
    h = harness()
    token = started(h)
    capsys.readouterr()
    h.clock.at(30_000)

    result = end(h, token)

    assert result == Ended("empty_session", "student")
    assert validated == []
    assert h.grader.received == []
    assert [e["event"] for e in events(capsys)] == ["session_ended_student"]


def test_t7_a_session_the_handoff_refuses_is_not_gradable_with_no_port_call(
    capsys: pytest.CaptureFixture[str],
) -> None:
    h = harness()
    # The state allows any UID up to 128 characters; the handoff wants letters
    # and digits only, so this session fails closed at the handoff.
    token = take_turns(h, started(h), 1)
    odd_owner = resign(h, token, owner_uid="synth-uid-001")
    capsys.readouterr()

    result = end(h, odd_owner, owner="synth-uid-001")

    assert result == Ended("not_gradable", "student")
    assert h.grader.received == []
    logged = events(capsys)
    assert [e["event"] for e in logged] == [
        "session_ended_student",
        "handoff_rejected_malformed",
    ]
    assert "synth-uid-001" not in str(logged)


@pytest.mark.parametrize("case", ["tampered", "foreign", "expired"])
def test_t7_an_invalid_foreign_or_expired_state_makes_no_port_call(
    case: str, validated: list[CompletedSession]
) -> None:
    h = harness()
    token = take_turns(h, started(h), 2)
    owner = OWNER
    if case == "tampered":
        token = token[:-2] + ("AA" if token[-2:] != "AA" else "BA")
    elif case == "foreign":
        owner = OTHER_OWNER
    else:
        h.clock.at(LIMIT_MS + END_GRACE_MS)

    error = refused(h, token, owner)

    expected = {
        "tampered": Rejection.INVALID,
        "foreign": Rejection.FOREIGN,
        "expired": Rejection.EXPIRED,
    }[case]
    assert error.reason is expected
    assert validated == []
    assert h.grader.received == []


def test_t7_the_result_is_never_graded_even_when_the_port_accepts() -> None:
    h = harness()
    h.grader.available = True

    result = end(h, take_turns(h, started(h), 1))

    assert len(h.grader.received) == 1
    assert result.outcome == "unscored"
    assert result.reason == "grading_unavailable"


def test_t7_end_logs_only_content_free_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    h = harness()
    token = take_turns(h, started(h), 2)
    session_id = h.codec.verify(token).session_id
    h.clock.at(12_345)
    capsys.readouterr()

    end(h, token)

    assert events(capsys) == [
        {
            "severity": "INFO",
            "message": "session_ended_student",
            "event": "session_ended_student",
            "session_id": session_id,
            "duration_ms": 12_345,
        },
        {
            "severity": "INFO",
            "message": "handoff_accepted",
            "event": "handoff_accepted",
            "session_id": session_id,
            "duration_ms": 12_345,
        },
        {
            "severity": "WARNING",
            "message": "grading_unavailable",
            "event": "grading_unavailable",
            "session_id": session_id,
        },
    ]


# The time rules at end (T5, SES-5)


def test_t5_end_before_the_limit_is_ended_by_the_student() -> None:
    h = harness()
    token = take_turns(h, started(h), 1)
    h.clock.at(LIMIT_MS - 1)

    result = end(h, token)

    assert result.ended_by == "student"
    assert h.grader.received[0].duration_ms == LIMIT_MS - 1


@pytest.mark.parametrize("elapsed_ms", [LIMIT_MS, LIMIT_MS + END_GRACE_MS - 1])
def test_t5_end_grace_accepts_an_end_after_the_limit(elapsed_ms: int) -> None:
    h = harness()
    token = take_turns(h, started(h), 1)
    h.clock.at(elapsed_ms)

    result = end(h, token)

    assert END_GRACE_MS == 60_000
    assert result.ended_by == "time_limit"
    assert h.grader.received[0].ended_by == "time_limit"
    assert h.grader.received[0].duration_ms == LIMIT_MS


def test_t5_end_grace_refuses_an_end_once_the_grace_is_over(
    capsys: pytest.CaptureFixture[str],
) -> None:
    h = harness()
    token = take_turns(h, started(h), 1)
    h.clock.at(LIMIT_MS + END_GRACE_MS)
    capsys.readouterr()

    error = refused(h, token)

    assert error.code == "session_expired"
    assert h.grader.received == []
    assert [e["event"] for e in events(capsys)] == ["state_rejected_expired"]


def test_t5_duration_never_ends_before_the_last_turn_started() -> None:
    h = harness()
    token = take_turns(h, started(h), 2, step_ms=5_000)
    h.clock.at(7_000)  # another instance, behind the last turn at 10,000 ms

    end(h, token)

    assert h.grader.received[0].duration_ms == 10_000


def test_t5_end_checks_the_owner_before_the_time() -> None:
    h = harness()
    token = take_turns(h, started(h), 1)
    h.clock.at(LIMIT_MS + END_GRACE_MS)

    assert refused(h, token, OTHER_OWNER).reason is Rejection.FOREIGN
