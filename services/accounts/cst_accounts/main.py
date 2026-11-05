"""Production factory and deletion-job entrypoint using workload identity."""

import json
from datetime import UTC, datetime

import firebase_admin
from fastapi import FastAPI
from google.cloud import firestore
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from .api import create_app
from .deletion import process_deletions
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


if __name__ == "__main__":
    auth, store = dependencies(Settings())
    result = process_deletions(auth, store, datetime.now(UTC))
    # Counts only. Never log UIDs, credentials or provider response payloads.
    print(json.dumps({"event": "account_deletion_sweep", **result}))
    raise SystemExit(1 if result["failed"] or result["overdue"] else 0)
