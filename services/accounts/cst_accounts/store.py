"""Owner-scoped Firestore reads, access records and durable deletion requests."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta

from google.api_core.exceptions import AlreadyExists, GoogleAPICallError
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from .domain import (
    AccessDenied,
    AccessState,
    DeletionPending,
    DeletionRequest,
    Profile,
    Unavailable,
)

# Server-only collection (infra/firestore.rules denies every client read and
# write). One document per account, keyed by the verified UID.
ACCESS = "access"
_STORED_STATES = {AccessState.PENDING, AccessState.APPROVED, AccessState.DENIED}


def _stored_state(data: dict[str, object] | None) -> AccessState:
    """The state of an existing access record. Anything malformed fails closed."""
    state = (data or {}).get("state")
    if isinstance(state, str) and state in _STORED_STATES:
        return AccessState(state)
    # Never guess: an unreadable record is an outage, not an approval.
    raise Unavailable()


@contextmanager
def storage_operation() -> Iterator[None]:
    try:
        yield
    except (GoogleAPICallError, OSError):
        raise Unavailable() from None
    except ValueError as error:
        # A transaction that exhausts its retries under contention is wrapped
        # in ValueError by the client library. It is an outage, not a 500.
        if isinstance(error.__cause__, GoogleAPICallError):
            raise Unavailable() from None
        raise


class FirestoreAccounts:
    def __init__(self, client: firestore.Client) -> None:
        self.client = client

    def pending(self, uid: str) -> bool:
        with storage_operation():
            return (
                self.client.collection("account_deletions").document(uid).get().exists
            )

    def access_state(self, uid: str) -> AccessState:
        """Read on every protected request: there is no approval cache (ACC-7)."""
        with storage_operation():
            snapshot = self.client.collection(ACCESS).document(uid).get()
        if not snapshot.exists:
            return AccessState.MISSING
        return _stored_state(snapshot.to_dict())

    def request_access(self, profile: Profile, now: datetime) -> AccessState:
        """Create the account's one access request, or return its current state.

        The create shares a transaction with a read of the deletion marker, so a
        deletion confirmed in parallel can't be outlived by a new record (DAT-3).
        The transaction never reads the access record itself: racing requests
        would each lock the missing document and deadlock. Instead the create
        fails for every racer but one, and they report what the winner wrote.
        A denied account creates nothing.
        """
        state = self.access_state(profile.uid)
        if state is AccessState.MISSING:
            state = self._create_request(profile, now)
        if state is AccessState.DENIED:
            raise AccessDenied()
        return state

    def _create_request(self, profile: Profile, now: datetime) -> AccessState:
        ref = self.client.collection(ACCESS).document(profile.uid)
        marker = self.client.collection("account_deletions").document(profile.uid)

        @firestore.transactional
        def create_once(transaction: firestore.Transaction) -> AccessState:
            if marker.get(transaction=transaction).exists:
                raise DeletionPending()
            # Exactly the fields POLICY DAT-2 allows; nothing from the request.
            transaction.create(
                ref,
                {
                    "display_name": profile.display_name,
                    "email": profile.email,
                    "state": AccessState.PENDING.value,
                    "requested_at": now,
                    "decided_at": None,
                    "version": 1,
                },
            )
            return AccessState.PENDING

        with storage_operation():
            try:
                return create_once(self.client.transaction())
            except AlreadyExists:
                pass  # A racing request created the record first.
            except ValueError as error:
                # Retries ran out under contention. Read what the winner wrote.
                if not isinstance(error.__cause__, GoogleAPICallError):
                    raise
        state = self.access_state(profile.uid)
        if state is AccessState.MISSING:
            raise Unavailable()  # Nothing was written: an outage, never a guess.
        return state

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

    def erase_student_data(self, uid: str) -> None:
        """Delete everything the server keeps for one owner (POLICY DAT-3).

        That is the scores, the student document and the access record, which
        holds the name and email. A new per-owner collection must be added here.
        """
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
            self.client.collection(ACCESS).document(uid).delete()

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
