"""Vendor speech SDKs may be imported only inside the adapter package (RC-16).

The check parses every Python file in the service, so it catches plain
imports, ``from`` imports and string-literal ``importlib.import_module`` or
``__import__`` calls. It cannot see an import built from a computed string;
code review covers that.
"""

import ast
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[1]
ADAPTERS_DIR = SERVICE_ROOT / "cst_session" / "speech" / "adapters"
SKIPPED_DIRS = {".venv", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}

VENDOR_SPEECH_MODULES = (
    "assemblyai",
    "azure.cognitiveservices.speech",
    "deepgram",
    "elevenlabs",
    "google.cloud.speech",
    "google.cloud.speech_v1",
    "google.cloud.speech_v1p1beta1",
    "google.cloud.speech_v2",
    "google.cloud.texttospeech",
    "google.cloud.texttospeech_v1",
    "google.cloud.texttospeech_v1beta1",
    "openai",
    "speechmatics",
)

CONTENT_HANDLING_MODULES = (
    "cst_session/speech/interface.py",
    "cst_session/speech/fake.py",
    "cst_session/speech/adapters/deepgram.py",
    "cst_session/handoff/contract.py",
    "cst_session/handoff/validation.py",
)
PERSISTENCE_MODULES = ("logging", "pathlib", "pickle", "shelve", "sqlite3", "tempfile")


# The speech wire client. Tests may use it to stand in for a vendor, so only
# the service package is checked for it.
SPEECH_WIRE_MODULES = ("websockets",)


def _is_vendor_module(
    name: str, modules: tuple[str, ...] = VENDOR_SPEECH_MODULES
) -> bool:
    return any(name == vendor or name.startswith(vendor + ".") for vendor in modules)


def _imported_names(tree: ast.AST) -> list[tuple[int, str]]:
    names: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append((node.lineno, node.module))
            names.extend(
                (node.lineno, f"{node.module}.{alias.name}") for alias in node.names
            )
        elif isinstance(node, ast.Call) and _is_dynamic_import(node.func):
            first = node.args[0] if node.args else None
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                names.append((node.lineno, first.value))
    return names


def _is_dynamic_import(func: ast.expr) -> bool:
    if isinstance(func, ast.Name):
        return func.id in {"__import__", "import_module"}
    return isinstance(func, ast.Attribute) and func.attr == "import_module"


def _python_files(root: Path) -> list[Path]:
    return [
        path for path in root.rglob("*.py") if not SKIPPED_DIRS.intersection(path.parts)
    ]


def find_vendor_imports(
    root: Path,
    adapters_dir: Path,
    modules: tuple[str, ...] = VENDOR_SPEECH_MODULES,
) -> list[str]:
    """Every import of ``modules`` under ``root`` outside ``adapters_dir``."""
    violations: list[str] = []
    for path in _python_files(root):
        if path.is_relative_to(adapters_dir):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for lineno, name in _imported_names(tree):
            if _is_vendor_module(name, modules):
                violations.append(f"{path.relative_to(root)}:{lineno} imports {name}")
    return sorted(set(violations))


def test_service_imports_no_vendor_speech_sdk_outside_the_adapters() -> None:
    assert find_vendor_imports(SERVICE_ROOT, ADAPTERS_DIR) == []


def test_the_service_package_uses_the_speech_wire_client_only_in_the_adapters() -> None:
    package = SERVICE_ROOT / "cst_session"

    assert find_vendor_imports(package, ADAPTERS_DIR, SPEECH_WIRE_MODULES) == []


def test_the_wire_check_fails_on_websockets_outside_the_adapters(
    tmp_path: Path,
) -> None:
    (tmp_path / "session_logic.py").write_text(
        "from websockets.asyncio.client import connect", encoding="utf-8"
    )

    assert find_vendor_imports(tmp_path, tmp_path / "adapters", SPEECH_WIRE_MODULES)


@pytest.mark.parametrize(
    "source",
    [
        "import openai",
        "import google.cloud.speech_v2 as speech",
        "from google.cloud import texttospeech",
        "from azure.cognitiveservices.speech import SpeechConfig",
        "import importlib\nimportlib.import_module('deepgram')",
        "__import__('elevenlabs.client')",
    ],
)
def test_the_check_fails_on_a_vendor_import_outside_the_adapters(
    tmp_path: Path, source: str
) -> None:
    (tmp_path / "session_logic.py").write_text(source, encoding="utf-8")

    assert find_vendor_imports(tmp_path, tmp_path / "adapters") != []


def test_the_check_allows_vendor_imports_inside_the_adapters(tmp_path: Path) -> None:
    adapters = tmp_path / "adapters"
    adapters.mkdir()
    (adapters / "google_speech.py").write_text(
        "from google.cloud import speech_v2", encoding="utf-8"
    )

    assert find_vendor_imports(tmp_path, adapters) == []


@pytest.mark.parametrize(
    "source",
    [
        "import openai_compatible_helpers",
        "from google.cloud import firestore",
        "from cst_session.speech import SpeechProvider",
    ],
)
def test_the_check_ignores_non_vendor_imports(tmp_path: Path, source: str) -> None:
    (tmp_path / "session_logic.py").write_text(source, encoding="utf-8")

    assert find_vendor_imports(tmp_path, tmp_path / "adapters") == []


@pytest.mark.parametrize("relative_path", CONTENT_HANDLING_MODULES)
def test_content_handling_modules_import_no_logging_or_storage(
    relative_path: str,
) -> None:
    tree = ast.parse((SERVICE_ROOT / relative_path).read_text(encoding="utf-8"))
    imported = {name.split(".")[0] for _, name in _imported_names(tree)}
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert imported.isdisjoint(PERSISTENCE_MODULES)
    assert "open" not in called and "print" not in called
