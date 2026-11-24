"""Production factory and deletion-job entrypoint using workload identity."""

from datetime import UTC, datetime

import firebase_admin
from fastapi import FastAPI
from google.cloud import firestore
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from .api import create_app
from .content_free_log import log_error, log_event
from .deletion import process_deletions
from .domain import AccountStore, IdentityProvider
from .firebase import FirebaseIdentity
from .store import FirestoreAccounts


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CST_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )
    project_id: str
    identity_api_key: SecretStr = Field(min_length=1)
    request_uri: str
    allowed_origins: tuple[str, ...] = ()


def dependencies(settings: Settings) -> tuple[FirebaseIdentity, FirestoreAccounts]:
    try:
        app = firebase_admin.get_app("cst-accounts")
    except ValueError:
        app = firebase_admin.initialize_app(
            options={"projectId": settings.project_id}, name="cst-accounts"
        )
    if app.project_id != settings.project_id:
        raise ValueError(
            "The configured Firebase application belongs to another project."
        )
    return FirebaseIdentity(
        app, settings.identity_api_key.get_secret_value(), settings.request_uri
    ), FirestoreAccounts(firestore.Client(project=settings.project_id))


def app_factory() -> FastAPI:
    settings = Settings()
    auth, store = dependencies(settings)
    return create_app(auth, store, settings.allowed_origins)


def run_sweep(auth: IdentityProvider, store: AccountStore, now: datetime) -> int:
    """Run one deletion sweep, log its counts and return the job's exit code."""
    try:
        result = process_deletions(auth, store, now)
    except Exception as exc:  # noqa: BLE001 - a traceback could carry a UID or email
        log_error("account_deletion_sweep_crashed", exc, code="sweep_crashed")
        return 1
    unhealthy = bool(result["failed"] or result["overdue"])
    # Counts only. infra/accounts/main.tf metrics filter on these keys.
    log_event(
        "account_deletion_sweep",
        severity="ERROR" if unhealthy else "INFO",
        completed=result["completed"],
        failed=result["failed"],
        overdue=result["overdue"],
    )
    return 1 if unhealthy else 0


if __name__ == "__main__":
    auth, store = dependencies(Settings())
    raise SystemExit(run_sweep(auth, store, datetime.now(UTC)))
