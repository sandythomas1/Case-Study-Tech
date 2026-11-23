"""Retryable cleanup invoked by a private, scheduled Cloud Run Job."""

from contextlib import suppress
from datetime import datetime

from .domain import AccountStore, IdentityProvider, Unavailable


def process_deletions(
    auth: IdentityProvider, store: AccountStore, now: datetime
) -> dict[str, int]:
    """Delete queued owners only; keep failures for the next run."""
    completed, failed, overdue = 0, 0, 0
    for request in store.due_deletions(now):
        overdue += int(now >= request.deadline)
        try:
            auth.disable(request.uid)
            store.erase_scores(request.uid)
            auth.delete(request.uid)
            store.complete_deletion(request.uid, now)
            completed += 1
        except Unavailable:
            failed += 1
            # Move failed owners out of this sweep's first page so they cannot
            # permanently starve newer requests. Preserve the original deadline.
            with suppress(Unavailable):
                store.retry_deletion(request.uid, now)
    return {"completed": completed, "failed": failed, "overdue": overdue}
