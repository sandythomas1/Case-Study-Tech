"""Real Firestore adapter integration. Never connects to a live project."""

import os
from datetime import UTC, datetime, timedelta

import pytest
from google.auth.credentials import AnonymousCredentials
from google.cloud import firestore

from cst_accounts.store import FirestoreAccounts

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"), reason="Firestore emulator required"
)


@pytest.fixture
def store():
    assert os.environ["FIRESTORE_EMULATOR_HOST"] in {"127.0.0.1:8085", "localhost:8085"}
    client = firestore.Client(
        project="demo-casestudy-tech", credentials=AnonymousCredentials()
    )
    yield FirestoreAccounts(client)
    client.close()


def test_request_is_idempotent_and_keeps_original_deadline(store):
    now = datetime.now(UTC)
    first = store.request_deletion("delete-test-a", now)
    second = store.request_deletion("delete-test-a", now + timedelta(days=1))
    assert second.requested_at == first.requested_at
    assert second.deadline == now + timedelta(days=30)
    assert store.pending("delete-test-a")


def test_erasing_scores_does_not_touch_another_student(store):
    for uid in ["delete-test-a", "delete-test-b"]:
        store.client.collection("students").document(uid).collection("scores").document(
            "one"
        ).set({"overall": 4})
    store.erase_scores("delete-test-a")
    assert store.scores("delete-test-a") == []
    assert store.scores("delete-test-b") == [{"overall": 4}]


def test_completed_denial_marker_survives_token_lifetime_then_is_purged(store):
    now = datetime.now(UTC)
    store.request_deletion("delete-test-completed", now)
    store.complete_deletion("delete-test-completed", now)
    assert store.pending("delete-test-completed")
    assert all(
        item.uid != "delete-test-completed"
        for item in store.due_deletions(now + timedelta(hours=1))
    )
    assert store.pending("delete-test-completed")
    store.due_deletions(now + timedelta(hours=3))
    assert not store.pending("delete-test-completed")


def test_retry_moves_failed_request_out_of_current_page_without_changing_deadline(
    store,
):
    now = datetime.now(UTC)
    original = store.request_deletion("retry-test", now)
    store.retry_deletion("retry-test", now)
    assert all(item.uid != "retry-test" for item in store.due_deletions(now))
    retried = [
        item
        for item in store.due_deletions(now + timedelta(hours=1))
        if item.uid == "retry-test"
    ]
    assert len(retried) == 1
    assert retried[0].deadline == original.deadline


def test_http_authorization_with_real_firestore_store_blocks_cross_owner_access(store):
    from unittest.mock import Mock, patch

    from fastapi.testclient import TestClient

    from cst_accounts.api import create_app
    from cst_accounts.firebase import FirebaseIdentity

    for uid, scenario in [("http-a", "routine"), ("http-b", "resistant")]:
        store.client.collection("students").document(uid).collection("scores").document(
            "one"
        ).set({"scenario_id": scenario, "overall": 4, "categories": [4] * 6})
    provider = FirebaseIdentity(Mock(), "test-project-key", "https://example.invalid")
    with (
        patch(
            "cst_accounts.firebase.auth.verify_id_token",
            return_value={
                "uid": "http-a",
                "firebase": {"sign_in_provider": "google.com"},
            },
        ),
        TestClient(create_app(provider, store)) as client,
    ):
        headers = {"Authorization": "Bearer verified-by-sdk-boundary"}
        result = client.get("/v1/scores", headers=headers)
        assert result.status_code == 200
        assert result.json()["scores"] == [
            {"scenario_id": "routine", "overall": 4, "categories": [4] * 6}
        ]
        assert (
            client.get("/v1/scores?student_id=http-b", headers=headers).status_code
            == 400
        )
        assert (
            client.get("/v1/students/http-b/scores", headers=headers).status_code == 404
        )
