"""The session domain stays free of web, cloud and identity frameworks (#31 FR-8, AC3).

The lifecycle, the signed state, the ports and the prompt loader hold the
rules. FastAPI, the Agent Platform HTTP client and Firebase belong in the
adapters and the app, so the domain can be tested with fakes and reused. Two
checks:

- a static one, over each domain file's imports, including string-literal
  ``import_module`` and ``__import__`` calls;
- a run-time one, which imports the domain in a fresh interpreter and checks
  that no framework module was loaded through any import chain.
"""

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_speech_import_boundary import _imported_names

SERVICE_ROOT = Path(__file__).resolve().parents[1]

DOMAIN_MODULES = (
    "cst_session/state.py",
    "cst_session/lifecycle.py",
    "cst_session/grading.py",
    "cst_session/persona/__init__.py",
    "cst_session/persona/port.py",
    "cst_session/scenarios/prompts.py",
)
FRAMEWORK_MODULES = (
    "fastapi",
    "starlette",
    "uvicorn",
    "httpx",
    "httpcore",
    "google",
    "firebase_admin",
    "pydantic_settings",
)


def _is_framework(name: str) -> bool:
    return any(name == top or name.startswith(top + ".") for top in FRAMEWORK_MODULES)


def framework_imports(source: str) -> list[str]:
    return sorted(
        {
            f"{line} imports {name}"
            for line, name in _imported_names(ast.parse(source))
            if _is_framework(name)
        }
    )


@pytest.mark.parametrize("relative_path", DOMAIN_MODULES)
def test_a_domain_module_imports_no_framework(relative_path: str) -> None:
    source = (SERVICE_ROOT / relative_path).read_text(encoding="utf-8")

    assert framework_imports(source) == []


def test_importing_the_domain_loads_no_framework() -> None:
    modules = [
        path.removesuffix(".py").removesuffix("/__init__").replace("/", ".")
        for path in DOMAIN_MODULES
    ]
    script = (
        "import importlib, json, sys\n"
        f"for name in {modules!r}:\n"
        "    importlib.import_module(name)\n"
        "print(json.dumps(sorted(sys.modules)))\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=SERVICE_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )

    loaded: list[str] = json.loads(result.stdout)
    assert set(modules) <= set(loaded)
    assert [name for name in loaded if _is_framework(name)] == []


@pytest.mark.parametrize(
    "source",
    [
        "import fastapi",
        "from fastapi import FastAPI",
        "from starlette.requests import Request",
        "import httpx",
        "from google.auth import default",
        "import google.auth.transport.requests",
        "import firebase_admin",
        "from firebase_admin import auth",
        "import importlib\nimportlib.import_module('httpx')",
        "__import__('google.auth')",
    ],
)
def test_the_check_catches_each_framework_import(source: str) -> None:
    assert framework_imports(source) != []


@pytest.mark.parametrize(
    "source",
    [
        "import json",
        "from pydantic import BaseModel",
        "from cst_session.state import StateCodec",
        "import googleapis_lookalike",
    ],
)
def test_the_check_allows_other_imports(source: str) -> None:
    assert framework_imports(source) == []
