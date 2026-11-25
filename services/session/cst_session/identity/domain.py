"""Identity and approval contracts, copied from ``cst_accounts.domain`` (T2).

Only what the session guard needs: the exceptions, the access states, the
verified student and two narrow ports. ``tests/test_identity_copy.py`` fails
if a copied class drifts from its accounts source.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class Rejected(Exception):
    """Invalid, expired, revoked, or non-Google credential."""


class DeletionPending(Exception):
    """The account has a pending deletion request, so it cannot sign in."""


class Unavailable(Exception):
    """An external dependency failed; access must fail closed."""


class AccessNotApproved(Exception):
    """The account's access record is not approved (POLICY ACC-4, ACC-7)."""


class AccessState(StrEnum):
    """Owner approval state of an account. A revoked account is ``denied``."""

    MISSING = "missing"
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


@dataclass(frozen=True)
class Student:
    uid: str


class TokenVerifier(Protocol):
    def verify(self, token: str) -> Student: ...


class AccessReader(Protocol):
    def pending(self, uid: str) -> bool: ...
    def access_state(self, uid: str) -> AccessState: ...
