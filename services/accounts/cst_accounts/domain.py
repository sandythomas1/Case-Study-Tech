"""Provider-neutral authentication, ownership and deletion contracts."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class Rejected(Exception):
    """Invalid, expired, revoked, or non-Google credential."""


class Unavailable(Exception):
    """An external dependency failed; access must fail closed."""


@dataclass(frozen=True)
class Student:
    uid: str


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
    def exchange(self, credential: str) -> Tokens: ...
    def refresh(self, refresh_token: str) -> Tokens: ...
    def disable(self, uid: str) -> None: ...
    def delete(self, uid: str) -> None: ...


class AccountStore(Protocol):
    def pending(self, uid: str) -> bool: ...
    def scores(self, uid: str) -> list[dict[str, object]]: ...
    def request_deletion(self, uid: str, now: datetime) -> DeletionRequest: ...
    def due_deletions(self, now: datetime) -> list[DeletionRequest]: ...
    def erase_scores(self, uid: str) -> None: ...
    def complete_deletion(self, uid: str, now: datetime) -> None: ...
    def retry_deletion(self, uid: str, now: datetime) -> None: ...
