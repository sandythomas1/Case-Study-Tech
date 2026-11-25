"""The port a turn calls to get the simulated client's reply (FR-5, FR-7).

The domain sees only this protocol. The production adapter calls Gemini
Enterprise Agent Platform; tests use a fake. An adapter raises
``PersonaUnavailable`` with one ``PersonaFailure`` code for every way the call
can fail. The message is that fixed code, so nothing from the upstream reply,
the request or the conversation reaches an error or a log. The API answers every
code with the one client code ``persona_unavailable``, and the cause appears
only in logs.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError

from cst_session.handoff.contract import TurnText

Speaker = Literal["student", "client"]


class PersonaFailure(StrEnum):
    TIMEOUT = "persona_timeout"
    UNREACHABLE = "persona_unreachable"
    HTTP_ERROR = "persona_http_error"
    AUTH = "persona_auth"
    BAD_RESPONSE = "persona_bad_response"
    BLOCKED = "persona_blocked"
    BAD_REPLY = "persona_bad_reply"


class PersonaUnavailable(Exception):
    """The persona could not reply. The message is the fixed ``code``.

    ``status_code`` is the upstream HTTP status when there was one, for logs.
    """

    def __init__(self, code: PersonaFailure, *, status_code: int | None = None) -> None:
        self.code = PersonaFailure(code)
        self.status_code = status_code
        super().__init__(self.code.value)


@dataclass(frozen=True, slots=True)
class PersonaMessage:
    """One turn of the history the persona sees, oldest first."""

    speaker: Speaker
    text: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class PersonaReply:
    """What the simulated client said. Untrusted until it passes ``TurnText``."""

    text: str = field(repr=False)


class PersonaPort(Protocol):
    async def reply(
        self, *, system_prompt: str, history: Sequence[PersonaMessage]
    ) -> PersonaReply:
        """The client's next turn, or raise ``PersonaUnavailable``.

        ``system_prompt`` is the verified scenario's prompt, the same on every
        turn. ``history`` ends with the student's new turn.
        """
        ...


class _TurnText(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, hide_input_in_errors=True)

    text: TurnText


def valid_turn_text(text: object) -> str | None:
    """``text`` if it is valid turn text (the handoff's ``TurnText``), else ``None``.

    The validation error is discarded, so nothing is echoed.
    """
    try:
        return _TurnText(text=text).text  # type: ignore[arg-type]
    except ValidationError:
        return None
