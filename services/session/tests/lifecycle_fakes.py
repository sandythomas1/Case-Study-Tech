"""Fakes for lifecycle tests: a settable clock, a scripted persona and a spy grader.

Everything is synthetic, and nothing touches the network or a store.
"""

import asyncio
from collections.abc import Coroutine, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from cst_session.grading import GradingUnavailable
from cst_session.handoff import CompletedSession
from cst_session.lifecycle import Sessions
from cst_session.persona import (
    PersonaFailure,
    PersonaMessage,
    PersonaReply,
    PersonaUnavailable,
)
from cst_session.scenarios import Catalogue, load_catalogue
from cst_session.scenarios.prompts import Prompts, load_prompts
from cst_session.state import StateCodec
from tests.state_fixtures import KEY

OWNER = "synthUid001"
OTHER_OWNER = "synthUid002"
T0 = 1_790_000_000_000
LIMIT_MS = 10 * 60_000
GRACE_MS = 60_000


def run[T](coroutine: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coroutine)


class FakeClock:
    def __init__(self, now_ms: int = T0) -> None:
        self.now = now_ms

    def now_ms(self) -> int:
        return self.now

    def at(self, elapsed_ms: int) -> None:
        self.now = T0 + elapsed_ms


@dataclass
class PersonaCall:
    system_prompt: str
    history: list[PersonaMessage]


@dataclass
class FakePersona:
    """Replies from a script, records each call, and can move the clock or fail."""

    reply_text: str = "I guess it has been a stressful term."
    failure: PersonaFailure | None = None
    clock: FakeClock | None = None
    advance_ms: int = 0
    calls: list[PersonaCall] = field(default_factory=list)

    async def reply(
        self, *, system_prompt: str, history: Sequence[PersonaMessage]
    ) -> PersonaReply:
        self.calls.append(PersonaCall(system_prompt, list(history)))
        if self.clock is not None:
            self.clock.now += self.advance_ms
        if self.failure is not None:
            raise PersonaUnavailable(self.failure, status_code=503)
        return PersonaReply(text=self.reply_text)


@dataclass
class SpyGrader:
    received: list[CompletedSession] = field(default_factory=list)
    available: bool = False

    async def submit(self, session: CompletedSession) -> None:
        self.received.append(session)
        if not self.available:
            raise GradingUnavailable()


@dataclass
class Harness:
    sessions: Sessions
    clock: FakeClock
    persona: FakePersona
    grader: SpyGrader
    catalogue: Catalogue
    prompts: Prompts
    codec: StateCodec


def harness(
    *,
    catalogue: Catalogue | None = None,
    persona: FakePersona | None = None,
    key: bytes = KEY,
) -> Harness:
    clock = FakeClock()
    persona = persona if persona is not None else FakePersona()
    persona.clock = clock
    grader = SpyGrader()
    catalogue = catalogue if catalogue is not None else load_catalogue()
    prompts = load_prompts()
    codec = StateCodec(key)
    sessions = Sessions(
        catalogue=catalogue,
        prompts=prompts,
        codec=codec,
        persona=persona,
        grader=grader,
        clock=clock,
    )
    return Harness(sessions, clock, persona, grader, catalogue, prompts, codec)


def with_release(catalogue: Catalogue, scenario_id: str, released: bool) -> Catalogue:
    return Catalogue(
        tuple(
            replace(scenario, released=released)
            if scenario.id == scenario_id
            else scenario
            for scenario in catalogue.scenarios
        )
    )


def with_version(catalogue: Catalogue, scenario_id: str, version: str) -> Catalogue:
    return Catalogue(
        tuple(
            replace(scenario, version=version)
            if scenario.id == scenario_id
            else scenario
            for scenario in catalogue.scenarios
        )
    )


def started(h: Harness, scenario_id: str = "routine_intake", **kwargs: Any) -> str:
    options: dict[str, Any] = {
        "crisis_opt_in": scenario_id == "crisis_risk",
        "save_transcript": True,
    }
    options.update(kwargs)
    return h.sessions.start(owner_uid=OWNER, scenario_id=scenario_id, **options).state


def take_turns(h: Harness, token: str, count: int, step_ms: int = 1_000) -> str:
    for number in range(count):
        h.clock.now += step_ms
        token = run(
            h.sessions.turn(
                owner_uid=OWNER, state=token, text=f"Student turn {number}."
            )
        ).state
    return token
