"""HTTP boundary for the session service (FR-1 to FR-8).

Every route except ``/health`` depends on the ``approved`` guard, copied from
the accounts service (``tests/test_identity_copy.py`` keeps the copies equal).
The owner always comes from the verified token: no request carries a UID.

A request passes, outermost first: the no-store headers, CORS, the request
limits (no query string, a 1 MiB body cap), the content-free error wrapper and
then the router. Every error body is a fixed code, so nothing a student wrote
and nothing from the persona call is echoed (T3).
"""

import json
from collections.abc import Awaitable, Callable
from typing import Annotated, Final, Literal

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .content_free_log import ContentFreeErrors
from .identity.domain import (
    AccessNotApproved,
    AccessReader,
    AccessState,
    DeletionPending,
    Rejected,
    Student,
    TokenVerifier,
    Unavailable,
)
from .lifecycle import EndedBy, EndReason, InvalidTurn, Sessions, StartRefused
from .persona.port import PersonaUnavailable
from .state import MAX_STATE_CHARS, StateRejected

MAX_BODY_BYTES: Final = 1024 * 1024
REFUSED_ORIGINS: Final = frozenset({"*", "null"})
_START_REFUSED_STATUS: Final = {"scenario_unavailable": 404, "opt_in_required": 403}


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class StartRequest(_Body):
    # Configuration only. Which scenario is released is checked on the server.
    scenario_id: str = Field(pattern=r"^[a-z_]{1,64}$")
    crisis_opt_in: StrictBool
    save_transcript: StrictBool
    modality: Literal["text"]


class TurnRequest(_Body):
    state: StrictStr = Field(min_length=1, max_length=MAX_STATE_CHARS)
    # Checked by the lifecycle, so a bad turn gets ``invalid_turn``.
    text: StrictStr


class EndRequest(_Body):
    state: StrictStr = Field(min_length=1, max_length=MAX_STATE_CHARS)


class StartResponse(BaseModel):
    session_id: str
    state: str
    time_limit_ms: int
    remaining_ms: int


class TurnResponse(BaseModel):
    reply: str
    state: str
    remaining_ms: int


class EndResponse(BaseModel):
    outcome: Literal["unscored"]
    reason: EndReason
    ended_by: EndedBy


def _fixed(status: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": code})


class RequestLimits:
    """Refuses a query string (400) and a body over the cap (413) before parsing (T9).

    A declared ``Content-Length`` over the cap is refused without reading. A
    chunked body is read only up to the cap. The accepted body is replayed to
    the app unchanged.
    """

    def __init__(self, app: ASGIApp, max_body_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope.get("query_string"):
            await _send_fixed(send, 400, "invalid_request")
            return
        declared = _content_length(scope)
        if declared == "invalid":
            await _send_fixed(send, 400, "invalid_request")
            return
        if declared is not None and declared > self.max_body_bytes:
            await _send_fixed(send, 413, "request_too_large")
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body += message.get("body", b"")
            if len(body) > self.max_body_bytes:
                await _send_fixed(send, 413, "request_too_large")
                return
            if not message.get("more_body", False):
                break
        await self.app(scope, _replay(bytes(body), receive), send)


def _content_length(scope: Scope) -> int | Literal["invalid"] | None:
    values = [
        value for name, value in scope.get("headers", []) if name == b"content-length"
    ]
    if not values:
        return None
    if len(values) > 1 or not values[0].isdigit():
        return "invalid"
    return int(values[0])


def _replay(body: bytes, receive: Receive) -> Receive:
    sent = False

    async def replayed() -> Message:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()

    return replayed


async def _send_fixed(send: Send, status: int, code: str) -> None:
    body = json.dumps({"detail": code}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def checked_origins(origins: tuple[str, ...]) -> tuple[str, ...]:
    """Exact origins only. A wildcard or ``null`` origin stops startup."""
    if REFUSED_ORIGINS.intersection(origins):
        raise ValueError("CST_ALLOWED_ORIGINS may not contain '*' or 'null'.")
    return origins


def create_app(
    auth: TokenVerifier,
    store: AccessReader,
    sessions: Sessions,
    origins: tuple[str, ...] = (),
) -> FastAPI:
    """Construct the app without creating credentials or connecting to cloud."""
    app = FastAPI(
        title="CaseStudy Tech Sessions", docs_url=None, redoc_url=None, openapi_url=None
    )
    # Added first, so it is the innermost middleware: its 500 still passes
    # through the limits, CORS and no-store middleware below.
    app.add_middleware(ContentFreeErrors)
    app.add_middleware(RequestLimits)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(checked_origins(origins)),
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=False,
    )

    @app.middleware("http")
    async def no_cache(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        # Default validation responses echo the input, which here is turn text.
        return _fixed(400, "invalid_request")

    @app.exception_handler(Rejected)
    async def rejected(request: Request, error: Rejected) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": "Sign in again."})

    @app.exception_handler(DeletionPending)
    async def deletion_pending(
        request: Request, error: DeletionPending
    ) -> JSONResponse:
        # A stable code the client can map to its own wording. Never carries
        # provider error bodies.
        return JSONResponse(
            status_code=403, content={"detail": "account_deletion_pending"}
        )

    @app.exception_handler(AccessNotApproved)
    async def access_not_approved(
        request: Request, error: AccessNotApproved
    ) -> JSONResponse:
        # One code for missing, pending and denied accounts. The client reads
        # the exact state from GET /v1/access.
        return JSONResponse(status_code=403, content={"detail": "access_not_approved"})

    @app.exception_handler(Unavailable)
    async def unavailable(request: Request, error: Unavailable) -> JSONResponse:
        return JSONResponse(
            status_code=503, content={"detail": "Service temporarily unavailable."}
        )

    @app.exception_handler(StartRefused)
    async def start_refused(request: Request, error: StartRefused) -> JSONResponse:
        # Unknown and unreleased scenarios get the same 404.
        return _fixed(_START_REFUSED_STATUS[error.code], error.code)

    @app.exception_handler(InvalidTurn)
    async def invalid_turn(request: Request, error: InvalidTurn) -> JSONResponse:
        return _fixed(400, error.code)

    @app.exception_handler(StateRejected)
    async def state_rejected(request: Request, error: StateRejected) -> JSONResponse:
        return _fixed(409, error.code)

    @app.exception_handler(PersonaUnavailable)
    async def persona_unavailable(
        request: Request, error: PersonaUnavailable
    ) -> JSONResponse:
        # One client code. The cause is in the logs only, and no state is
        # returned, so the failed turn cannot be continued.
        return _fixed(503, "persona_unavailable")

    def eligible(student: Student) -> Student:
        if store.pending(student.uid):
            raise DeletionPending()
        return student

    def bearer(request: Request) -> str:
        # Gateway replaces Authorization. Independently verify the forwarded
        # original token; never trust decoded gateway Userinfo alone.
        header = request.headers.get(
            "X-Forwarded-Authorization", request.headers.get("Authorization", "")
        )
        parts = header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise Rejected()
        return parts[1]

    def token_owner(request: Request) -> Student:
        return auth.verify(bearer(request))

    def signed_in(request: Request) -> Student:
        return eligible(token_owner(request))

    def approved(student: Annotated[Student, Depends(signed_in)]) -> Student:
        """The guard for every protected route (POLICY ACC-4, ACC-7).

        Read on every request with no cache, so a deny or revoke applies on the
        next one. A store failure raises Unavailable (503), never an approval.
        """
        if store.access_state(student.uid) is not AccessState.APPROVED:
            raise AccessNotApproved()
        return student

    # Exposed so tests/test_session_access.py finds the guard by identity.
    app.state.approval_guard = approved

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # Every other route depends on `approved`. tests/test_session_access.py
    # walks the route table, so a new route that skips it fails the build.
    @app.post("/v1/sessions", response_model=StartResponse)
    async def start_session(
        body: StartRequest, student: Annotated[Student, Depends(approved)]
    ) -> StartResponse:
        started = sessions.start(
            owner_uid=student.uid,
            scenario_id=body.scenario_id,
            crisis_opt_in=body.crisis_opt_in,
            save_transcript=body.save_transcript,
        )
        return StartResponse(
            session_id=started.session_id,
            state=started.state,
            time_limit_ms=started.time_limit_ms,
            remaining_ms=started.remaining_ms,
        )

    @app.post("/v1/sessions/turns", response_model=TurnResponse)
    async def take_turn(
        body: TurnRequest, student: Annotated[Student, Depends(approved)]
    ) -> TurnResponse:
        turned = await sessions.turn(
            owner_uid=student.uid, state=body.state, text=body.text
        )
        return TurnResponse(
            reply=turned.reply, state=turned.state, remaining_ms=turned.remaining_ms
        )

    @app.post("/v1/sessions/end", response_model=EndResponse)
    async def end_session(
        body: EndRequest, student: Annotated[Student, Depends(approved)]
    ) -> EndResponse:
        ended = await sessions.end(owner_uid=student.uid, state=body.state)
        return EndResponse(
            outcome=ended.outcome, reason=ended.reason, ended_by=ended.ended_by
        )

    return app
