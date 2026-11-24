"""The completed-session handoff contract, version 1.0.0 (#66).

When a session ends, the session service hands the grader this payload
(ARCHITECTURE AD-3, flow 4). The two are separate services (DD-02), and only a
completed session is graded (RC-09, POLICY SCO-1). The committed JSON Schema in
``handoff/`` is generated from these models, so a consumer can build against it
without this package.

The payload holds the whole conversation, so it lives only in memory: it is
never written to storage, a cache or a log (AG-2, ARCHITECTURE section 7).
``owner_uid`` is the UID the session service already verified (owner decision,
2026-11-23). The grader writes the score record under it, and the transcript
only when ``save_transcript`` is true: a session the student marks "don't save"
is never stored (POLICY DAT-1, transcript-storage D4; owner decision,
2026-11-23). The payload carries no credential. Service identity belongs to the
transport, where only the session service's account may invoke the grader
(AG-7, ARCHITECTURE section 9).

Validator messages are fixed strings, ``hide_input_in_errors`` keeps input
values out of validation errors, and turn text and the owner UID are left out
of ``repr``, so no error or debug line can carry session content.
"""

from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT = "cst.completed_session"
CONTRACT_VERSION = "1.0.0"
# A consumer accepts only the exact versions it knows, so every version change,
# minor and patch included, ships grader support first. The owner's deploy order
# enforces that (AG-9).
SUPPORTED_VERSIONS = frozenset({CONTRACT_VERSION})

CRISIS_SCENARIO = "crisis_risk"
MAX_TURNS = 500
MAX_TURN_CHARACTERS = 2000
MAX_DURATION_MS = 3_600_000

# Text may hold any character except the forbidden ones, and needs at least one
# visible character. Forbidden: control characters (tab and newline are
# allowed), the bidi embedding, override and isolate controls that reorder what
# a reader sees, and the byte-order mark, which regex engines disagree is
# whitespace. Allowed but not visible: zero-width spaces and joiners, direction
# marks, word joiners, the blank filler letters, variation selectors, soft
# hyphens, annotation characters and tag characters. Joiners, variation
# selectors and tags stay allowed because Persian, Indic scripts and emoji
# (tags make the England, Scotland and Wales flags) need them. One pattern, so
# JSON Schema consumers enforce the same rule. The astral ranges are literal
# characters, because Python, Rust and ECMA-262 share no escape for them; an
# ECMA-262 consumer compiles the pattern with the ``u`` flag.
_FORBIDDEN = r"\x00-\x08\x0b-\x1f\x7f-\x9f‪-‮⁦-⁩﻿"
_INVISIBLE = (
    r"­͏؜ᅟᅠ᠎​-‏⁠-⁤⠀ㅤ"
    r"︀-️ﾠ￹-￼"
    "\U0001d173-\U0001d17a\U000e0000-\U000e007f\U000e0100-\U000e01ef"
)
_TEXT_PATTERN = rf"^[^{_FORBIDDEN}]*[^\s{_FORBIDDEN}{_INVISIBLE}][^{_FORBIDDEN}]*$"

SessionId = Annotated[
    str,
    Field(
        min_length=36,
        max_length=36,
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        description="A canonical lowercase UUID, the same shape the log helper accepts.",
    ),
]
OwnerUid = Annotated[
    str,
    Field(
        pattern=r"^[A-Za-z0-9]{1,128}$",
        description="The verified Identity Platform UID of the student. Never logged.",
        repr=False,
    ),
]
SemanticVersion = Annotated[str, Field(pattern=r"^[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}$")]
TurnText = Annotated[
    str,
    Field(
        min_length=1,
        max_length=MAX_TURN_CHARACTERS,
        pattern=_TEXT_PATTERN,
        description=(
            "What was said, with at least one visible character. No control "
            "characters except tab and newline, no bidi controls, no byte-order mark."
        ),
        repr=False,
    ),
]
TurnIndex = Annotated[
    int, Field(ge=1, le=MAX_TURNS, description="1-based position in the conversation.")
]
ElapsedMs = Annotated[
    int,
    Field(
        ge=0,
        le=MAX_DURATION_MS,
        description="Milliseconds from the session start to the start of the turn.",
    ),
]


class _Strict(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, hide_input_in_errors=True
    )


class StudentTurn(_Strict):
    """A student turn, with its transcript reliability and conduct flags."""

    index: TurnIndex
    speaker: Literal["student"]
    text: TurnText
    at_ms: ElapsedMs
    input: Literal["text", "speech"] = Field(
        description="How the student gave this turn. A voice session may fall back to text."
    )
    uncertain_recognition: bool = Field(
        description=(
            "Speech recognition marked this turn as uncertain. Such a turn is never the "
            "only evidence for a level 1 behavior, a harm cap or a crisis critical "
            "failure (anchor spec uncertain_recognition_rule)."
        )
    )
    conduct_warning: bool = Field(
        description="This turn drew the session's one conduct warning (POLICY SAF-2)."
    )

    @model_validator(mode="after")
    def _typed_turns_are_certain(self) -> Self:
        if self.input == "text" and self.uncertain_recognition:
            raise ValueError("a typed turn cannot have uncertain recognition")
        return self


class ClientTurn(_Strict):
    """A turn spoken by the simulated client persona."""

    index: TurnIndex
    speaker: Literal["client"]
    text: TurnText
    at_ms: ElapsedMs


Turn = Annotated[StudentTurn | ClientTurn, Field(discriminator="speaker")]


class Scenario(_Strict):
    """The vetted scenario and the configuration version the session ran."""

    id: Literal["routine_intake", "resistant_client", "crisis_risk"]
    version: SemanticVersion


class Conduct(_Strict):
    """Conduct safeguards. A completed session has had at most one warning."""

    warnings: int = Field(ge=0, le=1)


class Crisis(_Strict):
    """Present only in the crisis scenario, which starts only after opt-in (SES-2)."""

    opted_in: Literal[True]


class CompletedSession(_Strict):
    """The payload the grader accepts: one completed session."""

    model_config = ConfigDict(
        title="Completed-session handoff",
        json_schema_extra={"$comment": f"{CONTRACT} {CONTRACT_VERSION} (#66)"},
    )

    contract: Literal["cst.completed_session"]
    contract_version: Literal["1.0.0"]
    session_id: SessionId
    owner_uid: OwnerUid
    scenario: Scenario
    modality: Literal["voice", "text"] = Field(
        description="The mode the session started in."
    )
    status: Literal["completed"] = Field(
        description=(
            "Only completed is accepted. incomplete, content_lost and "
            "ended_for_conduct are rejected with that reason."
        )
    )
    ended_by: Literal["student", "time_limit"]
    duration_ms: Annotated[int, Field(ge=0, le=MAX_DURATION_MS)]
    turns: Annotated[list[Turn], Field(min_length=1, max_length=MAX_TURNS)]
    conduct: Conduct
    crisis: Crisis | None = Field(
        description="Required in the crisis scenario and null in the others."
    )
    save_transcript: bool = Field(
        description=(
            "The student's per-session choice. When false the grader never stores "
            "the transcript (POLICY DAT-1, transcript-storage D4). It has no "
            "default, so a payload without it is rejected."
        )
    )

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        _check_turn_order(self.turns, self.duration_ms)
        students = [turn for turn in self.turns if isinstance(turn, StudentTurn)]
        if self.modality == "text" and any(turn.input == "speech" for turn in students):
            raise ValueError("a text session has no speech turns")
        if sum(turn.conduct_warning for turn in students) != self.conduct.warnings:
            raise ValueError("conduct warnings must match the flagged turns")
        if (self.scenario.id == CRISIS_SCENARIO) != (self.crisis is not None):
            raise ValueError("crisis flags belong to the crisis scenario only")
        return self


def _check_turn_order(turns: list[StudentTurn | ClientTurn], duration_ms: int) -> None:
    if [turn.index for turn in turns] != list(range(1, len(turns) + 1)):
        raise ValueError("turn indexes must run 1 to n in order")
    times = [turn.at_ms for turn in turns]
    if times != sorted(times):
        raise ValueError("turn times must not go backwards")
    if times[-1] > duration_ms:
        raise ValueError("a turn cannot start after the session ended")


def json_schema() -> dict[str, Any]:
    """The JSON Schema consumers build against (committed in ``handoff/``)."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **CompletedSession.model_json_schema(),
    }
