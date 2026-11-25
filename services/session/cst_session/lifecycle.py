"""Start, turn and end for a stateless practice session (FR-2, FR-4 to FR-7, AD-1).

The conversation lives only in the signed state the app holds between calls
(``state.py``). Each call verifies it in a fixed order: the MAC and strict
parse, then the owner, then the scenario and its version, then the time on the
server clock. New states are built only from a verified state plus fields the
server computes, so client data never skips validation.

Time rules (SES-5): with ``L`` the scenario's limit, a turn is refused once
``elapsed >= L``, checked before the persona call and again when the reply
arrives, so every signed turn starts before the limit. End is accepted until
``L + END_GRACE_MS``. Turn times never decrease, so clock skew between
instances cannot produce a state the handoff would refuse.

Errors carry fixed codes only. Logs go through ``content_free_log`` and never
carry a UID, turn text, prompt or token. ``session_id`` is logged only once
the MAC has passed.
"""

import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, NoReturn, Protocol

from cst_session.content_free_log import log_error, log_event
from cst_session.grading import GraderPort, GradingUnavailable
from cst_session.handoff import HandoffRejected, validate_handoff
from cst_session.handoff.contract import CRISIS_SCENARIO
from cst_session.persona import (
    PersonaFailure,
    PersonaMessage,
    PersonaPort,
    PersonaUnavailable,
    valid_turn_text,
)
from cst_session.scenarios import Catalogue, Scenario, ScenarioUnavailable
from cst_session.scenarios.prompts import Prompts
from cst_session.state import (
    MAX_STATE_TURNS,
    Rejection,
    SessionState,
    StateCodec,
    StateRejected,
    StateTooLarge,
    StateTurn,
)

END_GRACE_MS = 60_000
FUTURE_START_TOLERANCE_MS = 5_000

EndReason = Literal["grading_unavailable", "empty_session", "not_gradable"]
EndedBy = Literal["student", "time_limit"]


class Clock(Protocol):
    def now_ms(self) -> int:
        """Milliseconds since the Unix epoch on the server."""
        ...


class SystemClock:
    def now_ms(self) -> int:
        return time.time_ns() // 1_000_000


class StartRefused(Exception):
    """A session cannot start. The message is the fixed client ``code``."""

    def __init__(
        self, code: Literal["scenario_unavailable", "opt_in_required"]
    ) -> None:
        self.code = code
        super().__init__(code)


class InvalidTurn(Exception):
    """The student's text is not a valid turn. The message is a fixed code."""

    def __init__(self) -> None:
        self.code = "invalid_turn"
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class Started:
    session_id: str
    state: str
    time_limit_ms: int
    remaining_ms: int


@dataclass(frozen=True, slots=True)
class Turned:
    reply: str
    state: str
    remaining_ms: int


@dataclass(frozen=True, slots=True)
class Ended:
    reason: EndReason
    ended_by: EndedBy
    outcome: Literal["unscored"] = "unscored"


@dataclass(frozen=True, slots=True)
class _Verified:
    state: SessionState
    scenario: Scenario
    limit_ms: int
    elapsed_ms: int


class Sessions:
    """The session use cases. Every collaborator is injected."""

    __slots__ = ("_catalogue", "_clock", "_codec", "_grader", "_persona", "_prompts")

    def __init__(
        self,
        *,
        catalogue: Catalogue,
        prompts: Prompts,
        codec: StateCodec,
        persona: PersonaPort,
        grader: GraderPort,
        clock: Clock,
    ) -> None:
        self._catalogue = catalogue
        self._prompts = prompts
        self._codec = codec
        self._persona = persona
        self._grader = grader
        self._clock = clock

    def start(
        self,
        *,
        owner_uid: str,
        scenario_id: str,
        crisis_opt_in: bool,
        save_transcript: bool,
    ) -> Started:
        """Start a session. The student speaks first, so no model is called (L2-4)."""
        try:
            scenario = self._catalogue.startable(scenario_id)
        except ScenarioUnavailable:
            raise StartRefused("scenario_unavailable") from None
        opted_in = crisis_opt_in is True
        if scenario.requires_opt_in and not opted_in:
            raise StartRefused("opt_in_required")
        state = SessionState(
            session_id=str(uuid.uuid4()),
            owner_uid=owner_uid,
            scenario_id=scenario.id,  # type: ignore[arg-type]
            scenario_version=scenario.version,
            started_at_ms=self._clock.now_ms(),
            modality="text",
            crisis_opt_in=scenario.requires_opt_in and opted_in,
            save_transcript=save_transcript,
            conduct_warnings=0,
            turns=[],
        )
        token = self._codec.sign(state)
        log_event(
            "session_started",
            session_id=state.session_id,
            scenario_id=state.scenario_id,
            scenario_version=state.scenario_version,
        )
        limit_ms = _limit_ms(scenario)
        return Started(state.session_id, token, limit_ms, limit_ms)

    async def turn(self, *, owner_uid: str, state: object, text: object) -> Turned:
        """Add the student's turn and the client's reply, and re-sign the state.

        Raises ``StateRejected``, ``InvalidTurn`` or ``PersonaUnavailable``. A
        failure returns no state, so the attempt that failed is never signed.
        """
        verified = self._verify(owner_uid, state)
        current = verified.state
        if verified.elapsed_ms >= verified.limit_ms:
            _reject(Rejection.TIME_LIMIT, current)
        if len(current.turns) + 2 > MAX_STATE_TURNS:
            _reject(Rejection.TURN_LIMIT, current)
        student = StateTurn(
            speaker="student",
            text=_turn_text(text),
            at_ms=_not_before(verified.elapsed_ms, current.turns),
        )
        history = [
            PersonaMessage(turn.speaker, turn.text)
            for turn in [*current.turns, student]
        ]
        reply, latency_ms = await self._reply(current, history)
        elapsed_ms = self._elapsed_ms(current)
        if elapsed_ms >= verified.limit_ms:
            _reject(Rejection.TIME_LIMIT, current)
        client = StateTurn(
            speaker="client", text=reply, at_ms=max(elapsed_ms, student.at_ms)
        )
        try:
            token = self._codec.sign(
                _with_turns(current, [*current.turns, student, client])
            )
        except StateTooLarge:
            token = None
        if token is None:
            _reject(Rejection.TURN_LIMIT, current)
        log_event("session_turn", session_id=current.session_id, duration_ms=latency_ms)
        return Turned(reply, token, max(0, verified.limit_ms - elapsed_ms))

    async def end(self, *, owner_uid: str, state: object) -> Ended:
        """End the session and hand a gradable one to the grader port.

        Raises ``StateRejected``. The outcome is always unscored until #68.
        """
        verified = self._verify(owner_uid, state)
        current = verified.state
        if verified.elapsed_ms >= verified.limit_ms + END_GRACE_MS:
            _reject(Rejection.EXPIRED, current)
        ended_by: EndedBy = (
            "time_limit" if verified.elapsed_ms >= verified.limit_ms else "student"
        )
        duration_ms = _duration_ms(verified)
        log_event(
            f"session_ended_{ended_by}",
            session_id=current.session_id,
            duration_ms=duration_ms,
        )
        if not current.turns:
            return Ended("empty_session", ended_by)
        try:
            session = validate_handoff(_handoff(current, ended_by, duration_ms))
        except HandoffRejected:
            return Ended("not_gradable", ended_by)
        try:
            await self._grader.submit(session)
        except GradingUnavailable:
            log_event(
                "grading_unavailable", severity="WARNING", session_id=current.session_id
            )
        return Ended("grading_unavailable", ended_by)

    def _verify(self, owner_uid: str, token: object) -> _Verified:
        try:
            state = self._codec.verify(token)
        except StateRejected as error:
            reason = error.reason
        else:
            return self._check(owner_uid, state)
        _reject(reason, None)

    def _check(self, owner_uid: str, state: SessionState) -> _Verified:
        if state.owner_uid != owner_uid:
            _reject(Rejection.FOREIGN, state)
        scenario = self._scenario_for(state)
        if scenario is None:
            _reject(Rejection.SCENARIO, state)
        if state.started_at_ms > self._clock.now_ms() + FUTURE_START_TOLERANCE_MS:
            _reject(Rejection.INVALID, state)
        return _Verified(state, scenario, _limit_ms(scenario), self._elapsed_ms(state))

    def _scenario_for(self, state: SessionState) -> Scenario | None:
        try:
            scenario = self._catalogue.startable(state.scenario_id)
        except ScenarioUnavailable:
            return None
        if scenario.version != state.scenario_version:
            return None
        if scenario.requires_opt_in != state.crisis_opt_in:
            return None
        return scenario

    def _elapsed_ms(self, state: SessionState) -> int:
        return max(0, self._clock.now_ms() - state.started_at_ms)

    async def _reply(
        self, state: SessionState, history: Sequence[PersonaMessage]
    ) -> tuple[str, int]:
        """The persona's reply as valid turn text and the call's latency."""
        started_ms = self._clock.now_ms()
        failure: PersonaUnavailable | None = None
        text: str | None = None
        try:
            reply = await self._persona.reply(
                system_prompt=self._prompts.for_scenario(state.scenario_id),
                history=history,
            )
        except PersonaUnavailable as error:
            failure = error
        else:
            text = valid_turn_text(reply.text)
        latency_ms = max(0, self._clock.now_ms() - started_ms)
        if text is None:
            failure = failure or PersonaUnavailable(PersonaFailure.BAD_REPLY)
            _persona_failed(failure, state, latency_ms)
        return text, latency_ms


def _persona_failed(
    failure: PersonaUnavailable, state: SessionState, latency_ms: int
) -> NoReturn:
    log_error(
        "persona_failed",
        failure,
        code=failure.code.value,
        status_code=failure.status_code,
        duration_ms=latency_ms,
        session_id=state.session_id,
    )
    failure.__cause__ = None
    failure.__suppress_context__ = True
    raise failure


def _reject(reason: Rejection, state: SessionState | None) -> NoReturn:
    session_id = state.session_id if state is not None else None
    log_event(
        f"state_rejected_{reason.value}", severity="WARNING", session_id=session_id
    )
    raise StateRejected(reason)


def _turn_text(text: object) -> str:
    valid = valid_turn_text(text)
    if valid is None:
        raise InvalidTurn()
    return valid


def _not_before(elapsed_ms: int, turns: Sequence[StateTurn]) -> int:
    return max(elapsed_ms, turns[-1].at_ms) if turns else elapsed_ms


def _limit_ms(scenario: Scenario) -> int:
    return scenario.time_limit_minutes * 60_000


def _duration_ms(verified: _Verified) -> int:
    """Elapsed time capped at the limit, and never before the last turn started."""
    elapsed_ms = _not_before(verified.elapsed_ms, verified.state.turns)
    return min(elapsed_ms, verified.limit_ms)


def _with_turns(state: SessionState, turns: list[StateTurn]) -> SessionState:
    return SessionState(
        session_id=state.session_id,
        owner_uid=state.owner_uid,
        scenario_id=state.scenario_id,
        scenario_version=state.scenario_version,
        started_at_ms=state.started_at_ms,
        modality=state.modality,
        crisis_opt_in=state.crisis_opt_in,
        save_transcript=state.save_transcript,
        conduct_warnings=state.conduct_warnings,
        turns=turns,
    )


def _handoff(
    state: SessionState, ended_by: EndedBy, duration_ms: int
) -> dict[str, object]:
    """The completed-session payload, in the shape ``validate_handoff`` checks."""
    turns: list[dict[str, object]] = []
    for index, turn in enumerate(state.turns, start=1):
        entry: dict[str, object] = {
            "index": index,
            "speaker": turn.speaker,
            "text": turn.text,
            "at_ms": turn.at_ms,
        }
        if turn.speaker == "student":
            entry.update(
                input="text", uncertain_recognition=False, conduct_warning=False
            )
        turns.append(entry)
    crisis = {"opted_in": True} if state.scenario_id == CRISIS_SCENARIO else None
    return {
        "contract": "cst.completed_session",
        "contract_version": "1.0.0",
        "session_id": state.session_id,
        "owner_uid": state.owner_uid,
        "scenario": {"id": state.scenario_id, "version": state.scenario_version},
        "modality": state.modality,
        "status": "completed",
        "ended_by": ended_by,
        "duration_ms": duration_ms,
        "turns": turns,
        "conduct": {"warnings": 0},
        "crisis": crisis,
        "save_transcript": state.save_transcript,
    }
