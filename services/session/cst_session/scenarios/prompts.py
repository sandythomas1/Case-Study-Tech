"""The interim persona prompts, one per scenario, loaded read-only (#31).

Each prompt is a short synthetic text file in ``prompts/``, named after its
scenario id. They are interim until #67 replaces them (``prompts/README.md``).
Loading is as strict as ``load_catalogue``: exactly the three ids, UTF-8 with no
byte-order mark, no control or format characters except tab and newline, not
blank and at most ``MAX_PROMPT_CHARS`` characters. CRLF line endings from a
Windows checkout load as LF. A failure raises ``PromptError`` naming the file,
never its content, so a bad prompt stops the service at startup.

There is no write path (AG-6). A prompt changes only through a reviewed commit.
A prompt goes to the model only as the system instruction for its own verified
scenario (T6, T10).
"""

import unicodedata
from collections.abc import Mapping
from importlib.resources import files
from importlib.resources.abc import Traversable
from types import MappingProxyType
from typing import Final

from cst_session.scenarios.catalogue import SCENARIO_IDS

MAX_PROMPT_CHARS: Final = 1500
_ALLOWED_CONTROLS: Final = frozenset({"\n", "\t"})


class PromptError(Exception):
    """A persona prompt is missing, malformed or unexpected."""


class Prompts:
    """The loaded prompts. Read-only: it has no way to add or change one."""

    __slots__ = ("_texts",)

    def __init__(self, texts: Mapping[str, str]) -> None:
        self._texts: Mapping[str, str] = MappingProxyType(dict(texts))

    @property
    def texts(self) -> Mapping[str, str]:
        """Every prompt by scenario id, as a read-only mapping."""
        return self._texts

    def for_scenario(self, scenario_id: str) -> str:
        """The prompt for ``scenario_id``, or raise ``PromptError``."""
        text = self._texts.get(scenario_id)
        if text is None:
            raise PromptError("no prompt for this scenario")
        return text


def load_prompts(directory: Traversable | None = None) -> Prompts:
    """Load and check the three prompts from ``directory`` (default: ``prompts/``)."""
    root = (
        directory
        if directory is not None
        else files("cst_session.scenarios") / "prompts"
    )
    found = sorted(
        entry.name for entry in root.iterdir() if entry.name.endswith(".txt")
    )
    expected = sorted(f"{scenario_id}.txt" for scenario_id in SCENARIO_IDS)
    if found != expected:
        raise PromptError(f"expected exactly {expected}, found {found}")
    return Prompts(
        {
            scenario_id: _parse(
                f"{scenario_id}.txt", (root / f"{scenario_id}.txt").read_bytes()
            )
            for scenario_id in SCENARIO_IDS
        }
    )


def _parse(name: str, raw: bytes) -> str:
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError:
        decoded = None
    if decoded is None:
        raise PromptError(f"{name}: not valid UTF-8")
    # join/split rather than str.replace, which the write-path check reads as
    # Path.replace.
    text = "\n".join(decoded.split("\r\n")).strip()
    if not text:
        raise PromptError(f"{name}: empty")
    if len(text) > MAX_PROMPT_CHARS:
        raise PromptError(f"{name}: longer than {MAX_PROMPT_CHARS} characters")
    if any(_forbidden(char) for char in text):
        raise PromptError(f"{name}: holds a control or format character")
    return text


def _forbidden(char: str) -> bool:
    """Control, format, surrogate and private-use characters, except tab and newline."""
    return char not in _ALLOWED_CONTROLS and unicodedata.category(char).startswith("C")
