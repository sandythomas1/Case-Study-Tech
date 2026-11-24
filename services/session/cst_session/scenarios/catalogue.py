"""The three vetted scenarios, loaded read-only from version-controlled config.

The MVP ships exactly three scenarios (RC-22, DD-07). Each one is a TOML file in
``configs/``, named after its id. Loading is strict: a missing, unknown or
wrong-typed key fails, and so does any set of files other than the three
expected ids. A failure raises ``CatalogueError`` naming the file and key, so a
bad config stops the service at startup rather than reaching a student.

There is no create, edit or write path (AG-6). Scenarios and the catalogue are
immutable, and a scenario changes only through a reviewed commit to its file.

``Catalogue.library()`` lists the released scenarios for the library (#28).
``Catalogue.startable()`` is the check session start (#31) must call. It raises
the same ``ScenarioUnavailable`` for an unknown id and an unreleased one, so a
scenario held back under CD-3 cannot be told apart from one that never existed.
"""

import re
import tomllib
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Final

# The order the library shows them in. The ids match rubric/anchor-spec.v1.json.
SCENARIO_IDS: Final = ("routine_intake", "resistant_client", "crisis_risk")

_VERSION = re.compile(r"[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}", re.ASCII)
_MAX_TEXT = 300
_MAX_MINUTES = 60
_TEXT_KEYS: Final = (
    "title",
    "summary",
    "learning_objective",
    "session_format",
    "feedback_timing",
    "content_notice",
)
_FLAG_KEYS: Final = ("crisis", "requires_opt_in", "released")
_REQUIRED_KEYS: Final = frozenset(
    {"id", "version", "time_limit_minutes", *_TEXT_KEYS, *_FLAG_KEYS}
)
_OPTIONAL_KEYS: Final = frozenset({"opt_in_statement"})


class CatalogueError(Exception):
    """A scenario configuration is missing, malformed or unexpected."""


class ScenarioUnavailable(Exception):
    """The scenario does not exist or is not released, so it cannot start."""

    def __init__(self) -> None:
        super().__init__("This scenario is not available.")


@dataclass(frozen=True, slots=True, kw_only=True)
class Scenario:
    """One vetted scenario, as a student sees it before the session starts."""

    id: str
    version: str
    title: str
    summary: str
    learning_objective: str
    session_format: str
    time_limit_minutes: int
    feedback_timing: str
    content_notice: str
    crisis: bool
    requires_opt_in: bool
    opt_in_statement: str | None
    released: bool


class Catalogue:
    """The loaded scenarios. Read-only: it has no way to add or change one."""

    __slots__ = ("_scenarios",)

    def __init__(self, scenarios: tuple[Scenario, ...]) -> None:
        self._scenarios = scenarios

    @property
    def scenarios(self) -> tuple[Scenario, ...]:
        """Every configured scenario, released or not, in library order."""
        return self._scenarios

    def library(self) -> tuple[Scenario, ...]:
        """The released scenarios, in library order (#28)."""
        return tuple(scenario for scenario in self._scenarios if scenario.released)

    def startable(self, scenario_id: str) -> Scenario:
        """Return the released scenario ``scenario_id``, or raise ``ScenarioUnavailable``."""
        for scenario in self._scenarios:
            if scenario.id == scenario_id and scenario.released:
                return scenario
        raise ScenarioUnavailable()


def load_catalogue(directory: Traversable | None = None) -> Catalogue:
    """Load and validate the three scenarios from ``directory`` (default: ``configs/``)."""
    root = (
        directory
        if directory is not None
        else files("cst_session.scenarios") / "configs"
    )
    found = sorted(
        entry.name for entry in root.iterdir() if entry.name.endswith(".toml")
    )
    expected = sorted(f"{scenario_id}.toml" for scenario_id in SCENARIO_IDS)
    if found != expected:
        raise CatalogueError(f"expected exactly {expected}, found {found}")
    return Catalogue(
        tuple(
            _parse(f"{scenario_id}.toml", (root / f"{scenario_id}.toml").read_bytes())
            for scenario_id in SCENARIO_IDS
        )
    )


def _parse(name: str, raw: bytes) -> Scenario:
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise CatalogueError(f"{name}: not valid UTF-8 TOML") from exc

    keys = set(data)
    if missing := sorted(_REQUIRED_KEYS - keys):
        raise CatalogueError(f"{name}: missing {missing}")
    if unknown := sorted(keys - _REQUIRED_KEYS - _OPTIONAL_KEYS):
        raise CatalogueError(f"{name}: unknown {unknown}")

    if data["id"] != name.removesuffix(".toml"):
        raise CatalogueError(f"{name}: id must match the file name")
    if not isinstance(data["version"], str) or not _VERSION.fullmatch(data["version"]):
        raise CatalogueError(f"{name}: version must be MAJOR.MINOR.PATCH")
    minutes = data["time_limit_minutes"]
    if type(minutes) is not int or not 1 <= minutes <= _MAX_MINUTES:
        raise CatalogueError(f"{name}: time_limit_minutes must be 1 to {_MAX_MINUTES}")
    flags = {key: _flag(name, key, data[key]) for key in _FLAG_KEYS}

    return Scenario(
        id=data["id"],
        version=data["version"],
        title=_text(name, "title", data["title"]),
        summary=_text(name, "summary", data["summary"]),
        learning_objective=_text(
            name, "learning_objective", data["learning_objective"]
        ),
        session_format=_text(name, "session_format", data["session_format"]),
        time_limit_minutes=minutes,
        feedback_timing=_text(name, "feedback_timing", data["feedback_timing"]),
        content_notice=_text(name, "content_notice", data["content_notice"]),
        crisis=flags["crisis"],
        requires_opt_in=flags["requires_opt_in"],
        opt_in_statement=_opt_in_statement(name, data, flags),
        released=flags["released"],
    )


def _text(name: str, key: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > _MAX_TEXT
        or any(_breaks_the_line(char) for char in value)
    ):
        raise CatalogueError(
            f"{name}: {key} must be one trimmed line of 1 to {_MAX_TEXT} characters"
        )
    return value


def _breaks_the_line(char: str) -> bool:
    """Control and format characters (C*), and line or paragraph separators."""
    category = unicodedata.category(char)
    return category.startswith("C") or category in {"Zl", "Zp"}


def _flag(name: str, key: str, value: object) -> bool:
    if type(value) is not bool:
        raise CatalogueError(f"{name}: {key} must be true or false")
    return value


def _opt_in_statement(
    name: str, data: Mapping[str, object], flags: Mapping[str, bool]
) -> str | None:
    if flags["crisis"] and not flags["requires_opt_in"]:
        raise CatalogueError(f"{name}: a crisis scenario must require opt-in")
    has_statement = "opt_in_statement" in data
    if flags["requires_opt_in"] != has_statement:
        raise CatalogueError(
            f"{name}: opt_in_statement is required if and only if requires_opt_in is true"
        )
    if not has_statement:
        return None
    return _text(name, "opt_in_statement", data["opt_in_statement"])
