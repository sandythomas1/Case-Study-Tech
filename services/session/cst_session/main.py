"""Production factory for the session service, using workload identity (FR-3, FR-5).

``app_factory`` checks every setting before it creates a cloud client: a
missing or malformed state-signing key, or a persona location outside the
closed host map (``global`` included), stops startup with a fixed message.
"""

import logging

import firebase_admin
from fastapi import FastAPI
from google.cloud import firestore
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from .api import checked_origins, create_app
from .grading import UnavailableGrader
from .identity.firebase import FirebaseIdentity
from .identity.store import FirestoreAccess
from .lifecycle import Sessions, SystemClock
from .persona.agent_platform import AdcTokenSource, AgentPlatformPersona
from .scenarios import load_catalogue
from .scenarios.prompts import load_prompts
from .state import StateCodec, decode_signing_key

FIREBASE_APP_NAME = "cst-session"
# httpx logs each request URL at INFO. The URL names the project and model,
# and a client log line is not written through the content-free helper.
QUIET_LOGGERS = ("httpx", "httpcore")


class Settings(BaseSettings):
    # No .env file: the signing key comes only from the runtime environment,
    # which Cloud Run fills from Secret Manager.
    model_config = SettingsConfigDict(
        env_prefix="CST_", extra="ignore", hide_input_in_errors=True
    )
    project_id: str
    persona_model: str
    agent_platform_location: str
    state_signing_key: SecretStr
    allowed_origins: tuple[str, ...] = ()


def quiet_client_loggers() -> None:
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def sessions(settings: Settings) -> Sessions:
    """The lifecycle with its production adapters. Opens no connection."""
    codec = StateCodec(
        decode_signing_key(settings.state_signing_key.get_secret_value())
    )
    persona = AgentPlatformPersona(
        project=settings.project_id,
        location=settings.agent_platform_location,
        model=settings.persona_model,
        tokens=AdcTokenSource(),
    )
    return Sessions(
        catalogue=load_catalogue(),
        prompts=load_prompts(),
        codec=codec,
        persona=persona,
        grader=UnavailableGrader(),
        clock=SystemClock(),
    )


def identity(settings: Settings) -> tuple[FirebaseIdentity, FirestoreAccess]:
    try:
        app = firebase_admin.get_app(FIREBASE_APP_NAME)
    except ValueError:
        app = firebase_admin.initialize_app(
            options={"projectId": settings.project_id}, name=FIREBASE_APP_NAME
        )
    if app.project_id != settings.project_id:
        raise ValueError(
            "The configured Firebase application belongs to another project."
        )
    return FirebaseIdentity(app), FirestoreAccess(
        firestore.Client(project=settings.project_id)
    )


def app_factory() -> FastAPI:
    settings = Settings()
    # Everything that can refuse a setting runs before any cloud client exists.
    lifecycle = sessions(settings)
    origins = checked_origins(settings.allowed_origins)
    quiet_client_loggers()
    auth, store = identity(settings)
    return create_app(auth, store, lifecycle, origins)
