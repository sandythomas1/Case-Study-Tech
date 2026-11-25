"""Service code logs only through content_free_log (AC4, POLICY DAT-7).

Ruff's ``T20`` and ``LOG015`` rules (pyproject.toml) flag ``print``, ``pprint``
and calls such as ``logging.info()`` on the root logger. This check covers what
ruff cannot see, in every ``cst_*`` package of the service:

- an import of ``logging``, ``traceback`` or ``warnings`` (plain or ``from``)
  outside the per-service allow-list below, where each entry gives its reason;
- the root logger, through ``getLogger()`` (or ``getLogger("")``,
  ``getLogger(None)``, ``getLogger("root")``) or ``logging.root``, in any file;
- any reference to ``sys.stdout``, ``sys.stderr``, ``sys.__stdout__`` or
  ``sys.__stderr__`` (or importing them with ``from sys import ...``) anywhere
  except the helper, which is exempt only at its exact path
  ``cst_<service>/content_free_log.py``;
- any ``os.write`` call, in any file;
- in the modules that handle session content and log (per service, below),
  any logging other than ``log_event``/``log_error`` imported from the
  service's own helper, and any logger-style method call.

The same file runs in every service and picks its lists by service
directory name. It parses source, so it cannot see a module or logger name
built at run time; review covers that.
"""

import ast
import re
from collections.abc import Mapping
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[1]
HELPER = "content_free_log.py"
HELPER_PATH = re.compile(r"cst_[a-z0-9_]+/content_free_log\.py")
LOGGING_MODULES = ("logging", "traceback", "warnings")
ROOT_LOGGER_NAMES = (None, "", "root")
STD_STREAMS = {"stdout", "stderr", "__stdout__", "__stderr__"}

# Files that may import a logging module, per service, each with its reason.
# Adding one needs review: the file must still never log content.
LOGGING_IMPORT_ALLOW_LIST: dict[str, dict[str, str]] = {
    "accounts": {
        "cst_accounts/firebase.py": (
            "Raises the httpx and httpcore log level so request URLs carrying the"
            " API key are never logged."
        ),
    },
    "session": {
        "cst_session/main.py": (
            "Raises the httpx and httpcore log level so persona request URLs are"
            " never logged."
        ),
        "cst_session/speech/adapters/deepgram_transport.py": (
            "Builds an unregistered logger with a NullHandler so the websockets"
            " client logs nothing."
        ),
    },
}
ALLOWED = LOGGING_IMPORT_ALLOW_LIST.get(SERVICE_ROOT.name, {})

# Modules that hold session content and log, per service. They log only
# through the helper and may never join the allow-list above.
CONTENT_LOGGING_MODULES: dict[str, tuple[str, ...]] = {
    "session": (
        "cst_session/lifecycle.py",
        "cst_session/handoff/validation.py",
    ),
}
CONTENT_LOGGERS = CONTENT_LOGGING_MODULES.get(SERVICE_ROOT.name, ())
HELPER_FUNCTIONS = {"log_event", "log_error"}
LOGGER_METHODS = {
    "debug",
    "info",
    "warning",
    "warn",
    "error",
    "exception",
    "critical",
    "fatal",
    "log",
}


def _is_logging_module(name: str) -> bool:
    return any(
        name == module or name.startswith(module + ".") for module in LOGGING_MODULES
    )


def _is_root_logger_lookup(node: ast.Call) -> bool:
    func = node.func
    named = (isinstance(func, ast.Attribute) and func.attr == "getLogger") or (
        isinstance(func, ast.Name) and func.id == "getLogger"
    )
    if not named:
        return False
    if not node.args and not node.keywords:
        return True
    name = node.args[0] if node.args else node.keywords[0].value
    return isinstance(name, ast.Constant) and name.value in ROOT_LOGGER_NAMES


def _is_logging_root(node: ast.Attribute) -> bool:
    return (
        node.attr == "root"
        and isinstance(node.value, ast.Name)
        and node.value.id == "logging"
    )


def _is_std_stream(node: ast.Attribute) -> bool:
    return (
        node.attr in STD_STREAMS
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
    )


def _is_os_write(node: ast.Call) -> bool:
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "write"
        and isinstance(func.value, ast.Name)
        and func.value.id == "os"
    )


def _import_violations(node: ast.Import | ast.ImportFrom, allowed: bool) -> list[str]:
    if isinstance(node, ast.Import):
        modules = [alias.name for alias in node.names]
    elif node.module and node.level == 0:
        modules = [node.module]
    else:
        return []
    found: list[str] = []
    if not allowed:
        found += [f"imports {name}" for name in modules if _is_logging_module(name)]
    if isinstance(node, ast.ImportFrom):
        names = {alias.name for alias in node.names}
        if node.module == "logging" and "root" in names:
            found.append("uses the root logger")
        if node.module == "sys" and names & STD_STREAMS:
            found.append("imports a std stream")
        if node.module == "os" and "write" in names:
            found.append("imports os.write")
    return found


def _file_violations(
    tree: ast.AST, allowed: bool, helper: bool
) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        problems: list[str] = []
        if isinstance(node, ast.Import | ast.ImportFrom):
            problems = _import_violations(node, allowed)
            if helper:
                problems = [p for p in problems if p != "imports a std stream"]
        elif isinstance(node, ast.Call) and _is_root_logger_lookup(node):
            problems = ["uses the root logger"]
        elif isinstance(node, ast.Call) and _is_os_write(node):
            problems = ["writes with os.write"]
        elif isinstance(node, ast.Attribute) and _is_std_stream(node) and not helper:
            problems = ["uses a std stream"]
        elif isinstance(node, ast.Attribute) and _is_logging_root(node):
            problems = ["uses the root logger"]
        found += [(getattr(node, "lineno", 0), problem) for problem in problems]
    return found


def find_logging_bypasses(root: Path, allowed: Mapping[str, str]) -> list[str]:
    """Every logging bypass in the ``cst_*`` packages under ``root``."""
    violations: list[str] = []
    for path in sorted(root.glob("cst_*/**/*.py")):
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        helper = HELPER_PATH.fullmatch(relative) is not None
        found = _file_violations(tree, relative in allowed, helper)
        violations += [f"{relative}:{line} {problem}" for line, problem in found]
    return violations


def test_service_packages_log_only_through_the_helper() -> None:
    assert sorted(SERVICE_ROOT.glob("cst_*/__init__.py"))
    assert find_logging_bypasses(SERVICE_ROOT, ALLOWED) == []


def helper_only_violations(source: str, package: str) -> list[str]:
    """How a content module logs other than through ``package``'s helper."""
    helper_module = f"{package}.content_free_log"
    found: list[str] = []
    imported_helpers: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module == helper_module:
            names = {alias.name for alias in node.names}
            found += [
                f"imports {name} from the helper" for name in names - HELPER_FUNCTIONS
            ]
            imported_helpers |= names & HELPER_FUNCTIONS
        elif isinstance(node, ast.ImportFrom | ast.Import):
            modules = (
                [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else [alias.name for alias in node.names]
            )
            if any(name.endswith("content_free_log") for name in modules):
                found.append("imports the helper module, not its functions")
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in LOGGER_METHODS
        ):
            found.append(f"calls .{node.func.attr}()")
    if not imported_helpers:
        found.append("does not log through the helper")
    return found


@pytest.mark.parametrize("relative_path", CONTENT_LOGGERS)
def test_content_modules_log_only_through_the_helper(relative_path: str) -> None:
    source = (SERVICE_ROOT / relative_path).read_text(encoding="utf-8")
    package = relative_path.split("/")[0]

    assert relative_path not in ALLOWED
    assert helper_only_violations(source, package) == []


@pytest.mark.parametrize(
    "source",
    [
        "from cst_demo.content_free_log import log_event, _write",
        "import cst_demo.content_free_log as helper",
        "from cst_demo import content_free_log",
        "from cst_demo.content_free_log import log_event\nlogger.info('x')",
        "from cst_demo.content_free_log import log_event\nlog.warning('x')",
        "from cst_other.content_free_log import log_event",
        "import json",
    ],
)
def test_the_helper_only_check_fails_on_other_logging(source: str) -> None:
    assert helper_only_violations(source, "cst_demo") != []


def test_the_helper_only_check_allows_the_helper_functions() -> None:
    source = "from cst_demo.content_free_log import log_error, log_event"

    assert helper_only_violations(source, "cst_demo") == []


def test_every_allow_list_entry_exists_and_has_a_reason() -> None:
    for relative, reason in ALLOWED.items():
        assert (SERVICE_ROOT / relative).is_file(), relative
        assert reason.strip(), relative


def write_module(root: Path, source: str, name: str = "handler.py") -> None:
    module = root / "cst_demo" / name
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text(source, encoding="utf-8")


@pytest.mark.parametrize(
    "source",
    [
        "import logging\nlogging.getLogger().info('x')",
        "import logging\nlogging.getLogger('').warning('x')",
        "import logging\nlogging.getLogger(name=None).error('x')",
        "import logging\nlogging.getLogger('root').exception('x')",
        "from logging import getLogger\nlog = getLogger()",
        "import sys\nsys.stdout.write('x')",
        "import sys\nsys.stderr.writelines(['x'])",
        "import logging",
        "import logging.handlers",
        "import logging as log",
        "from logging import getLogger",
        "from logging.handlers import RotatingFileHandler",
        "import traceback",
        "from traceback import format_exc",
        "import warnings",
        "from warnings import warn",
        "from sys import stdout",
        "from sys import stderr as err",
        "from sys import __stdout__",
        "from sys import __stderr__",
        "import sys\nprint('x', file=sys.stderr)",
        "import sys\nout = sys.stdout",
        "import sys\nsys.__stdout__.write('x')",
        "import sys\nsys.__stderr__.flush()",
        "import sys\nwriter = getattr(sys.stdout, 'write')",
        "import os\nos.write(1, b'x')",
        "import os\nos.write(2, b'x')",
        "from os import write",
    ],
)
def test_the_check_fails_on_a_bypass(tmp_path: Path, source: str) -> None:
    write_module(tmp_path, source)

    assert find_logging_bypasses(tmp_path, {}) != []


@pytest.mark.parametrize(
    "source",
    [
        "import logging\nlogging.root.info('x')",
        "import logging\nlogging.root.handlers.clear()",
        "from logging import root",
        "import sys\nsys.stdout.write('x')",
        "from sys import stdout",
    ],
)
def test_an_allow_listed_file_still_may_not_use_the_root_logger_or_streams(
    tmp_path: Path, source: str
) -> None:
    write_module(tmp_path, source)

    assert find_logging_bypasses(tmp_path, {"cst_demo/handler.py": "reason"}) != []


@pytest.mark.parametrize(
    "source",
    [
        "import logging\nlogging.getLogger('httpx').setLevel(logging.WARNING)",
        "import logging\nlogging.getLogger(__name__)",
    ],
)
def test_an_allow_listed_file_may_configure_named_loggers(
    tmp_path: Path, source: str
) -> None:
    write_module(tmp_path, source)

    assert find_logging_bypasses(tmp_path, {"cst_demo/handler.py": "reason"}) == []


@pytest.mark.parametrize(
    "source",
    [
        "import io\nio.StringIO().write('x')",
        "import sys\nsys.exit(1)",
        "from sys import argv",
        "import json",
    ],
)
def test_the_check_allows_other_modules_and_streams(
    tmp_path: Path, source: str
) -> None:
    write_module(tmp_path, source)

    assert find_logging_bypasses(tmp_path, {}) == []


HELPER_SOURCES = (
    "import sys\nsys.stdout.write('x')",
    "import sys\nsys.stdout.flush()",
    "from sys import stdout",
)


@pytest.mark.parametrize("source", HELPER_SOURCES)
def test_only_the_helper_may_touch_std_streams(tmp_path: Path, source: str) -> None:
    write_module(tmp_path, source, name=HELPER)

    assert find_logging_bypasses(tmp_path, {}) == []


@pytest.mark.parametrize(
    "name", [f"sub/{HELPER}", f"deep/sub/{HELPER}", "my_" + HELPER]
)
@pytest.mark.parametrize("source", HELPER_SOURCES)
def test_a_file_named_like_the_helper_elsewhere_is_not_exempt(
    tmp_path: Path, name: str, source: str
) -> None:
    write_module(tmp_path, source, name=name)

    assert find_logging_bypasses(tmp_path, {}) != []


def test_even_the_helper_may_not_use_os_write(tmp_path: Path) -> None:
    write_module(tmp_path, "import os\nos.write(1, b'x')", name=HELPER)

    assert find_logging_bypasses(tmp_path, {}) != []


def test_the_helper_may_not_import_logging(tmp_path: Path) -> None:
    write_module(tmp_path, "import logging", name=HELPER)

    assert find_logging_bypasses(tmp_path, {}) != []
