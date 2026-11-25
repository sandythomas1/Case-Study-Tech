"""The persona and grader ports carry fixed messages only (FR-5, FR-6, FR-7)."""

import asyncio

import pytest

from cst_session.grading import GradingUnavailable, UnavailableGrader
from cst_session.handoff import CompletedSession
from cst_session.persona import (
    PersonaFailure,
    PersonaMessage,
    PersonaReply,
    PersonaUnavailable,
)
from tests.handoff_fixtures import routine


@pytest.mark.parametrize("code", list(PersonaFailure))
def test_a_persona_failure_message_is_its_fixed_code(code: PersonaFailure) -> None:
    error = PersonaUnavailable(code)

    assert error.code is code
    assert str(error) == code.value
    assert error.args == (code.value,)


def test_the_persona_failure_codes_are_the_planned_set() -> None:
    assert {code.value for code in PersonaFailure} == {
        "persona_timeout",
        "persona_unreachable",
        "persona_http_error",
        "persona_auth",
        "persona_bad_response",
        "persona_blocked",
        "persona_bad_reply",
    }


def test_persona_text_is_left_out_of_repr() -> None:
    message = PersonaMessage(speaker="student", text="Synthetic canary 7Q")
    reply = PersonaReply(text="Synthetic canary 8R")

    assert "canary" not in repr(message) and "canary" not in repr(reply)


def test_the_interim_grader_always_reports_grading_unavailable() -> None:
    session = CompletedSession.model_validate(routine())

    with pytest.raises(GradingUnavailable) as caught:
        asyncio.run(UnavailableGrader().submit(session))
    assert str(caught.value) == "grading_unavailable"
