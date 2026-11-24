"""Account boundaries exercised through the real HTTP router."""

import json
import logging
import socket
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from cst_accounts.api import create_app

# Synthetic accounts only (POLICY ACC-9). student-a and student-b are
# pre-approved test accounts; student-new has never requested access.
SYNTHETIC_ACCOUNTS = {"student-a", "student-b", "student-new"}


class FakeAuth:
    def __init__(self):
        self.disabled = set()
        self.deleted = set()
        self.unavailable = False

    def verify(self, token):
        from cst_accounts.domain import Rejected, Student, Unavailable

        if self.unavailable:
            raise Unavailable()
        if token not in SYNTHETIC_ACCOUNTS or token in self.disabled:
            raise Rejected()
        return Student(uid=token)

    def profile(self, token):
        from cst_accounts.domain import Profile

        uid = self.verify(token).uid
        return Profile(
            uid=uid, display_name=f"Synthetic {uid}", email=f"{uid}@test.invalid"
        )

    def exchange(self, credential):
        from cst_accounts.domain import DeletionPending, Tokens

        if credential in self.disabled:
            # The provider reports USER_DISABLED for an account being deleted.
            raise DeletionPending()
        self.verify(credential)
        return Tokens(id_token=credential, refresh_token="refresh-a", expires_in=3600)

    def refresh(self, refresh_token):
        from cst_accounts.domain import Rejected

        if refresh_token != "refresh-a":
            raise Rejected()
        return self.exchange("student-a")

    def disable(self, uid):
        from cst_accounts.domain import Unavailable

        if self.unavailable:
            raise Unavailable()
        self.disabled.add(uid)

    def delete(self, uid):
        self.deleted.add(uid)


class FakeStore:
    def __init__(self):
        self.records = {
            "student-a": [
                {
                    "scenario_id": "routine",
                    "overall": 3.5,
                    "categories": [3, 4, 3, 4, 3, 4],
                }
            ],
            "student-b": [
                {"scenario_id": "resistant", "overall": 4.0, "categories": [4] * 6}
            ],
        }
        self.access = {"student-a": "approved", "student-b": "approved"}
        self.access_unavailable = False
        self.requests = {}
        self.erased = []
        self.fail_erase = False
        self.retry_after = {}

    def pending(self, uid):
        return uid in self.requests

    def access_state(self, uid):
        from cst_accounts.domain import AccessState, Unavailable

        if self.access_unavailable:
            raise Unavailable()
        return AccessState(self.access.get(uid, "missing"))

    def request_access(self, profile, now):
        from cst_accounts.domain import AccessDenied, AccessState, DeletionPending

        # Mirrors the Firestore transaction: the marker is re-read at create time.
        if self.pending(profile.uid):
            raise DeletionPending()
        state = self.access.setdefault(profile.uid, "pending")
        if state == "denied":
            raise AccessDenied()
        return AccessState(state)

    def scores(self, uid):
        return self.records.get(uid, [])

    def request_deletion(self, uid, now):
        from cst_accounts.domain import DeletionRequest

        if uid not in self.requests:
            self.requests[uid] = DeletionRequest(uid=uid, requested_at=now)
        return self.requests[uid]

    def due_deletions(self, now):
        return [
            item
            for item in self.requests.values()
            if self.retry_after.get(item.uid, now) <= now
        ]

    def retry_deletion(self, uid, now):
        from datetime import timedelta

        self.retry_after[uid] = now + timedelta(hours=1)

    def erase_student_data(self, uid):
        from cst_accounts.domain import Unavailable

        if self.fail_erase:
            raise Unavailable()
        self.records.pop(uid, None)
        self.access.pop(uid, None)
        self.erased.append(uid)

    def complete_deletion(self, uid, now):
        self.requests.pop(uid, None)


@pytest.fixture
def setup():
    auth, store = FakeAuth(), FakeStore()
    with TestClient(create_app(auth, store)) as client:
        yield client, auth, store


@pytest.mark.parametrize("path", ["/v1/me", "/v1/scores", "/v1/account/deletion"])
def test_allowlisted_browser_preflight_does_not_require_a_student_token(path):
    auth, store = FakeAuth(), FakeStore()
    with TestClient(create_app(auth, store, ("https://student.example",))) as client:
        response = client.options(
            path,
            headers={
                "Origin": "https://student.example",
                "Access-Control-Request-Method": "POST"
                if path.endswith("deletion")
                else "GET",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert response.status_code == 200
        assert (
            response.headers["access-control-allow-origin"] == "https://student.example"
        )
        assert "access-control-allow-credentials" not in response.headers


def test_other_browser_origins_do_not_receive_cors_permission():
    with TestClient(
        create_app(FakeAuth(), FakeStore(), ("https://student.example",))
    ) as client:
        response = client.options(
            "/v1/scores",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize(
    "header", [None, "", "Bearer", "Basic student-a", "Bearer forged", "Bearer a b"]
)
def test_invalid_auth_is_401_without_data_access(setup, header):
    client, _, store = setup
    store.scores = lambda uid: pytest.fail("storage was accessed before authentication")
    headers = {} if header is None else {"Authorization": header}
    response = client.get("/v1/scores", headers=headers)
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


def test_owner_is_derived_from_verified_token(setup):
    client, _, _ = setup
    a = client.get("/v1/scores", headers={"Authorization": "Bearer student-a"})
    b = client.get("/v1/scores", headers={"Authorization": "Bearer student-b"})
    assert a.status_code == b.status_code == 200
    assert a.json()["scores"][0]["scenario_id"] == "routine"
    assert b.json()["scores"][0]["scenario_id"] == "resistant"


def test_caller_cannot_override_identity_with_query_or_gateway_metadata(setup):
    client, _, _ = setup
    response = client.get(
        "/v1/scores?student_id=student-b", headers={"Authorization": "Bearer student-a"}
    )
    assert response.status_code == 400
    response = client.get("/v1/scores", headers={"X-Apigateway-Api-Userinfo": "forged"})
    assert response.status_code == 401
    assert (
        client.get(
            "/v1/students/student-b/scores",
            headers={"Authorization": "Bearer student-a"},
        ).status_code
        == 404
    )


def test_gateway_forwarded_token_is_independently_verified(setup):
    client, _, _ = setup
    response = client.get(
        "/v1/me",
        headers={
            "Authorization": "Bearer gateway-service-token",
            "X-Forwarded-Authorization": "Bearer student-a",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"uid": "student-a"}
    assert (
        client.get(
            "/v1/me", headers={"X-Forwarded-Authorization": "Bearer forged"}
        ).status_code
        == 401
    )


def test_verification_outage_fails_closed(setup):
    client, auth, _ = setup
    auth.unavailable = True
    assert (
        client.get("/v1/me", headers={"Authorization": "Bearer student-a"}).status_code
        == 503
    )


def test_only_google_exchange_and_refresh_routes_exist(setup):
    client, _, _ = setup
    response = client.post("/v1/auth/google", json={"credential": "student-a"})
    assert response.status_code == 200
    assert response.json()["expires_in"] == 3600
    assert response.headers["cache-control"] == "no-store"
    assert (
        client.post("/v1/auth/refresh", json={"refresh_token": "refresh-a"}).status_code
        == 200
    )
    assert client.post("/v1/auth/password", json={}).status_code == 404


def test_invalid_request_never_echoes_credentials(setup):
    client, _, _ = setup
    response = client.post(
        "/v1/auth/google",
        json={"credential": "sensitive-marker", "password": "private-marker"},
    )
    assert response.status_code == 400
    assert "marker" not in response.text
    response = client.post("/v1/auth/google", json={"credential": "forged"})
    assert response.status_code == 401
    assert "forged" not in response.text


def test_deletion_requires_confirmation_and_denies_access_immediately(setup):
    client, auth, store = setup
    headers = {"Authorization": "Bearer student-a"}
    assert (
        client.post("/v1/account/deletion", json={}, headers=headers).status_code == 400
    )
    assert not store.requests
    result = client.post(
        "/v1/account/deletion", json={"confirmation": "DELETE"}, headers=headers
    )
    assert result.status_code == 202
    assert result.json()["accepted"] is True
    assert "student-a" in auth.disabled
    assert "student-a" in store.requests
    assert client.get("/v1/scores", headers=headers).status_code in {401, 403}
    assert "student-b" not in store.requests


PENDING = {"detail": "account_deletion_pending"}


def test_pending_deletion_blocks_refresh_and_new_exchange_with_a_stable_code(setup):
    client, _, store = setup
    store.request_deletion("student-a", datetime.now(UTC))
    exchange = client.post("/v1/auth/google", json={"credential": "student-a"})
    assert exchange.status_code == 403
    assert exchange.json() == PENDING
    refresh = client.post("/v1/auth/refresh", json={"refresh_token": "refresh-a"})
    assert refresh.status_code == 403
    assert refresh.json() == PENDING


def test_provider_disabled_account_is_reported_as_pending_deletion(setup):
    client, auth, _ = setup
    auth.disabled.add("student-a")
    exchange = client.post("/v1/auth/google", json={"credential": "student-a"})
    assert exchange.status_code == 403
    assert exchange.json() == PENDING
    refresh = client.post("/v1/auth/refresh", json={"refresh_token": "refresh-a"})
    assert refresh.status_code == 403
    assert refresh.json() == PENDING


def test_deletion_denial_survives_provider_revocation_outage(setup):
    from cst_accounts.domain import Unavailable

    client, auth, store = setup

    def failed_disable(uid):
        raise Unavailable()

    auth.disable = failed_disable
    headers = {"Authorization": "Bearer student-a"}
    result = client.post(
        "/v1/account/deletion", json={"confirmation": "DELETE"}, headers=headers
    )
    assert result.status_code == 202
    assert "student-a" in store.requests
    assert client.get("/v1/scores", headers=headers).status_code == 403


def _keep_tokens_valid(auth):
    """Model a lost 202: revocation failed, so the student's token still verifies."""
    from cst_accounts.domain import Unavailable

    def failed_disable(uid):
        raise Unavailable()

    auth.disable = failed_disable


def test_repeated_deletion_request_from_owner_returns_the_existing_request(setup):
    client, auth, store = setup
    _keep_tokens_valid(auth)
    headers = {"Authorization": "Bearer student-a"}
    body = {"confirmation": "DELETE"}
    first = client.post("/v1/account/deletion", json=body, headers=headers)
    assert first.status_code == 202
    second = client.post("/v1/account/deletion", json=body, headers=headers)
    assert second.status_code == 202
    assert second.json()["accepted"] is True
    assert second.json() == first.json()
    assert list(store.requests) == ["student-a"]
    # Every other route stays closed while deletion is pending.
    assert client.get("/v1/me", headers=headers).status_code == 403
    assert client.get("/v1/scores", headers=headers).status_code == 403
    assert (
        client.post("/v1/auth/refresh", json={"refresh_token": "refresh-a"}).status_code
        == 403
    )
    assert (
        client.post("/v1/account/deletion", json={}, headers=headers).status_code == 400
    )


def test_another_owner_cannot_touch_a_pending_deletion(setup):
    client, auth, store = setup
    _keep_tokens_valid(auth)
    a = {"Authorization": "Bearer student-a"}
    b = {"Authorization": "Bearer student-b"}
    body = {"confirmation": "DELETE"}
    assert client.post("/v1/account/deletion", json=body, headers=a).status_code == 202
    pending_a = store.requests["student-a"]
    # The owner comes only from the verified token, never from the body or query.
    assert (
        client.post(
            "/v1/account/deletion", json={**body, "uid": "student-a"}, headers=b
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/v1/account/deletion?uid=student-a",
            json=body,
            headers={"Authorization": "Bearer forged"},
        ).status_code
        == 401
    )
    assert "student-b" not in store.requests
    assert client.get("/v1/scores", headers=b).status_code == 200
    assert client.post("/v1/account/deletion", json=body, headers=b).status_code == 202
    assert store.requests["student-a"] is pending_a
    assert store.requests["student-b"].uid == "student-b"
    assert store.records["student-a"]


def test_score_projection_drops_extra_private_fields(setup):
    client, _, store = setup
    store.records["student-a"][0]["transcript"] = "private-transcript-marker"
    response = client.get("/v1/scores", headers={"Authorization": "Bearer student-a"})
    assert response.status_code == 200
    assert "private-transcript-marker" not in response.text
    assert set(response.json()["scores"][0]) == {"scenario_id", "overall", "categories"}


def test_deletion_worker_is_idempotent_and_removes_only_owner_scores():
    from cst_accounts.deletion import process_deletions

    auth, store = FakeAuth(), FakeStore()
    now = datetime.now(UTC)
    store.request_deletion("student-a", now)
    assert process_deletions(auth, store, now)["completed"] == 1
    assert "student-a" in auth.deleted
    assert "student-a" not in store.records
    assert "student-b" in store.records
    assert process_deletions(auth, store, now)["completed"] == 0


def test_deletion_worker_retries_failed_storage_without_deleting_identity():
    from cst_accounts.deletion import process_deletions

    auth, store = FakeAuth(), FakeStore()
    now = datetime.now(UTC)
    store.request_deletion("student-a", now)
    store.fail_erase = True
    assert process_deletions(auth, store, now)["failed"] == 1
    assert "student-a" in store.requests
    assert "student-a" not in auth.deleted
    store.fail_erase = False
    assert process_deletions(auth, store, now)["completed"] == 0
    from datetime import timedelta

    assert process_deletions(auth, store, now + timedelta(hours=1))["completed"] == 1


SYNTHETIC_TURN = "SYNTHETIC-TURN: I feel hopeless"


class TurnEchoingStore(FakeStore):
    """A storage failure whose message echoes session content (synthetic)."""

    def scores(self, uid):
        raise ValueError(SYNTHETIC_TURN)


def assert_content_free(*texts: str) -> None:
    for text in texts:
        assert "hopeless" not in text
        assert "SYNTHETIC-TURN" not in text
        assert "Traceback" not in text


def test_unhandled_error_returns_the_generic_envelope_and_logs_only_its_class(
    capsys, caplog
):
    caplog.set_level(logging.DEBUG)
    # raise_server_exceptions stays on: an exception that escaped to Starlette's
    # ServerErrorMiddleware would fail this test instead of returning a 500.
    with TestClient(create_app(FakeAuth(), TurnEchoingStore())) as client:
        response = client.get(
            "/v1/scores", headers={"Authorization": "Bearer student-a"}
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    captured = capsys.readouterr()
    assert_content_free(response.text, captured.out, captured.err, caplog.text)
    assert [json.loads(line) for line in captured.out.splitlines()] == [
        {
            "severity": "ERROR",
            "message": "unhandled_error",
            "event": "unhandled_error",
            "status_code": 500,
            "error_class": "ValueError",
            "error_code": "internal_error",
        }
    ]


@contextmanager
def served(app):
    """Run ``app`` on a real uvicorn server, configured like the Dockerfile."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    # log_config=None leaves uvicorn's loggers propagating to the root logger,
    # so caplog sees anything uvicorn would log, including tracebacks.
    config = uvicorn.Config(
        app, log_config=None, log_level="debug", access_log=False, lifespan="off"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]})
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            assert thread.is_alive() and time.monotonic() < deadline
            time.sleep(0.01)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(10)
        sock.close()


def test_unhandled_error_never_reaches_the_uvicorn_traceback_logger(capsys, caplog):
    caplog.set_level(logging.DEBUG)
    with served(create_app(FakeAuth(), TurnEchoingStore())) as url:
        response = httpx.get(
            f"{url}/v1/scores", headers={"Authorization": "Bearer student-a"}
        )

    assert response.status_code == 500
    captured = capsys.readouterr()
    assert_content_free(response.text, captured.out, captured.err, caplog.text)
    assert "Exception in ASGI application" not in caplog.text
    assert '"error_class": "ValueError"' in captured.out


class InputEchoingAuth(FakeAuth):
    """A provider failure whose message echoes the request body (synthetic)."""

    def exchange(self, credential):
        raise ValueError(f"provider rejected credential {credential!r}")


def test_a_failing_request_never_logs_or_echoes_its_body(capsys, caplog):
    caplog.set_level(logging.DEBUG)
    with served(create_app(InputEchoingAuth(), FakeStore())) as url:
        response = httpx.post(
            f"{url}/v1/auth/google", json={"credential": SYNTHETIC_TURN}
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}
    captured = capsys.readouterr()
    assert_content_free(response.text, captured.out, captured.err, caplog.text)
    assert "Exception in ASGI application" not in caplog.text
    assert [json.loads(line) for line in captured.out.splitlines()] == [
        {
            "severity": "ERROR",
            "message": "unhandled_error",
            "event": "unhandled_error",
            "status_code": 500,
            "error_class": "ValueError",
            "error_code": "internal_error",
        }
    ]


@pytest.mark.parametrize(
    ("fail_erase", "overdue", "expected"),
    [
        (False, False, ({"completed": 1, "failed": 0, "overdue": 0}, "INFO", 0)),
        (True, False, ({"completed": 0, "failed": 1, "overdue": 0}, "ERROR", 1)),
        (False, True, ({"completed": 1, "failed": 0, "overdue": 1}, "ERROR", 1)),
    ],
)
def test_deletion_sweep_logs_the_counts_the_alert_metrics_filter_on(
    capsys, fail_erase, overdue, expected
):
    from datetime import timedelta

    from cst_accounts.main import run_sweep

    counts, severity, exit_code = expected
    auth, store = FakeAuth(), FakeStore()
    now = datetime.now(UTC)
    store.request_deletion("student-a", now - timedelta(days=31 if overdue else 0))
    store.fail_erase = fail_erase

    assert run_sweep(auth, store, now) == exit_code

    out = capsys.readouterr().out
    assert "student-a" not in out
    # infra/accounts/main.tf metrics filter on jsonPayload.event, .failed,
    # .overdue and severity, so these must stay top-level.
    assert [json.loads(line) for line in out.splitlines()] == [
        {
            "severity": severity,
            "message": "account_deletion_sweep",
            "event": "account_deletion_sweep",
            **counts,
        }
    ]


def test_a_crashing_deletion_sweep_logs_only_its_class_and_fails_the_job(capsys):
    from cst_accounts.main import run_sweep

    class ProviderLeakingStore(FakeStore):
        def due_deletions(self, now):
            raise RuntimeError("provider said: student-a@example.com")

    assert run_sweep(FakeAuth(), ProviderLeakingStore(), datetime.now(UTC)) == 1

    captured = capsys.readouterr()
    assert "example.com" not in captured.out + captured.err
    assert "Traceback" not in captured.out + captured.err
    # A different event, so the missing-sweep alert does not count a crash as a
    # completed sweep, and ERROR severity, which the failure metric counts.
    assert json.loads(captured.out) == {
        "severity": "ERROR",
        "message": "account_deletion_sweep_crashed",
        "event": "account_deletion_sweep_crashed",
        "error_class": "RuntimeError",
        "error_code": "sweep_crashed",
    }
