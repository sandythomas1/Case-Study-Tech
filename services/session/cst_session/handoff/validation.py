"""Accept a completed session, or reject it with one fixed reason (#66).

Both sides call this: the session service before it hands a session over, and
the grader when it receives one. The checks run in this order, so the most
specific reason wins:

1. The input is a JSON object naming this contract, or it is ``malformed``.
2. Its ``contract_version`` is one this code knows, or ``version_mismatch``.
3. Its ``status`` is ``completed``. ``incomplete``, ``content_lost`` and
   ``ended_for_conduct`` are rejected with that reason before the rest is read,
   so a session that lost content is never reported as malformed.
4. The whole payload matches the schema, or it is ``malformed``.

Nothing here stores the payload. Logging goes only through the content-free
helper and carries the session ID and duration: never turn text or the owner
UID (POLICY DAT-1, DAT-7). A pydantic ``ValidationError`` is discarded, because
its ``errors()`` still returns the raw input even with ``hide_input_in_errors``.
A rejection is raised outside any ``except`` block, so it carries no chained
error that could hold input values. Its traceback still references frames whose
locals hold the payload, so a caller turns ``HandoffRejected`` into a fixed
response at once and never hands it to an error reporter that captures locals.
"""

import json
from enum import StrEnum
from typing import NoReturn

from pydantic import ValidationError

from cst_session.content_free_log import log_event
from cst_session.handoff.contract import CONTRACT, SUPPORTED_VERSIONS, CompletedSession

# The largest valid session is 500 turns of 2,000 four-byte characters: 4,000,000
# bytes of text as ``encode_handoff`` writes it (raw UTF-8), plus the field
# names. A body that escapes non-ASCII text as ``\uXXXX`` can be up to three
# times larger, so a producer sends only what ``encode_handoff`` returns.
MAX_BODY_BYTES = 5 * 1024 * 1024


class RejectionReason(StrEnum):
    INCOMPLETE = "incomplete"
    CONTENT_LOST = "content_lost"
    ENDED_FOR_CONDUCT = "ended_for_conduct"
    VERSION_MISMATCH = "version_mismatch"
    MALFORMED = "malformed"


_STATUS_REASONS = {
    "incomplete": RejectionReason.INCOMPLETE,
    "content_lost": RejectionReason.CONTENT_LOST,
    "ended_for_conduct": RejectionReason.ENDED_FOR_CONDUCT,
}


class HandoffRejected(Exception):
    """The payload is not a gradable completed session. The message is the reason."""

    def __init__(self, reason: RejectionReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


def encode_handoff(session: CompletedSession) -> bytes:
    """The request body for a session that ``validate_handoff`` accepted.

    The producer sends exactly these bytes: UTF-8 JSON with no ``\\u`` escapes,
    so every valid session fits under ``MAX_BODY_BYTES``.
    """
    return session.model_dump_json().encode("utf-8")


def parse_handoff(body: bytes) -> CompletedSession:
    """Decode a request body and validate it. Raises ``HandoffRejected``.

    The body must be UTF-8 with no byte-order mark (RFC 8259 section 8.1).
    """
    payload: object = None
    decoded = len(body) <= MAX_BODY_BYTES
    if decoded:
        try:
            payload = json.loads(
                body.decode("utf-8"),
                object_pairs_hook=_unique_keys,
                parse_constant=_no_constants,
            )
        except (ValueError, RecursionError):
            decoded = False
    if not decoded:
        _reject(RejectionReason.MALFORMED, None)
    return validate_handoff(payload)


def validate_handoff(payload: object) -> CompletedSession:
    """Validate decoded JSON. Raises ``HandoffRejected``."""
    reason = _envelope_reason(payload)
    if reason is None:
        session = _completed_session(payload)
        if session is not None:
            log_event(
                "handoff_accepted",
                session_id=session.session_id,
                duration_ms=session.duration_ms,
            )
            return session
        reason = RejectionReason.MALFORMED
    _reject(reason, payload)


def _envelope_reason(payload: object) -> RejectionReason | None:
    if not isinstance(payload, dict) or payload.get("contract") != CONTRACT:
        return RejectionReason.MALFORMED
    version = payload.get("contract_version")
    if not isinstance(version, str) or version not in SUPPORTED_VERSIONS:
        return RejectionReason.VERSION_MISMATCH
    status = payload.get("status")
    if not isinstance(status, str):
        return RejectionReason.MALFORMED
    if status in _STATUS_REASONS:
        return _STATUS_REASONS[status]
    return None if status == "completed" else RejectionReason.MALFORMED


def _completed_session(payload: object) -> CompletedSession | None:
    try:
        return CompletedSession.model_validate(payload)
    except ValidationError:
        return None


def _reject(reason: RejectionReason, payload: object) -> NoReturn:
    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    log_event(
        f"handoff_rejected_{reason.value}", severity="WARNING", session_id=session_id
    )
    raise HandoffRejected(reason)


def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate key")
    return result


def _no_constants(name: str) -> object:
    raise ValueError("non-finite number")
