"""Account boundaries exercised through the real HTTP router."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from cst_accounts.api import create_app


class FakeAuth:
    def __init__(self):
        self.disabled = set()
        self.deleted = set()
        self.unavailable = False

    def verify(self, token):
        from cst_accounts.domain import Rejected, Student, Unavailable

        if self.unavailable:
            raise Unavailable()
        if token not in {"student-a", "student-b"} or token in self.disabled:
            raise Rejected()
        return Student(uid=token)

    def exchange(self, credential):
        from cst_accounts.domain import Tokens

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
        self.requests = {}
        self.erased = []
        self.fail_erase = False
        self.retry_after = {}

    def pending(self, uid):
        return uid in self.requests

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

    def erase_scores(self, uid):
        from cst_accounts.domain import Unavailable

        if self.fail_erase:
            raise Unavailable()
        self.records.pop(uid, None)
        self.erased.append(uid)

    def complete_deletion(self, uid, now):
        self.requests.pop(uid, None)


@pytest.fixture
def setup():
    auth, store = FakeAuth(), FakeStore()
    with TestClient(create_app(auth, store)) as client:
        yield client, auth, store


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


def test_pending_deletion_blocks_refresh_and_new_exchange(setup):
    client, _, store = setup
    store.request_deletion("student-a", datetime.now(UTC))
    assert (
        client.post("/v1/auth/google", json={"credential": "student-a"}).status_code
        == 403
    )
    assert (
        client.post("/v1/auth/refresh", json={"refresh_token": "refresh-a"}).status_code
        == 403
    )


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
