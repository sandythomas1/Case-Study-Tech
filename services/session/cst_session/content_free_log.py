"""Content-free structured logging for Cloud Logging (POLICY DAT-1, DAT-7).

The only sanctioned way for a service to log. Each call writes one JSON object
per line to stdout, which Cloud Run forwards to Cloud Logging as ``jsonPayload``
with ``severity`` and ``message`` lifted into the log entry.

A field reaches the log only if its name is on the allow-list below and its
value has the expected type and shape. Anything else is dropped silently and
its value is never written, so session content, names, emails and tokens cannot
leak through a stray keyword argument. Errors are logged by exception class name
and a stable code only: never ``str(exc)``, ``repr(exc)``, notes, causes or a
traceback.

Each identifier field has its own exact shape, so a Firebase UID, an API key or
a sentence squashed into one word cannot pass as an id:

- ``request_id``, ``session_id``: a canonical lowercase UUID
  (``8-4-4-4-12`` hex) or 32 lowercase hex characters.
- ``scenario_id``: a lowercase hyphen slug such as ``resistant-client``, at most
  64 characters. No underscores or dots.
- ``scenario_version``: semantic version ``MAJOR.MINOR.PATCH``, up to four
  digits each.

Counts (``completed``, ``failed``, ``overdue``) and ``duration_ms`` must be
non-negative and below ``2**63``; ``status_code`` must be 100 to 599.

``ContentFreeErrors`` is a pure ASGI middleware that turns an unhandled
exception into the generic 500 envelope (or a 1011 close for a websocket) and
logs it by class and code, before the server could print a traceback. From an
exception group it answers the errors and re-raises only the rest (such as a
cancellation), without the original group as context.

Copy rule (owner decision 2026-11-23): the canonical copy is
``services/accounts/cst_accounts/content_free_log.py``. Every other service
holds a byte-identical copy in its own ``cst_<service>`` package, and
``tests/test_content_free_log_copies.py`` in each service fails on drift. Edit
the accounts copy, then copy the file over the others.

Standard library only, so any service can hold a copy.
"""

import json
import math
import re
import sys
import threading
from collections.abc import Awaitable, Callable, MutableMapping
from contextlib import suppress
from typing import Any, Literal, get_args

Severity = Literal[
    "DEFAULT",
    "DEBUG",
    "INFO",
    "NOTICE",
    "WARNING",
    "ERROR",
    "CRITICAL",
    "ALERT",
    "EMERGENCY",
]

_SEVERITIES: frozenset[str] = frozenset(get_args(Severity))
# Event names and error codes are code literals in snake_case.
_EVENT = re.compile(r"[a-z][a-z0-9_]{0,63}", re.ASCII)
_ERROR_CLASS = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}", re.ASCII)
_INVALID_EVENT = "invalid_event"
_INVALID_CODE = "invalid_code"

_OPAQUE_ID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{32}",
    re.ASCII,
)
_IDENTIFIER_FIELDS: dict[str, re.Pattern[str]] = {
    "request_id": _OPAQUE_ID,
    "session_id": _OPAQUE_ID,
    "scenario_id": re.compile(r"(?=.{1,64}\Z)[a-z0-9]+(-[a-z0-9]+)*", re.ASCII),
    "scenario_version": re.compile(r"[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}", re.ASCII),
}
# Named counts. infra/accounts/main.tf log metrics filter on jsonPayload.failed
# and jsonPayload.overdue, so these stay top-level integers.
_COUNT_FIELDS = frozenset({"completed", "failed", "overdue"})
_NUMBER_LIMIT = 2**63

_WRITE_LOCK = threading.Lock()


def log_event(event: str, *, severity: Severity = "INFO", **fields: object) -> None:
    """Log ``event`` with only the allow-listed ``fields`` that are well typed."""
    _write(_entry(event, severity, fields))


def log_error(event: str, exc: BaseException, *, code: str, **fields: object) -> None:
    """Log an error by its class name and stable ``code``, never its message."""
    entry = _entry(event, "ERROR", fields)
    error_class = type(exc).__name__
    entry["error_class"] = (
        error_class if _matches(_ERROR_CLASS, error_class) else "UnnamedError"
    )
    entry["error_code"] = code if _matches(_EVENT, code) else _INVALID_CODE
    _write(entry)


def _entry(event: str, severity: str, fields: dict[str, object]) -> dict[str, object]:
    name = event if _matches(_EVENT, event) else _INVALID_EVENT
    entry: dict[str, object] = {
        "severity": severity if severity in _SEVERITIES else "DEFAULT",
        "message": name,
        "event": name,
    }
    for key, value in fields.items():
        clean = _allowed(key, value)
        if clean is not None:
            entry[key] = clean
    return entry


def _allowed(key: str, value: object) -> object | None:
    """Return the value to log for ``key``, or ``None`` to drop the field."""
    pattern = _IDENTIFIER_FIELDS.get(key)
    if pattern is not None:
        return value if _matches(pattern, value) else None
    if isinstance(value, bool):
        # bool is a subclass of int, and True is not a count, status or duration.
        return None
    if key in _COUNT_FIELDS and isinstance(value, int):
        return value if 0 <= value < _NUMBER_LIMIT else None
    if key == "status_code" and isinstance(value, int):
        return value if 100 <= value <= 599 else None
    if key == "duration_ms" and isinstance(value, int | float):
        # Range first: math.isfinite raises on an int too large for a float.
        in_range = 0 <= value < _NUMBER_LIMIT and math.isfinite(value)
        return value if in_range else None
    return None


def _matches(pattern: re.Pattern[str], value: object) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _write(entry: dict[str, object]) -> None:
    # Logging must never break the caller, even when stdout is closed.
    try:
        line = json.dumps(entry, ensure_ascii=True, allow_nan=False) + "\n"
        with _WRITE_LOCK:
            sys.stdout.write(line)
            sys.stdout.flush()
    except (OSError, ValueError, TypeError):
        return


# ASGI types, spelled with the standard library so no framework is needed.
Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

_ERROR_BODY = json.dumps({"detail": "Internal server error."}).encode()


class ContentFreeErrors:
    """Answer any unhandled exception without echoing it (DAT-7).

    A framework ``Exception`` handler is not enough: Starlette's
    ``ServerErrorMiddleware`` re-raises after running it, and uvicorn then logs
    the traceback, whose message may echo a student's turn. This middleware
    catches the exception first, logs only its class and a stable code, and
    sends the generic 500 envelope (HTTP) or a 1011 close (websocket). Add it as
    the innermost middleware so the 500 still gets CORS and cache headers.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        kind = scope.get("type")
        if kind not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        started = False

        async def tracked_send(message: Message) -> None:
            nonlocal started
            started = started or message.get("type") == "http.response.start"
            await send(message)

        try:
            await self.app(scope, receive, tracked_send)
        except BaseExceptionGroup as group:
            # A group may mix a cancellation (not an Exception) with an error
            # whose message echoes content. Answer the errors; re-raise only the
            # rest, unchained, so no traceback can print the original group.
            errors, rest = group.split(Exception)
            if errors is not None:
                await _answer(errors, kind == "websocket", started, send)
            if rest is not None:
                raise _content_free_group(rest) from None
        except Exception as exc:  # noqa: BLE001 - the catch-all; logged by class only
            await _answer(exc, kind == "websocket", started, send)


def _content_free_group(rest: BaseExceptionGroup[BaseException]) -> BaseException:
    """Rebuild ``rest`` so its traceback cannot print content.

    ``split`` copies the original group's message, and a nested group or a
    leaf's chained context may carry content too. The new group has a fixed
    message, holds only the leaves, and suppresses each leaf's chain.
    """
    leaves: list[BaseException] = []
    pending: list[BaseException] = [rest]
    while pending:
        current = pending.pop(0)
        if isinstance(current, BaseExceptionGroup):
            pending[:0] = list(current.exceptions)
            continue
        current.__cause__ = None
        current.__suppress_context__ = True
        leaves.append(current)
    return BaseExceptionGroup("unhandled_error", leaves)


async def _answer(
    exc: BaseException, websocket: bool, started: bool, send: Send
) -> None:
    """Log ``exc`` by class and code, then send the generic error reply."""
    if websocket:
        log_error("unhandled_error", exc, code="internal_error")
        reply: list[Message] = [{"type": "websocket.close", "code": 1011}]
    elif started:
        # The status line is on the wire, so no second response can follow.
        log_error("unhandled_error", exc, code="internal_error_after_start")
        reply = []
    else:
        log_error("unhandled_error", exc, code="internal_error", status_code=500)
        reply = _internal_error_response()
    # A failed send must not raise here: its traceback would chain the
    # original exception, message included, as its context.
    with suppress(Exception):
        for message in reply:
            await send(message)


def _internal_error_response() -> list[Message]:
    return [
        {
            "type": "http.response.start",
            "status": 500,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(_ERROR_BODY)).encode()),
            ],
        },
        {"type": "http.response.body", "body": _ERROR_BODY},
    ]
