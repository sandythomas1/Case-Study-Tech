"""Real Firestore adapter integration. Never connects to a live project."""

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

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
    # A fresh uid, so a rerun against a long-lived emulator finds no old marker.
    uid = f"delete-test-{uuid4().hex}"
    now = datetime.now(UTC)
    first = store.request_deletion(uid, now)
    second = store.request_deletion(uid, now + timedelta(days=1))
    assert second.requested_at == first.requested_at
    assert second.deadline == now + timedelta(days=30)
    assert store.pending(uid)


def test_erasing_scores_does_not_touch_another_student(store):
    for uid in ["delete-test-a", "delete-test-b"]:
        store.client.collection("students").document(uid).collection("scores").document(
            "one"
        ).set({"overall": 4})
    store.erase_student_data("delete-test-a")
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
        # Synthetic pre-approved test accounts (POLICY ACC-9).
        store.client.collection("access").document(uid).set({"state": "approved"})
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


# Owner approval gate (#72) against the real Firestore adapter.


def synthetic_profile(prefix):
    from uuid import uuid4

    from cst_accounts.domain import Profile

    uid = f"{prefix}-{uuid4().hex[:12]}"
    return Profile(
        uid=uid, display_name="Synthetic Student", email=f"{uid}@test.invalid"
    )


def test_a_first_access_request_creates_one_pending_record(store):
    from cst_accounts.domain import AccessState

    profile = synthetic_profile("access-first")
    now = datetime.now(UTC)
    assert store.access_state(profile.uid) is AccessState.MISSING

    assert store.request_access(profile, now) is AccessState.PENDING

    record = store.client.collection("access").document(profile.uid).get().to_dict()
    assert record == {
        "display_name": "Synthetic Student",
        "email": f"{profile.uid}@test.invalid",
        "state": "pending",
        "requested_at": record["requested_at"],
        "decided_at": None,
        "version": 1,
    }
    assert abs(record["requested_at"] - now) < timedelta(seconds=1)
    assert store.access_state(profile.uid) is AccessState.PENDING


def test_a_repeated_access_request_keeps_the_original_record(store):
    from cst_accounts.domain import AccessState

    profile = synthetic_profile("access-repeat")
    first = datetime.now(UTC)
    store.request_access(profile, first)
    assert (
        store.request_access(profile, first + timedelta(days=1)) is AccessState.PENDING
    )
    record = store.client.collection("access").document(profile.uid).get().to_dict()
    assert abs(record["requested_at"] - first) < timedelta(seconds=1)
    assert record["version"] == 1


def test_concurrent_access_requests_leave_exactly_one_record(store):
    from concurrent.futures import ThreadPoolExecutor

    from cst_accounts.domain import AccessState

    # A fresh uid every run, so the race really happens on a long-lived emulator.
    profile = synthetic_profile(f"access-race-{uuid4().hex}")
    now = datetime.now(UTC)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(lambda _: store.request_access(profile, now), range(16))
        )
    assert set(results) == {AccessState.PENDING}
    matching = [
        doc.id
        for doc in store.client.collection("access").stream()
        if doc.id == profile.uid
    ]
    assert matching == [profile.uid]
    record = store.client.collection("access").document(profile.uid).get().to_dict()
    assert record["version"] == 1


def test_a_denied_account_request_is_rejected_and_changes_nothing(store):
    from cst_accounts.domain import AccessDenied, AccessState

    profile = synthetic_profile("access-denied")
    ref = store.client.collection("access").document(profile.uid)
    ref.set({"state": "denied", "version": 3})

    with pytest.raises(AccessDenied):
        store.request_access(profile, datetime.now(UTC))

    assert ref.get().to_dict() == {"state": "denied", "version": 3}
    assert store.access_state(profile.uid) is AccessState.DENIED


@pytest.mark.parametrize(
    "record",
    [{}, {"state": "APPROVED"}, {"state": "revoked"}, {"state": None}, {"state": 1}],
)
def test_a_malformed_access_record_fails_closed(store, record):
    from cst_accounts.domain import Unavailable

    profile = synthetic_profile("access-malformed")
    store.client.collection("access").document(profile.uid).set(record)
    with pytest.raises(Unavailable):
        store.access_state(profile.uid)
    with pytest.raises(Unavailable):
        store.request_access(profile, datetime.now(UTC))


def test_deletion_cleanup_removes_the_access_record_with_the_scores(store):
    from cst_accounts.domain import AccessState

    gone, kept = synthetic_profile("erase-gone"), synthetic_profile("erase-kept")
    for profile in (gone, kept):
        store.request_access(profile, datetime.now(UTC))
        store.client.collection("students").document(profile.uid).collection(
            "scores"
        ).document("one").set({"scenario_id": "routine", "overall": 3})

    store.erase_student_data(gone.uid)

    assert not store.client.collection("access").document(gone.uid).get().exists
    assert store.scores(gone.uid) == []
    assert store.access_state(gone.uid) is AccessState.MISSING
    assert store.access_state(kept.uid) is AccessState.PENDING
    assert len(store.scores(kept.uid)) == 1


def test_the_http_guard_with_the_real_store_follows_the_access_record(store):
    from unittest.mock import Mock, patch

    from fastapi.testclient import TestClient

    from cst_accounts.api import create_app
    from cst_accounts.firebase import FirebaseIdentity

    profile = synthetic_profile("http-gate")
    store.client.collection("students").document(profile.uid).collection(
        "scores"
    ).document("one").set(
        {"scenario_id": "routine", "overall": 4, "categories": [4] * 6}
    )
    provider = FirebaseIdentity(Mock(), "test-project-key", "https://example.invalid")
    claims = {
        "uid": profile.uid,
        "firebase": {"sign_in_provider": "google.com"},
        "name": profile.display_name,
        "email": profile.email,
        "email_verified": True,
    }
    headers = {"Authorization": "Bearer verified-by-sdk-boundary"}
    with (
        patch("cst_accounts.firebase.auth.verify_id_token", return_value=claims),
        TestClient(create_app(provider, store)) as client,
    ):
        assert client.get("/v1/scores", headers=headers).status_code == 403
        assert client.post("/v1/access/request", headers=headers).json() == {
            "state": "pending"
        }
        assert client.get("/v1/scores", headers=headers).status_code == 403
        ref = store.client.collection("access").document(profile.uid)
        ref.update({"state": "approved", "decided_at": datetime.now(UTC), "version": 2})
        assert client.get("/v1/scores", headers=headers).status_code == 200
        ref.update({"state": "denied", "version": 3})
        assert client.get("/v1/scores", headers=headers).status_code == 403
        assert client.get("/v1/access", headers=headers).json() == {"state": "denied"}


def test_a_deletion_marker_blocks_the_create_inside_the_transaction(store):
    # DAT-3: the API's eligibility check ran first; the marker landed after it.
    from cst_accounts.domain import DeletionPending

    profile = synthetic_profile("access-deleting")
    store.request_deletion(profile.uid, datetime.now(UTC))
    with pytest.raises(DeletionPending):
        store.request_access(profile, datetime.now(UTC))
    assert not store.client.collection("access").document(profile.uid).get().exists
