"""Startup refuses a missing or bad key and any persona location but ``us`` (T4, T8).

Every refusal happens before a Firebase app or Firestore client is created,
so these tests never reach a cloud API.
"""

import base64
import logging
from typing import Any

import pytest
from pydantic import ValidationError

from cst_session import main
from cst_session.persona.agent_platform import PersonaConfigError
from cst_session.state import SigningKeyError

KEY_TEXT = base64.urlsafe_b64encode(bytes(range(32))).rstrip(b"=").decode()
SECRET_SENTINEL = "c2VjcmV0LXNlbnRpbmVsLXZhbHVl"
ENV = {
    "CST_PROJECT_ID": "cst-synthetic-01",
    "CST_PERSONA_MODEL": "gemini-3.8-flash",
    "CST_AGENT_PLATFORM_LOCATION": "us",
    "CST_STATE_SIGNING_KEY": KEY_TEXT,
    "CST_ALLOWED_ORIGINS": '["https://app.example.test"]',
}


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    for name in ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("CST_VERTEX_LOCATION", raising=False)
    return dict(ENV)


@pytest.fixture
def no_cloud(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Records any attempt to create a cloud client, and fails it."""
    created: list[str] = []

    def refuse(name: str) -> Any:
        def create(*_: Any, **__: Any) -> Any:
            created.append(name)
            raise AssertionError(f"{name} created during a refused startup")

        return create

    monkeypatch.setattr(main, "identity", refuse("identity"))
    return created


def start(monkeypatch: pytest.MonkeyPatch, values: dict[str, str]) -> Any:
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    return main.app_factory()


@pytest.mark.parametrize(
    "key", [None, "", "short", KEY_TEXT + "AA", KEY_TEXT + "=", SECRET_SENTINEL]
)
def test_t8_startup_fails_without_key(
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, str],
    no_cloud: list[str],
    key: str | None,
) -> None:
    if key is None:
        del env["CST_STATE_SIGNING_KEY"]
    else:
        env["CST_STATE_SIGNING_KEY"] = key
    with pytest.raises((SigningKeyError, ValidationError)) as caught:
        start(monkeypatch, env)
    if key:
        assert key not in str(caught.value)
    assert no_cloud == []


@pytest.mark.parametrize(
    "location", [None, "", "global", "us-central1", "eu", "GLOBAL"]
)
def test_t4_startup_fails_on_global_or_missing_location(
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, str],
    no_cloud: list[str],
    location: str | None,
) -> None:
    if location is None:
        del env["CST_AGENT_PLATFORM_LOCATION"]
    else:
        env["CST_AGENT_PLATFORM_LOCATION"] = location
    with pytest.raises((PersonaConfigError, ValidationError)):
        start(monkeypatch, env)
    assert no_cloud == []


def test_t4_the_old_vertex_variable_is_not_read(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], no_cloud: list[str]
) -> None:
    del env["CST_AGENT_PLATFORM_LOCATION"]
    monkeypatch.setenv("CST_VERTEX_LOCATION", "us")
    with pytest.raises(ValidationError):
        start(monkeypatch, env)


@pytest.mark.parametrize(
    ("name", "value"),
    [("CST_PERSONA_MODEL", "palm-2"), ("CST_PROJECT_ID", "Bad_Project")],
)
def test_startup_fails_on_a_bad_model_or_project(
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, str],
    no_cloud: list[str],
    name: str,
    value: str,
) -> None:
    env[name] = value
    with pytest.raises(PersonaConfigError):
        start(monkeypatch, env)
    assert no_cloud == []


@pytest.mark.parametrize("origins", ['["*"]', '["null"]'])
def test_startup_fails_on_a_wildcard_origin(
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, str],
    no_cloud: list[str],
    origins: str,
) -> None:
    env["CST_ALLOWED_ORIGINS"] = origins
    with pytest.raises(ValueError, match="CST_ALLOWED_ORIGINS"):
        start(monkeypatch, env)
    assert no_cloud == []


def test_valid_settings_build_the_app_with_the_guard(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str]
) -> None:
    from tests.api_fakes import FakeAuth, FakeStore

    monkeypatch.setattr(main, "identity", lambda _: (FakeAuth(), FakeStore()))
    for name in main.QUIET_LOGGERS:
        logger = logging.getLogger(name)
        monkeypatch.setattr(logger, "level", logger.level)
    app = start(monkeypatch, env)
    assert app.state.approval_guard is not None
    assert app.openapi_url is None and app.docs_url is None
    for name in main.QUIET_LOGGERS:
        assert logging.getLogger(name).level == logging.WARNING


def test_settings_never_show_the_key(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str]
) -> None:
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    settings = main.Settings()
    assert KEY_TEXT not in repr(settings) and KEY_TEXT not in str(settings)
    assert main.Settings.model_config.get("env_file") is None
