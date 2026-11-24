"""HTTP boundary for the accounts service."""

import contextlib
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from .content_free_log import ContentFreeErrors
from .domain import (
    AccessDenied,
    AccessNotApproved,
    AccessState,
    AccountStore,
    DeletionPending,
    IdentityProvider,
    ProfileUnusable,
    Rejected,
    Score,
    Student,
    Tokens,
    Unavailable,
)


class GoogleCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")
    credential: str = Field(min_length=1, max_length=8192)


class RefreshCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str = Field(min_length=1, max_length=8192)


class AccessRequest(BaseModel):
    """An access request carries nothing: identity comes from the token only."""

    model_config = ConfigDict(extra="forbid")


class AccessStatus(BaseModel):
    state: AccessState


class DeleteConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: Literal["DELETE"]


def create_app(
    auth: IdentityProvider, store: AccountStore, origins: tuple[str, ...] = ()
) -> FastAPI:
    """Construct the app without creating credentials or connecting to cloud."""
    app = FastAPI(title="CaseStudy Tech Accounts", docs_url=None, redoc_url=None)
    # Added first, so it is the innermost middleware: its 500 still passes
    # through the CORS and no-store middleware below, like every other response.
    app.add_middleware(ContentFreeErrors)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins),
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
        # Default validation responses can echo credential inputs.
        return JSONResponse(status_code=400, content={"detail": "Invalid request."})

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

    @app.exception_handler(ProfileUnusable)
    async def profile_unusable(
        request: Request, error: ProfileUnusable
    ) -> JSONResponse:
        # Not 401: signing in again would return the same token claims.
        return JSONResponse(status_code=403, content={"detail": "profile_unusable"})

    @app.exception_handler(AccessDenied)
    async def access_denied(request: Request, error: AccessDenied) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": "access_denied"})

    @app.exception_handler(Unavailable)
    async def unavailable(request: Request, error: Unavailable) -> JSONResponse:
        return JSONResponse(
            status_code=503, content={"detail": "Service temporarily unavailable."}
        )

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

    # Exposed so tests/test_access.py can find the guard by identity, not name.
    app.state.approval_guard = approved

    def validated_tokens(tokens: Tokens) -> Tokens:
        eligible(auth.verify(tokens.id_token))
        return tokens

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/auth/google", response_model=Tokens)
    def google_login(body: GoogleCredential) -> Tokens:
        return validated_tokens(auth.exchange(body.credential))

    @app.post("/v1/auth/refresh", response_model=Tokens)
    def refresh(body: RefreshCredential) -> Tokens:
        return validated_tokens(auth.refresh(body.refresh_token))

    # Protected (owner, 2026-11-24). Before approval the app checks /v1/access.
    @app.get("/v1/me")
    def me(student: Annotated[Student, Depends(approved)]) -> dict[str, str]:
        return {"uid": student.uid}

    @app.get("/v1/access", response_model=AccessStatus)
    def access_state(
        request: Request, student: Annotated[Student, Depends(signed_in)]
    ) -> AccessStatus:
        if request.query_params:
            raise HTTPException(400, "Query parameters are not supported.")
        return AccessStatus(state=store.access_state(student.uid))

    @app.post("/v1/access/request", response_model=AccessStatus)
    def request_access(
        request: Request, body: AccessRequest | None = None
    ) -> AccessStatus:
        # Name and email come from the verified token. The body may only be
        # empty, so a forged UID, name, email or state is rejected (400).
        if request.query_params:
            raise HTTPException(400, "Query parameters are not supported.")
        profile = auth.profile(bearer(request))
        eligible(Student(uid=profile.uid))
        # The store re-checks the deletion marker inside its transaction.
        return AccessStatus(state=store.request_access(profile, datetime.now(UTC)))

    # Every other route depends on `approved`. tests/test_access.py walks the
    # route table, so a new route that skips it fails the build.
    @app.get("/v1/scores")
    def scores(
        request: Request, student: Annotated[Student, Depends(approved)]
    ) -> dict[str, list[Score]]:
        if request.query_params:
            raise HTTPException(400, "Query parameters are not supported.")
        return {
            "scores": [
                Score.model_validate(record) for record in store.scores(student.uid)
            ]
        }

    @app.post("/v1/account/deletion", status_code=202)
    def request_deletion(
        body: DeleteConfirmation, student: Annotated[Student, Depends(token_owner)]
    ) -> dict[str, object]:
        # Not gated by a pending deletion: a retry after a lost 202 gets the
        # owner's existing request back. The store only touches the token's uid.
        deletion = store.request_deletion(student.uid, datetime.now(UTC))
        # Persist denial before revocation. The worker retries provider outages.
        with contextlib.suppress(Unavailable):
            auth.disable(student.uid)
        return {
            "accepted": True,
            "requested_at": deletion.requested_at,
            "deadline": deletion.deadline,
        }

    return app
