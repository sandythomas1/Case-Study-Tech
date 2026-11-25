"""T2: every session route except /health requires an approved, non-deleting student.

The matrix follows the accounts service's ``tests/test_access.py``. On every
rejection the persona is never called (FR-1).
"""

import inspect
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute, APIWebSocketRoute
from starlette.routing import Mount

from cst_session import api as api_module
from cst_session.api import create_app
from cst_session.identity.domain import AccessState
from tests.api_fakes import OTHER_TOKEN, TOKEN, Api, FakeAuth, FakeStore, api
from tests.lifecycle_fakes import OWNER, started

ALLOWED_WITHOUT_APPROVAL = {("GET", "/health")}
PROTECTED = {
    ("POST", "/v1/sessions"),
    ("POST", "/v1/sessions/turns"),
    ("POST", "/v1/sessions/end"),
}


def calls(target: Api) -> dict[str, Callable[..., Any]]:
    """Each protected route, called with a body that would otherwise succeed."""
    state = started(target.h)
    return {
        "start": lambda **kw: target.start(**kw),
        "turn": lambda **kw: target.turn(state, **kw),
        "end": lambda **kw: target.end(state, **kw),
    }


ROUTES = ["start", "turn", "end"]


def assert_refused(response: Any, status: int, detail: str, target: Api) -> None:
    assert response.status_code == status
    assert response.json() == {"detail": detail}
    assert "state" not in response.json()
    assert target.persona.calls == []
    assert target.h.grader.received == []


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Basic abc"},
        {"Authorization": f"Bearer {TOKEN} extra"},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer unknown-token"},
        {"X-Forwarded-Authorization": "Bearer unknown-token"},
    ],
)
def test_t2_missing_or_bad_credential_is_401(
    route: str, headers: dict[str, str]
) -> None:
    target = api()
    response = calls(target)[route](token=None, headers=headers)
    assert_refused(response, 401, "Sign in again.", target)


@pytest.mark.parametrize("route", ROUTES)
def test_t2_forwarded_token_wins_over_gateway_authorization(route: str) -> None:
    target = api()
    headers = {
        "X-Forwarded-Authorization": "Bearer unknown-token",
        "Authorization": f"Bearer {TOKEN}",
    }
    response = calls(target)[route](token=None, headers=headers)
    assert_refused(response, 401, "Sign in again.", target)


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize(
    "state", [AccessState.MISSING, AccessState.PENDING, AccessState.DENIED]
)
def test_t2_unapproved_account_is_403(route: str, state: AccessState) -> None:
    target = api()
    target.store.access[OWNER] = state
    response = calls(target)[route]()
    assert_refused(response, 403, "access_not_approved", target)


@pytest.mark.parametrize("route", ROUTES)
def test_t2_pending_deletion_is_403(route: str) -> None:
    target = api()
    target.store.deletions.add(OWNER)
    response = calls(target)[route]()
    assert_refused(response, 403, "account_deletion_pending", target)


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("failing", ["auth", "store"])
def test_t2_dependency_outage_is_503_never_approval(route: str, failing: str) -> None:
    target = api()
    if failing == "auth":
        target.auth.unavailable = True
    else:
        target.store.unavailable = True
    response = calls(target)[route]()
    assert_refused(response, 503, "Service temporarily unavailable.", target)


def test_t2_revoke_between_turns_applies_on_the_next_request() -> None:
    target = api()
    state = target.start().json()["state"]
    first = target.turn(state)
    assert first.status_code == 200
    target.store.access[OWNER] = AccessState.DENIED
    second = target.turn(first.json()["state"])
    assert second.status_code == 403
    assert second.json() == {"detail": "access_not_approved"}
    assert len(target.persona.calls) == 1


def test_t2_approval_is_read_on_every_request() -> None:
    target = api()
    state = target.start().json()["state"]
    target.turn(state)
    reads = [read for read, _ in target.store.reads]
    assert reads.count("access_state") == 2
    assert reads.count("pending") == 2


def test_t2_another_students_token_cannot_use_the_state() -> None:
    target = api()
    state = target.start().json()["state"]
    response = target.turn(state, token=OTHER_TOKEN)
    assert response.status_code == 409
    assert response.json() == {"detail": "state_invalid"}
    assert target.persona.calls == []


def test_t2_health_is_unguarded_and_reads_nothing() -> None:
    target = api()
    response = target.client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert target.store.reads == [] and target.auth.verified == []


def dependency_calls(dependant: Any) -> Iterator[Any]:
    for child in dependant.dependencies:
        yield child.call
        yield from dependency_calls(child)


def route_inventory(app: FastAPI) -> set[tuple[str, str]]:
    """Every (method, path), asserting each one outside the allow-list is guarded."""
    guard = app.state.approval_guard
    seen: set[tuple[str, str]] = set()
    for route in app.routes:
        if isinstance(route, APIRoute):
            methods = sorted(route.methods or ())
        elif isinstance(route, APIWebSocketRoute):
            methods = ["WEBSOCKET"]
        else:
            # A mount or raw route would bypass dependencies entirely. The
            # OpenAPI route is off, so nothing else is allowed.
            raise AssertionError(f"unchecked route {route!r}")
        for method in methods:
            seen.add((method, route.path))
            guarded = any(call is guard for call in dependency_calls(route.dependant))
            if (method, route.path) in ALLOWED_WITHOUT_APPROVAL:
                assert not guarded, (method, route.path)
            else:
                assert guarded, f"{method} {route.path} skips the approval guard"
    return seen


def app() -> FastAPI:
    return create_app(FakeAuth(), FakeStore(), api().h.sessions)


def test_t2_every_route_outside_the_allow_list_depends_on_the_guard() -> None:
    seen = route_inventory(app())
    # The allow-list names only routes that exist, so it can't silently grow.
    assert seen == ALLOWED_WITHOUT_APPROVAL | PROTECTED


def test_t2_inventory_counts_websocket_routes() -> None:
    target = app()

    @target.websocket("/v1/sessions/live")
    async def live(websocket: Any) -> None:
        await websocket.close()

    with pytest.raises(AssertionError, match="WEBSOCKET /v1/sessions/live"):
        route_inventory(target)


def test_t2_inventory_fails_on_a_mount() -> None:
    target = app()
    target.router.routes.append(Mount("/static", app=FastAPI()))
    with pytest.raises(AssertionError, match="unchecked route"):
        route_inventory(target)


def test_t2_no_route_path_names_a_scenario() -> None:
    assert all("scenario" not in path for _, path in route_inventory(app()))


def test_t2_no_setting_turns_the_gate_off(monkeypatch: pytest.MonkeyPatch) -> None:
    # The same gate in every environment. create_app takes no flag and reads no
    # environment variable that could skip it.
    assert set(inspect.signature(create_app).parameters) == {
        "auth",
        "store",
        "sessions",
        "origins",
    }
    for name in ("ENV", "APP_ENV", "DEBUG", "SKIP_ACCESS_GATE", "ACCESS_GATE"):
        monkeypatch.setenv(name, "off")
    target = api()
    target.store.access[OWNER] = AccessState.PENDING
    assert target.start().status_code == 403
    assert "environ" not in inspect.getsource(api_module)
