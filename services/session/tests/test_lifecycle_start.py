"""Session start: scenario binding, the crisis opt-in and server fields (T10, T5, FR-2).

The student speaks first (L2-4, owner decided 2026-11-25), so start makes no
model call and returns a signed state with no turns.
"""

import json
import uuid

import pytest

from cst_session.lifecycle import StartRefused
from cst_session.scenarios import SCENARIO_IDS
from tests.lifecycle_fakes import (
    LIMIT_MS,
    OWNER,
    T0,
    Harness,
    harness,
    with_release,
)


def start(scenario_id: str, crisis_opt_in: bool, save_transcript: bool = True) -> str:
    h = harness()
    return h.sessions.start(
        owner_uid=OWNER,
        scenario_id=scenario_id,
        crisis_opt_in=crisis_opt_in,
        save_transcript=save_transcript,
    ).state


def refusal(
    scenario_id: str, crisis_opt_in: object, h: Harness | None = None
) -> StartRefused:
    h = h if h is not None else harness()
    with pytest.raises(StartRefused) as caught:
        h.sessions.start(
            owner_uid=OWNER,
            scenario_id=scenario_id,
            crisis_opt_in=crisis_opt_in,  # type: ignore[arg-type]
            save_transcript=True,
        )
    error = caught.value
    assert error.__cause__ is None
    assert error.__context__ is None or error.__suppress_context__
    return error


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_t10_start_returns_a_signed_state_with_server_fields_and_no_turns(
    scenario_id: str,
) -> None:
    h = harness()

    result = h.sessions.start(
        owner_uid=OWNER,
        scenario_id=scenario_id,
        crisis_opt_in=scenario_id == "crisis_risk",
        save_transcript=False,
    )
    state = h.codec.verify(result.state)

    assert state.session_id == result.session_id
    assert uuid.UUID(state.session_id).version == 4
    assert str(uuid.UUID(state.session_id)) == state.session_id
    assert state.owner_uid == OWNER
    assert state.scenario_id == scenario_id
    assert state.scenario_version == h.catalogue.startable(scenario_id).version
    assert state.started_at_ms == T0
    assert state.modality == "text"
    assert state.save_transcript is False
    assert state.conduct_warnings == 0
    assert state.turns == []
    assert result.time_limit_ms == result.remaining_ms == LIMIT_MS


def test_t10_start_makes_no_persona_call() -> None:
    h = harness()

    h.sessions.start(
        owner_uid=OWNER,
        scenario_id="routine_intake",
        crisis_opt_in=False,
        save_transcript=True,
    )

    assert h.persona.calls == []


def test_t10_each_start_gets_a_new_session_id() -> None:
    h = harness()
    ids = {
        h.sessions.start(
            owner_uid=OWNER,
            scenario_id="routine_intake",
            crisis_opt_in=False,
            save_transcript=True,
        ).session_id
        for _ in range(20)
    }

    assert len(ids) == 20


def test_t10_unknown_and_unreleased_scenarios_raise_the_same_error() -> None:
    held_back = harness(
        catalogue=with_release(harness().catalogue, "resistant_client", False)
    )

    unknown = refusal(scenario_id="free_chat", crisis_opt_in=False)
    unreleased = refusal(
        h=held_back, scenario_id="resistant_client", crisis_opt_in=False
    )

    assert unknown.code == unreleased.code == "scenario_unavailable"
    assert str(unknown) == str(unreleased) == "scenario_unavailable"


def test_t10_the_crisis_scenario_requires_the_opt_in() -> None:
    error = refusal(scenario_id="crisis_risk", crisis_opt_in=False)

    assert error.code == "opt_in_required" == str(error)


@pytest.mark.parametrize("value", ["true", 1, None])
def test_t10_only_a_real_true_counts_as_the_opt_in(value: object) -> None:
    assert (
        refusal(scenario_id="crisis_risk", crisis_opt_in=value).code
        == "opt_in_required"
    )


def test_t10_the_crisis_scenario_starts_with_the_opt_in() -> None:
    h = harness()

    state = h.codec.verify(start("crisis_risk", crisis_opt_in=True))

    assert state.crisis_opt_in is True


@pytest.mark.parametrize("scenario_id", ["routine_intake", "resistant_client"])
def test_t10_crisis_opt_in_is_false_outside_the_crisis_scenario(
    scenario_id: str,
) -> None:
    h = harness()

    state = h.codec.verify(start(scenario_id, crisis_opt_in=True))

    assert state.crisis_opt_in is False


def test_t10_a_refused_start_signs_nothing_and_logs_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    refusal(scenario_id="crisis_risk", crisis_opt_in=False)
    refusal(scenario_id="free_chat", crisis_opt_in=False)

    assert capsys.readouterr().out == ""


def test_t10_start_logs_only_the_session_and_scenario(
    capsys: pytest.CaptureFixture[str],
) -> None:
    h = harness()
    result = h.sessions.start(
        owner_uid=OWNER,
        scenario_id="resistant_client",
        crisis_opt_in=False,
        save_transcript=True,
    )

    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines == [
        {
            "severity": "INFO",
            "message": "session_started",
            "event": "session_started",
            "session_id": result.session_id,
            "scenario_id": "resistant_client",
            "scenario_version": "1.0.0",
        }
    ]
    assert OWNER not in str(lines)
