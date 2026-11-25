"""The port end hands a validated completed session to (FR-6, T7).

The session service never grades. End gives the port exactly the
``CompletedSession`` that ``validate_handoff`` returned, and only that. Until
the grader client lands in #68, the only adapter is ``UnavailableGrader``, so
every ending is unscored with the reason ``grading_unavailable``. #68 adds a
graded outcome without changing this port's input.
"""

from typing import Protocol

from cst_session.handoff.contract import CompletedSession


class GradingUnavailable(Exception):
    """The grader cannot take the session now. The message is a fixed code."""

    def __init__(self) -> None:
        super().__init__("grading_unavailable")


class GraderPort(Protocol):
    async def submit(self, session: CompletedSession) -> None:
        """Hand ``session`` to the grader, or raise ``GradingUnavailable``."""
        ...


class UnavailableGrader:
    """The grader port until #68: it always reports grading unavailable."""

    async def submit(self, session: CompletedSession) -> None:
        raise GradingUnavailable()
