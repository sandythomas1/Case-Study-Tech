"""Owner approval gate (#72) through the real HTTP router (POLICY ACC-4…ACC-9).

The store and identity provider are the in-memory fakes from test_accounts.py.
The real Firestore store is covered in test_store_emulator.py and the rules in
infra/rules.test.mjs.
"""

import json
import logging

import pytest
from fastapi.testclient import TestClient
from test_accounts import FakeAuth, FakeStore

from cst_accounts.api import create_app

NEW = {"Authorization": "Bearer student-new"}
APPROVED = {"Authorization": "Bearer student-a"}

# Protected routes (ACC-4). /v1/me is protected by owner decision, 2026-11-24.
PROTECTED = [("GET", "/v1/me"), ("GET", "/v1/scores")]
# Reachable before approval (ACC-4). Sign-in and refresh carry no bearer token.
UNGATED = [
    ("GET", "/v1/access", None),
    ("POST", "/v1/access/request", None),
    ("POST", "/v1/account/deletion", {"confirmation": "DELETE"}),
]


@pytest.fixture
def setup():
    auth, store = FakeAuth(), FakeStore()
    with TestClient(create_app(auth, store)) as client:
        yield client, auth, store


def headers(uid):
    return {"Authorization": f"Bearer {uid}"}


# AC1: one request, idempotent, denied creates nothing


def test_a_first_request_creates_one_pending_record_from_the_token(setup):
    client, _, store = setup
    assert client.get("/v1/access", headers=NEW).json() == {"state": "missing"}

    response = client.post("/v1/access/request", headers=NEW)

    assert response.status_code == 200
    assert response.json() == {"state": "pending"}
    assert store.access == {
        "student-a": "approved",
        "student-b": "approved",
        "student-new": "pending",
    }
    assert client.get("/v1/access", headers=NEW).json() == {"state": "pending"}


def test_a_repeated_request_returns_the_existing_state_and_adds_nothing(setup):
    client, _, store = setup
    for _ in range(3):
        assert client.post("/v1/access/request", headers=NEW).json() == {
            "state": "pending"
        }
    assert list(store.access).count("student-new") == 1
    # An approved account's request never downgrades it.
    assert client.post("/v1/access/request", headers=APPROVED).json() == {
        "state": "approved"
    }
    assert store.access["student-a"] == "approved"


def test_a_denied_account_cannot_request_again(setup):
    client, _, store = setup
    store.access["student-new"] = "denied"

    response = client.post("/v1/access/request", headers=NEW)

    assert response.status_code == 403
    assert response.json() == {"detail": "access_denied"}
    assert store.access["student-new"] == "denied"
    assert client.get("/v1/access", headers=NEW).json() == {"state": "denied"}


def test_a_store_outage_during_a_request_is_503_and_creates_nothing(setup):
    from cst_accounts.domain import Unavailable

    client, _, store = setup

    def outage(profile, now):
        raise Unavailable()

    store.request_access = outage
    response = client.post("/v1/access/request", headers=NEW)
    assert response.status_code == 503
    assert "student-new" not in store.access


# AC2: the guard admits approved only, and fails closed


@pytest.mark.parametrize("state", ["missing", "pending", "denied"])
@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_the_guard_rejects_every_unapproved_state(setup, state, method, path):
    client, _, store = setup
    if state != "missing":
        store.access["student-new"] = state
    store.records["student-new"] = [
        {"scenario_id": "routine", "overall": 3, "categories": [3] * 6}
    ]

    response = client.request(method, path, headers=NEW)

    assert response.status_code == 403
    assert response.json() == {"detail": "access_not_approved"}
    assert "routine" not in response.text
    assert "student-new" not in response.text


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_the_guard_admits_an_approved_account(setup, method, path):
    client, _, _ = setup
    response = client.request(method, path, headers=APPROVED)
    assert response.status_code == 200


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_a_store_failure_during_the_check_is_rejected_not_admitted(setup, method, path):
    client, _, store = setup
    store.access_unavailable = True
    response = client.request(method, path, headers=APPROVED)
    assert response.status_code == 503
    assert "scores" not in response.text


@pytest.mark.parametrize(("method", "path", "body"), UNGATED)
def test_access_state_request_and_deletion_need_no_approval(setup, method, path, body):
    client, _, _ = setup
    response = client.request(method, path, headers=NEW, json=body)
    assert response.status_code in {200, 202}


def test_access_routes_still_require_a_verified_token(setup):
    client, _, store = setup
    for method, path, _ in UNGATED[:2]:
        assert client.request(method, path).status_code == 401
        assert (
            client.request(method, path, headers=headers("forged")).status_code == 401
        )
    assert set(store.access) == {"student-a", "student-b"}


def queue_deletion_without_revocation(store, uid):
    # The deletion marker exists but the provider has not yet disabled the
    # identity (a revocation outage), so the old token still verifies.
    from datetime import UTC, datetime

    store.request_deletion(uid, datetime.now(UTC))


def test_an_account_being_deleted_cannot_request_access(setup):
    client, _, store = setup
    queue_deletion_without_revocation(store, "student-new")
    assert client.get("/v1/access", headers=NEW).json() == {
        "detail": "account_deletion_pending"
    }
    response = client.post("/v1/access/request", headers=NEW)
    assert response.status_code == 403
    assert response.json() == {"detail": "account_deletion_pending"}
    assert "student-new" not in store.access


def test_a_deletion_confirmed_after_the_eligibility_check_still_wins(setup):
    # DAT-3: the store re-checks the marker inside its create transaction.
    client, _, store = setup
    real = store.pending
    calls = []

    def marker_lands_after_first_check(uid):
        calls.append(uid)
        if len(calls) == 1:
            result = real(uid)
            queue_deletion_without_revocation(store, uid)
            return result
        return real(uid)

    store.pending = marker_lands_after_first_check
    response = client.post("/v1/access/request", headers=NEW)
    assert response.json() == {"detail": "account_deletion_pending"}
    assert "student-new" not in store.access


def test_deletion_pending_wins_over_approval(setup):
    client, _, store = setup
    queue_deletion_without_revocation(store, "student-a")
    response = client.get("/v1/scores", headers=APPROVED)
    assert response.json() == {"detail": "account_deletion_pending"}


# The allow-list is closed: a route added later without `approved` fails here.
# #31 copies this test for the session service.

ALLOWED_WITHOUT_APPROVAL = {
    ("GET", "/health"),
    ("POST", "/v1/auth/google"),
    ("POST", "/v1/auth/refresh"),
    ("GET", "/v1/access"),
    ("POST", "/v1/access/request"),
    ("POST", "/v1/account/deletion"),
}


def dependency_calls(dependant):
    for child in dependant.dependencies:
        yield child.call
        yield from dependency_calls(child)


def test_every_route_outside_the_allow_list_depends_on_the_approval_guard():
    from fastapi.routing import APIRoute, APIWebSocketRoute

    app = create_app(FakeAuth(), FakeStore())
    guard = app.state.approval_guard
    seen = set()
    for route in app.routes:
        if isinstance(route, APIRoute):
            methods = sorted(route.methods or ())
        elif isinstance(route, APIWebSocketRoute):
            methods = ["WEBSOCKET"]
        else:
            # A mount or raw route would bypass dependencies entirely.
            path = getattr(route, "path", None)
            assert path == "/openapi.json", f"unchecked route {route!r}"
            continue
        for method in methods:
            seen.add((method, route.path))
            guarded = any(call is guard for call in dependency_calls(route.dependant))
            if (method, route.path) in ALLOWED_WITHOUT_APPROVAL:
                assert not guarded, (method, route.path)
            else:
                assert guarded, f"{method} {route.path} skips the approval guard"
    # The allow-list names only routes that exist, so it can't silently grow.
    assert seen >= ALLOWED_WITHOUT_APPROVAL
    assert {(m, p) for m, p in PROTECTED} <= seen


def test_no_setting_turns_the_gate_off(monkeypatch):
    # ACC-9: the same gate in every environment. create_app takes no flag and
    # reads no environment variable that could skip it.
    import inspect

    from cst_accounts import api

    assert set(inspect.signature(create_app).parameters) == {"auth", "store", "origins"}
    for name in ("ENV", "APP_ENV", "DEBUG", "SKIP_ACCESS_GATE", "ACCESS_GATE"):
        monkeypatch.setenv(name, "off")
    with TestClient(create_app(FakeAuth(), FakeStore())) as client:
        assert client.get("/v1/scores", headers=NEW).status_code == 403
    assert "environ" not in inspect.getsource(api)


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_the_access_record_has_no_client_write_route(setup, method):
    client, _, store = setup
    for path in ("/v1/access", "/v1/access/request"):
        assert client.request(method, path, headers=NEW).status_code == 405
    assert "student-new" not in store.access


def test_an_unusable_profile_is_a_stable_403_not_a_sign_in_loop(setup):
    from cst_accounts.domain import ProfileUnusable

    client, auth, store = setup

    def unusable(token):
        raise ProfileUnusable()

    auth.profile = unusable
    response = client.post("/v1/access/request", headers=NEW)
    assert response.status_code == 403
    assert response.json() == {"detail": "profile_unusable"}
    assert "student-new" not in store.access


# AC3: forged identity in the request has no effect


@pytest.mark.parametrize(
    "forged",
    [
        {"uid": "student-b"},
        {"display_name": "Someone Else"},
        {"name": "Someone Else"},
        {"email": "owner@test.invalid"},
        {"state": "approved"},
        {"uid": "student-new", "state": "approved", "email": "x@test.invalid"},
    ],
)
def test_a_forged_uid_name_email_or_state_in_the_body_has_no_effect(setup, forged):
    client, auth, store = setup
    recorded = []
    store_request = store.request_access

    def spy(profile, now):
        recorded.append(profile)
        return store_request(profile, now)

    store.request_access = spy

    response = client.post("/v1/access/request", headers=NEW, json=forged)

    assert response.status_code == 400
    assert "Someone" not in response.text and "test.invalid" not in response.text
    assert recorded == []
    assert set(store.access) == {"student-a", "student-b"}
    # The same caller with no body records only the verified token's claims.
    assert client.post("/v1/access/request", headers=NEW).json() == {"state": "pending"}
    assert recorded == [auth.profile("student-new")]
    assert store.access["student-b"] == "approved"


def test_an_empty_json_body_is_accepted(setup):
    client, _, store = setup
    response = client.post("/v1/access/request", headers=NEW, json={})
    assert response.json() == {"state": "pending"}
    assert store.access["student-new"] == "pending"


@pytest.mark.parametrize("path", ["/v1/access", "/v1/access/request"])
def test_a_forged_uid_in_the_query_is_rejected(setup, path):
    client, _, store = setup
    method = "POST" if path.endswith("request") else "GET"
    response = client.request(method, f"{path}?uid=student-a", headers=NEW)
    assert response.status_code == 400
    assert "student-new" not in store.access


def test_an_unapproved_caller_cannot_read_another_accounts_state(setup):
    client, _, store = setup
    store.access["student-new"] = "pending"
    response = client.get("/v1/access", headers=NEW)
    assert response.json() == {"state": "pending"}
    for forged in ({"X-Apigateway-Api-Userinfo": "student-a"}, {"X-Uid": "student-a"}):
        assert client.get("/v1/access", headers={**NEW, **forged}).json() == {
            "state": "pending"
        }


# AC4: a revoke applies on the very next request (no positive cache)


def test_a_revoke_between_two_requests_makes_the_second_fail(setup):
    client, _, store = setup
    assert client.get("/v1/scores", headers=APPROVED).status_code == 200

    store.access["student-a"] = "denied"

    response = client.get("/v1/scores", headers=APPROVED)
    assert response.status_code == 403
    assert response.json() == {"detail": "access_not_approved"}


def test_approval_is_read_on_every_protected_request(setup):
    client, _, store = setup
    reads = []
    real = store.access_state

    def counting(uid):
        reads.append(uid)
        return real(uid)

    store.access_state = counting
    for _ in range(3):
        client.get("/v1/scores", headers=APPROVED)
    assert reads == ["student-a"] * 3


def test_approval_on_one_request_does_not_carry_to_another_account(setup):
    client, _, store = setup
    assert client.get("/v1/scores", headers=APPROVED).status_code == 200
    assert client.get("/v1/scores", headers=NEW).status_code == 403


# AC6 (fake store): deletion removes the access record with the scores


def test_the_deletion_sweep_removes_the_access_record_with_the_scores(setup):
    from datetime import UTC, datetime

    from cst_accounts.deletion import process_deletions

    client, auth, store = setup
    client.post(
        "/v1/account/deletion", headers=APPROVED, json={"confirmation": "DELETE"}
    )
    assert process_deletions(auth, store, datetime.now(UTC))["completed"] == 1
    assert "student-a" not in store.access
    assert "student-a" not in store.records
    # Another owner's access record is untouched.
    assert store.access["student-b"] == "approved"


def test_a_revoke_keeps_the_scores(setup):
    # ACC-8: revoking access does not delete scores. Only deletion does.
    client, _, store = setup
    store.access["student-a"] = "denied"
    assert client.get("/v1/scores", headers=APPROVED).status_code == 403
    assert store.records["student-a"]


# AC7: no name or email in logs on success or error paths


def test_no_name_or_email_reaches_logs_on_success_or_error(capsys, caplog, monkeypatch):
    from cst_accounts.domain import Unavailable

    auth, store = FakeAuth(), FakeStore()
    caplog.set_level(logging.DEBUG)
    with TestClient(create_app(auth, store), raise_server_exceptions=False) as client:
        client.post("/v1/access/request", headers=NEW)  # success
        client.post("/v1/access/request", headers=NEW)  # repeat
        client.post("/v1/access/request", headers=NEW, json={"email": "f@x.invalid"})
        store.access["student-b"] = "denied"
        client.post("/v1/access/request", headers=headers("student-b"))  # denied
        client.get("/v1/scores", headers=NEW)  # not approved

        def outage(*args):
            raise Unavailable()

        monkeypatch.setattr(store, "access_state", outage)
        client.get("/v1/scores", headers=APPROVED)  # store failure

        def crash(profile, now):
            raise RuntimeError(f"echo {profile.display_name} {profile.email}")

        monkeypatch.setattr(store, "request_access", crash)
        crashed = client.post("/v1/access/request", headers=headers("student-a"))

    assert crashed.status_code == 500
    captured = capsys.readouterr()
    logged = captured.out + captured.err + caplog.text + crashed.text
    for value in ("Synthetic", "test.invalid", "x.invalid", "@"):
        assert value not in logged
    # The crash is still observable, as its class only.
    events = [json.loads(line) for line in captured.out.splitlines() if line]
    assert any(e.get("error_class") == "RuntimeError" for e in events)


def test_a_profile_repr_never_shows_the_name_or_email():
    from cst_accounts.domain import Profile

    text = repr(Profile(uid="u", display_name="Synthetic Name", email="a@test.invalid"))
    assert "Synthetic" not in text and "test.invalid" not in text


def test_a_transaction_that_exhausts_its_retries_is_unavailable_not_a_500():
    from google.api_core.exceptions import Aborted

    from cst_accounts.domain import Unavailable
    from cst_accounts.store import storage_operation

    with pytest.raises(Unavailable) as raised, storage_operation():
        raise ValueError("Failed to commit transaction in 5 attempts.") from Aborted(
            "Transaction lock timeout."
        )
    assert raised.value.__cause__ is None
    # Any other ValueError is a programming error and still surfaces.
    with pytest.raises(ValueError), storage_operation():
        raise ValueError("bug")


def missing_then(state):
    """access_state for a race: missing on the first read, the winner's after."""
    from cst_accounts.domain import AccessState

    reads = iter([AccessState.MISSING])
    return lambda uid: next(reads, state)


def test_a_racing_request_that_finds_a_denial_is_rejected_not_reported(monkeypatch):
    from datetime import UTC, datetime
    from unittest.mock import MagicMock

    from google.api_core.exceptions import AlreadyExists

    from cst_accounts.domain import AccessDenied, AccessState, Profile
    from cst_accounts.store import FirestoreAccounts

    client = MagicMock()
    client.transaction.side_effect = AlreadyExists("created by a racing request")
    store = FirestoreAccounts(client)
    monkeypatch.setattr(store, "access_state", missing_then(AccessState.DENIED))
    with pytest.raises(AccessDenied):
        store.request_access(
            Profile("student-new", "Synthetic", "student-new@test.invalid"),
            datetime.now(UTC),
        )


@pytest.mark.parametrize("state", ["pending", "approved"])
def test_a_racing_request_reports_the_record_the_winner_created(monkeypatch, state):
    # QA (#72 T10): the AlreadyExists branch re-reads and reports the state as is,
    # and never creates or overwrites a record.
    from datetime import UTC, datetime
    from unittest.mock import MagicMock

    from google.api_core.exceptions import AlreadyExists

    from cst_accounts.domain import AccessState, Profile
    from cst_accounts.store import FirestoreAccounts

    client = MagicMock()
    client.transaction.side_effect = AlreadyExists("created by a racing request")
    store = FirestoreAccounts(client)
    monkeypatch.setattr(store, "access_state", missing_then(AccessState(state)))
    result = store.request_access(
        Profile("student-new", "Synthetic", "student-new@test.invalid"),
        datetime.now(UTC),
    )
    assert result is AccessState(state)
    client.collection.return_value.document.return_value.set.assert_not_called()


def exhausted_retries() -> ValueError:
    from google.api_core.exceptions import Aborted

    error = ValueError("Failed to commit transaction in 5 attempts.")
    error.__cause__ = Aborted("Transaction lock timeout.")
    return error


@pytest.mark.parametrize(
    ("winner", "outcome"),
    [
        ("pending", "pending"),
        ("approved", "approved"),
        ("denied", "AccessDenied"),
        ("missing", "Unavailable"),
    ],
)
def test_contention_that_exhausts_retries_reports_what_the_winner_wrote(
    monkeypatch, winner, outcome
):
    from datetime import UTC, datetime
    from unittest.mock import MagicMock

    from cst_accounts.domain import AccessState, Profile
    from cst_accounts.store import FirestoreAccounts

    client = MagicMock()
    client.transaction.side_effect = exhausted_retries()
    store = FirestoreAccounts(client)
    monkeypatch.setattr(store, "access_state", missing_then(AccessState(winner)))
    profile = Profile("student-new", "Synthetic", "student-new@test.invalid")
    if outcome in {"AccessDenied", "Unavailable"}:
        with pytest.raises(Exception) as raised:
            store.request_access(profile, datetime.now(UTC))
        assert type(raised.value).__name__ == outcome
    else:
        assert store.request_access(profile, datetime.now(UTC)) is AccessState(outcome)


def test_a_value_error_that_is_not_contention_still_surfaces(monkeypatch):
    from datetime import UTC, datetime
    from unittest.mock import MagicMock

    from cst_accounts.domain import AccessState, Profile
    from cst_accounts.store import FirestoreAccounts

    client = MagicMock()
    client.transaction.side_effect = ValueError("bug")
    store = FirestoreAccounts(client)
    monkeypatch.setattr(store, "access_state", missing_then(AccessState.MISSING))
    with pytest.raises(ValueError, match="bug"):
        store.request_access(
            Profile("student-new", "Synthetic", "student-new@test.invalid"),
            datetime.now(UTC),
        )
