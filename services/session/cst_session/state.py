"""The signed session state the app holds between requests, contract v1 (AD-1).

The service stores nothing, so every turn and end carries the whole session
back as a token the server signed (T1)::

    v1.<payload_b64>.<tag_b64>
    tag = HMAC-SHA256(key, b"cst.session_state.v1." + payload_b64_ascii)

Both parts are unpadded base64url. The MAC covers the exact bytes sent, so the
canonical JSON encoding below exists only to make tests deterministic. There is
no algorithm or key field and no compression, and only the standard library's
``hmac`` and ``hashlib`` touch the key.

``StateCodec.verify`` runs verification steps 1 to 3 in order, each only if the
one before passed: the length cap and a full match on the token shape, with
nothing decoded; the MAC, compared with ``hmac.compare_digest``; then a strict
decode, ``json.loads`` with unique keys and no NaN or infinity, and the strict
model. Every failure is the same ``StateRejected``, raised outside any
``except`` block so it chains nothing that could hold input. The owner, scenario
and time steps (4 to 6) belong to ``lifecycle``.

The state is signed, not encrypted: the student can read their own transcript,
which the app already holds. It never carries a prompt or server-only data.

Size caps (T9): at most ``MAX_STATE_TURNS`` turns and ``MAX_STATE_CHARS``
characters per token. ``sign`` refuses a state whose token would be over the
cap, so the server never signs a state it could not accept back.

The key (T8, L2-2, owner decided 2026-11-25): ``CST_STATE_SIGNING_KEY`` is 43
characters of unpadded base64url that decode to exactly 32 bytes and encode back
to the same text. ``decode_signing_key`` refuses anything else with one fixed
message that names neither the value nor its length.
"""

import base64
import binascii
import hashlib
import hmac
import json
import re
from enum import StrEnum
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cst_session.handoff.contract import (
    MAX_DURATION_MS,
    SemanticVersion,
    SessionId,
    TurnText,
)
from cst_session.handoff.validation import _no_constants, _unique_keys

KEY_BYTES: Final = 32
MAX_STATE_TURNS: Final = 200
MAX_STATE_CHARS: Final = 1_000_000

_VERSION_PREFIX: Final = "v1"
_DOMAIN: Final = b"cst.session_state.v1."
_KEY_TEXT = re.compile(r"[A-Za-z0-9_-]{43}", re.ASCII)
_TOKEN = re.compile(r"v1\.([A-Za-z0-9_-]+)\.([A-Za-z0-9_-]{43})", re.ASCII)
_KEY_ERROR: Final = "CST_STATE_SIGNING_KEY is not a valid state-signing key."
_EPOCH_MS_LIMIT: Final = 2**53


class SigningKeyError(ValueError):
    """The signing key is missing or malformed. The message never shows it."""

    def __init__(self) -> None:
        super().__init__(_KEY_ERROR)


class Rejection(StrEnum):
    """Why a state was refused. The value names the ``state_rejected_*`` log event."""

    INVALID = "invalid"
    FOREIGN = "foreign"
    SCENARIO = "scenario"
    TIME_LIMIT = "time_limit"
    EXPIRED = "expired"
    TURN_LIMIT = "turn_limit"


# The stable code the app sees. A foreign or rebound state looks like a forged
# one, so a caller learns nothing about another student's session.
_CLIENT_CODES: Final = {
    Rejection.INVALID: "state_invalid",
    Rejection.FOREIGN: "state_invalid",
    Rejection.SCENARIO: "state_invalid",
    Rejection.TIME_LIMIT: "session_time_limit",
    Rejection.EXPIRED: "session_expired",
    Rejection.TURN_LIMIT: "turn_limit_reached",
}


class StateRejected(Exception):
    """A state failed verification. The message is the stable client ``code``."""

    def __init__(self, reason: Rejection) -> None:
        self.reason = reason
        self.code = _CLIENT_CODES[reason]
        super().__init__(self.code)


class StateTooLarge(Exception):
    """The state would exceed a size cap, so it is never signed (T9)."""

    def __init__(self) -> None:
        super().__init__("state_too_large")


class _Strict(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, hide_input_in_errors=True
    )


class StateTurn(_Strict):
    """One turn as the state carries it. The server computes ``at_ms``."""

    speaker: Literal["student", "client"]
    text: TurnText
    at_ms: Annotated[int, Field(ge=0, le=MAX_DURATION_MS)]


class SessionState(_Strict):
    """Everything the session needs between requests (FR-3)."""

    session_id: SessionId
    owner_uid: Annotated[str, Field(min_length=1, max_length=128, repr=False)]
    scenario_id: Literal["routine_intake", "resistant_client", "crisis_risk"]
    scenario_version: SemanticVersion
    started_at_ms: Annotated[int, Field(ge=0, lt=_EPOCH_MS_LIMIT)]
    modality: Literal["text"]
    crisis_opt_in: bool
    save_transcript: bool
    conduct_warnings: Annotated[int, Field(ge=0, le=1)]
    turns: Annotated[list[StateTurn], Field(max_length=MAX_STATE_TURNS)]


def decode_signing_key(text: str) -> bytes:
    """Decode ``CST_STATE_SIGNING_KEY``, or raise ``SigningKeyError``."""
    if not isinstance(text, str) or _KEY_TEXT.fullmatch(text) is None:
        raise SigningKeyError()
    raw = _strict_b64decode(text)
    if raw is None or len(raw) != KEY_BYTES:
        raise SigningKeyError()
    return raw


class StateCodec:
    """Signs and verifies session states with one 32-byte key."""

    __slots__ = ("_key",)

    def __init__(self, key: bytes) -> None:
        if not isinstance(key, bytes) or len(key) != KEY_BYTES:
            raise SigningKeyError()
        self._key = key

    def __repr__(self) -> str:
        return "StateCodec(key=<hidden>)"

    def sign(self, state: SessionState) -> str:
        """The token for ``state``. Raises ``StateTooLarge`` over a cap."""
        if len(state.turns) > MAX_STATE_TURNS:
            raise StateTooLarge()
        payload_b64 = _b64encode(_canonical(state))
        token = f"{_VERSION_PREFIX}.{payload_b64}.{_b64encode(self._tag(payload_b64))}"
        if len(token) > MAX_STATE_CHARS:
            raise StateTooLarge()
        return token

    def verify(self, token: object) -> SessionState:
        """The state ``token`` carries, or raise ``StateRejected`` (steps 1 to 3)."""
        if not isinstance(token, str) or len(token) > MAX_STATE_CHARS:
            raise StateRejected(Rejection.INVALID)
        match = _TOKEN.fullmatch(token)
        if match is None:
            raise StateRejected(Rejection.INVALID)
        payload_b64, tag_b64 = match.groups()
        tag = _strict_b64decode(tag_b64)
        if tag is None or not hmac.compare_digest(self._tag(payload_b64), tag):
            raise StateRejected(Rejection.INVALID)
        payload = _strict_b64decode(payload_b64)
        state = _parse(payload) if payload is not None else None
        if state is None:
            raise StateRejected(Rejection.INVALID)
        return state

    def _tag(self, payload_b64: str) -> bytes:
        message = _DOMAIN + payload_b64.encode("ascii")
        return hmac.new(self._key, message, hashlib.sha256).digest()


def _canonical(state: SessionState) -> bytes:
    return json.dumps(
        state.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


def _parse(payload: bytes) -> SessionState | None:
    try:
        data = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_keys,
            parse_constant=_no_constants,
        )
    except (ValueError, RecursionError):
        return None
    try:
        return SessionState.model_validate(data)
    except ValidationError:
        # Discarded: errors() still returns the raw input.
        return None


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _strict_b64decode(text: str) -> bytes | None:
    """Decode unpadded base64url that re-encodes to exactly ``text``, else ``None``.

    The caller has already matched ``text`` against the base64url alphabet.
    """
    if len(text) % 4 == 1:
        return None
    try:
        raw = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except binascii.Error:
        return None
    return raw if _b64encode(raw) == text else None
