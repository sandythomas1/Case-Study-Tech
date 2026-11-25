"""Point reads of the access record and deletion marker, copied from accounts (T2).

``_stored_state``, ``storage_operation``, ``pending`` and ``access_state`` are
verbatim copies of ``cst_accounts.store``. The session service only reads:
it never writes Firestore.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import firestore

from .domain import AccessState, Unavailable

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


class FirestoreAccess:
    """Reads only. Every protected request reads again: there is no cache."""

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
