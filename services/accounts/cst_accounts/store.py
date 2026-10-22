"""Owner-scoped Firestore reads and durable deletion requests."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from .domain import DeletionRequest, Unavailable


@contextmanager
def storage_operation() -> Iterator[None]:
    try:
        yield
    except (GoogleAPICallError, OSError):
        raise Unavailable() from None


class FirestoreAccounts:
    def __init__(self, client: firestore.Client) -> None:
        self.client = client

    def pending(self, uid: str) -> bool:
        with storage_operation():
            return (
                self.client.collection("account_deletions").document(uid).get().exists
            )

    def scores(self, uid: str) -> list[dict[str, object]]:
        with storage_operation():
            # There is deliberately no caller-supplied owner or collection path.
            return [
                doc.to_dict()
                for doc in self.client.collection("students")
                .document(uid)
                .collection("scores")
                .limit(100)
                .stream()
            ]

    def request_deletion(self, uid: str, now: datetime) -> DeletionRequest:
        ref = self.client.collection("account_deletions").document(uid)

        @firestore.transactional
        def create_once(transaction: firestore.Transaction) -> DeletionRequest:
            existing = ref.get(transaction=transaction)
            if existing.exists:
                data = existing.to_dict() or {}
                if not isinstance(data.get("requested_at"), datetime):
                    raise Unavailable()
                return DeletionRequest(uid, data["requested_at"])
            transaction.create(
                ref,
                {
                    "requested_at": now,
                    "deadline": now + timedelta(days=30),
                    "state": "pending",
                    "next_attempt_at": now,
                },
            )
            return DeletionRequest(uid, now)

        with storage_operation():
            return create_once(self.client.transaction())

    def due_deletions(self, now: datetime) -> list[DeletionRequest]:
        with storage_operation():
            # Purge completed denial markers only after all old ID tokens expire.
            expired = (
                self.client.collection("account_deletions")
                .where(filter=FieldFilter("purge_after", "<=", now))
                .limit(100)
                .stream()
            )
            for doc in expired:
                doc.reference.delete()
            pending = (
                self.client.collection("account_deletions")
                .where(filter=FieldFilter("next_attempt_at", "<=", now))
                .order_by("next_attempt_at")
                .limit(100)
                .stream()
            )
            return [
                DeletionRequest(doc.id, (doc.to_dict() or {})["requested_at"])
                for doc in pending
            ]

    def erase_scores(self, uid: str) -> None:
        with storage_operation():
            scores = (
                self.client.collection("students").document(uid).collection("scores")
            )
            while docs := list(scores.limit(400).stream()):
                batch = self.client.batch()
                for doc in docs:
                    batch.delete(doc.reference)
                batch.commit()
            self.client.collection("students").document(uid).delete()

    def complete_deletion(self, uid: str, now: datetime) -> None:
        with storage_operation():
            self.client.collection("account_deletions").document(uid).update(
                {
                    "state": "completed",
                    "purge_after": now + timedelta(hours=2),
                    "next_attempt_at": firestore.DELETE_FIELD,
                }
            )

    def retry_deletion(self, uid: str, now: datetime) -> None:
        with storage_operation():
            self.client.collection("account_deletions").document(uid).update(
                {"next_attempt_at": now + timedelta(hours=1)}
            )
