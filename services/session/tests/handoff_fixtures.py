"""Load the committed synthetic handoff fixtures in ``handoff/fixtures/v1``."""

import copy
import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parents[3] / "handoff" / "fixtures" / "v1"
ACCEPTED = sorted((FIXTURES / "accepted").glob("*.json"))
REJECTED = sorted((FIXTURES / "rejected").glob("*.json"))


def load(path: Path) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return payload


def expected_reason(path: Path) -> str:
    """A rejected fixture is named ``<reason>.json`` or ``<reason>--<case>.json``."""
    return path.stem.split("--")[0]


def routine() -> dict[str, Any]:
    """A fresh copy of the routine text session, for tests that change one field."""
    return copy.deepcopy(load(FIXTURES / "accepted" / "routine-intake-text.json"))


def voice() -> dict[str, Any]:
    """A fresh copy of the resistant-client voice session."""
    return copy.deepcopy(load(FIXTURES / "accepted" / "resistant-client-voice.json"))


def crisis() -> dict[str, Any]:
    """A fresh copy of the crisis session."""
    return copy.deepcopy(load(FIXTURES / "accepted" / "crisis-risk-voice.json"))
