"""Provider-neutral authentication, access, ownership and deletion contracts."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class Rejected(Exception):
    """Invalid, expired, revoked, or non-Google credential."""


class DeletionPending(Exception):
    """The account has a pending deletion request, so it cannot sign in."""


class Unavailable(Exception):
    """An external dependency failed; access must fail closed."""


class AccessNotApproved(Exception):
    """The account's access record is not approved (POLICY ACC-4, ACC-7)."""


class ProfileUnusable(Exception):
    """The verified token lacks a verified email or carries an unusable name."""


class AccessDenied(Exception):
    """A denied or revoked account cannot request access again (POLICY ACC-6)."""


class AccessState(StrEnum):
    """Owner approval state of an account. A revoked account is ``denied``."""

    MISSING = "missing"
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


@dataclass(frozen=True)
class Student:
    uid: str


@dataclass(frozen=True)
class Profile:
    """Verified identity claims an access request records (POLICY DAT-2).

    The name and email never appear in a repr, so a stray log or traceback
    cannot carry them (POLICY DAT-7).
    """

    uid: str
    display_name: str = field(repr=False)
    email: str = field(repr=False)


class Tokens(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id_token: str = Field(min_length=1)
    refresh_token: str = Field(min_length=1)
    expires_in: int = Field(gt=0, le=3600)


class Score(BaseModel):
    """Allowlisted score projection, never narrative content."""

    model_config = ConfigDict(extra="ignore", frozen=True)
    scenario_id: str
    overall: float = Field(ge=1, le=5, allow_inf_nan=False)
    categories: list[float] = Field(min_length=6, max_length=6)


@dataclass(frozen=True)
class DeletionRequest:
    uid: str
    requested_at: datetime

    @property
    def deadline(self) -> datetime:
        return self.requested_at + timedelta(days=30)


class IdentityProvider(Protocol):
    def verify(self, token: str) -> Student: ...
    def profile(self, token: str) -> Profile: ...
    def exchange(self, credential: str) -> Tokens: ...
    def refresh(self, refresh_token: str) -> Tokens: ...
    def disable(self, uid: str) -> None: ...
    def delete(self, uid: str) -> None: ...


class AccountStore(Protocol):
    def pending(self, uid: str) -> bool: ...
    def access_state(self, uid: str) -> AccessState: ...
    def request_access(self, profile: Profile, now: datetime) -> AccessState: ...
    def scores(self, uid: str) -> list[dict[str, object]]: ...
    def request_deletion(self, uid: str, now: datetime) -> DeletionRequest: ...
    def due_deletions(self, now: datetime) -> list[DeletionRequest]: ...
    def erase_student_data(self, uid: str) -> None: ...
    def complete_deletion(self, uid: str, now: datetime) -> None: ...
    def retry_deletion(self, uid: str, now: datetime) -> None: ...
