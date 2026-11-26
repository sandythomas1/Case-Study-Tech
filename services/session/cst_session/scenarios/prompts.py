"""The persona prompts, one per scenario, versioned and loaded read-only (#31, #67).

Each prompt is a vetted, fictional text file in ``prompts/``, named after its
scenario id (``prompts/README.md``). Loading is as strict as ``load_catalogue``:
exactly the three ids, UTF-8 with no byte-order mark, no control or format
characters except tab and newline, not blank and at most ``MAX_PROMPT_CHARS``
characters. CRLF line endings from a Windows checkout load as LF.

``prompts/manifest.toml`` records each prompt's version (``MAJOR.MINOR.PATCH``)
and the SHA-256 of its loaded text (after CRLF to LF and the strip). A prompt
whose text doesn't match its digest never loads, so every prompt edit comes
with a reviewed version bump (FR-2). A failure raises ``PromptError`` naming the
file or scenario id, never prompt content or a digest, so a bad prompt stops the
service at startup.

There is no write path (AG-6). A prompt changes only through a reviewed commit.
A prompt goes to the model only as the system instruction for its own verified
scenario (T6, T10).
"""

import hashlib
import re
import tomllib
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from types import MappingProxyType
from typing import Final

from cst_session.scenarios.catalogue import SCENARIO_IDS

MAX_PROMPT_CHARS: Final = 3000
_ALLOWED_CONTROLS: Final = frozenset({"\n", "\t"})
_MANIFEST: Final = "manifest.toml"
_MANIFEST_KEYS: Final = frozenset({"version", "sha256"})
# Strict semver core: no leading zeros, no pre-release or build suffix.
_VERSION: Final = re.compile(
    r"(?:0|[1-9][0-9]{0,3})(?:\.(?:0|[1-9][0-9]{0,3})){2}", re.ASCII
)
_DIGEST: Final = re.compile(r"[0-9a-f]{64}", re.ASCII)


class PromptError(Exception):
    """A persona prompt is missing, malformed or unexpected."""


class Prompts:
    """The loaded prompts. Read-only: it has no way to add or change one."""

    __slots__ = ("_texts", "_versions")

    def __init__(self, texts: Mapping[str, str], versions: Mapping[str, str]) -> None:
        self._texts: Mapping[str, str] = MappingProxyType(dict(texts))
        self._versions: Mapping[str, str] = MappingProxyType(dict(versions))

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

    def version_for(self, scenario_id: str) -> str:
        """The recorded version of the prompt for ``scenario_id``, or raise ``PromptError``."""
        version = self._versions.get(scenario_id)
        if version is None:
            raise PromptError("no prompt version for this scenario")
        return version


def load_prompts(directory: Traversable | None = None) -> Prompts:
    """Load and check the three prompts and their manifest from ``directory``.

    The default directory is the packaged ``prompts/``.
    """
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
    manifest = _manifest(root / _MANIFEST)
    texts = {
        scenario_id: _parse(
            f"{scenario_id}.txt", (root / f"{scenario_id}.txt").read_bytes()
        )
        for scenario_id in SCENARIO_IDS
    }
    for scenario_id, text in texts.items():
        if _digest(text) != manifest[scenario_id].sha256:
            raise PromptError(
                f"{_MANIFEST}: {scenario_id}: sha256 does not match {scenario_id}.txt"
            )
    return Prompts(
        texts, {scenario_id: entry.version for scenario_id, entry in manifest.items()}
    )


def _digest(text: str) -> str:
    """Lowercase hex SHA-256 of the loaded text's UTF-8 bytes."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class _Recorded:
    """One manifest entry: the prompt's version and the digest of its text."""

    version: str
    sha256: str


def _manifest(entry: Traversable) -> dict[str, _Recorded]:
    """Parse the manifest: exactly the three ids, each a ``version`` and a ``sha256``."""
    if not entry.is_file():
        raise PromptError(f"{_MANIFEST}: missing")
    try:
        data = tomllib.loads(entry.read_bytes().decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise PromptError(f"{_MANIFEST}: not valid UTF-8 TOML") from exc

    ids = set(data)
    if missing := sorted(set(SCENARIO_IDS) - ids):
        raise PromptError(f"{_MANIFEST}: missing ids {missing}")
    if unknown := sorted(ids - set(SCENARIO_IDS)):
        raise PromptError(f"{_MANIFEST}: unknown ids {unknown}")
    return {
        scenario_id: _recorded(scenario_id, data[scenario_id])
        for scenario_id in SCENARIO_IDS
    }


def _recorded(scenario_id: str, table: object) -> _Recorded:
    where = f"{_MANIFEST}: {scenario_id}"
    if not isinstance(table, dict):
        raise PromptError(f"{where}: must be a table")
    keys = set(table)
    if missing := sorted(_MANIFEST_KEYS - keys):
        raise PromptError(f"{where}: missing {missing}")
    if unknown := sorted(keys - _MANIFEST_KEYS):
        raise PromptError(f"{where}: unknown {unknown}")
    version, digest = table["version"], table["sha256"]
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise PromptError(f"{where}: version must be MAJOR.MINOR.PATCH")
    if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
        raise PromptError(f"{where}: sha256 must be 64 lowercase hex characters")
    return _Recorded(version=version, sha256=digest)


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
