"""No API path creates or edits a scenario (#27 AC4, AG-6, RC-22).

Scenarios change only through a reviewed commit to ``configs/``. This check
parses every service package in the repository (``services/*/cst_*``), so the
session and grading HTTP apps are covered as soon as they exist:

- A route whose path mentions a scenario may only be a read (``GET``/``HEAD``).
  That covers ``@app.post(...)``-style decorators, ``api_route``/``add_api_route``
  with ``methods=``, ``add_route``, Starlette ``Route(...)`` and websockets.
- The scenarios package, which holds the catalogue and the interim persona
  prompt loader (#31), never writes a file.

It cannot see a path built at run time; code review covers that.
"""

import ast
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIOS_PACKAGE = REPO_ROOT / "services" / "session" / "cst_session" / "scenarios"
SKIPPED_DIRS = {".venv", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}

READ_METHODS = {"GET", "HEAD"}
WRITE_DECORATORS = {"post", "put", "patch", "delete", "options", "websocket"}
ROUTE_CALLS = {
    "api_route",
    "add_api_route",
    "add_route",
    "route",
    "Route",
    "websocket_route",
}
WRITE_CALLS = {
    "write_text",
    "write_bytes",
    "mkdir",
    "unlink",
    "rename",
    "replace",
    "touch",
}


def service_files() -> Iterator[Path]:
    for package in sorted((REPO_ROOT / "services").glob("*/cst_*")):
        for path in sorted(package.rglob("*.py")):
            if not SKIPPED_DIRS.intersection(path.parts):
                yield path


def mentions_scenario(node: ast.Call) -> bool:
    return any(
        isinstance(arg, ast.Constant)
        and isinstance(arg.value, str)
        and "scenario" in arg.value.lower()
        for arg in [*node.args, *(keyword.value for keyword in node.keywords)]
    )


def declared_methods(node: ast.Call) -> set[str] | None:
    """The methods a route call declares, or ``None`` if it declares none."""
    for keyword in node.keywords:
        if keyword.arg == "methods" and isinstance(
            keyword.value, ast.List | ast.Tuple | ast.Set
        ):
            return {
                element.value.upper()
                for element in keyword.value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            }
    return None


def call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return None


def scenario_write_routes(tree: ast.AST) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not mentions_scenario(node):
            continue
        name = call_name(node)
        if name in WRITE_DECORATORS:
            lines.append(node.lineno)
        elif name in ROUTE_CALLS:
            methods = declared_methods(node)
            if methods is None or not methods <= READ_METHODS:
                lines.append(node.lineno)
    return lines


def file_writes(tree: ast.AST) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = call_name(node)
        if name in WRITE_CALLS:
            lines.append(node.lineno)
        elif name == "open":
            modes = [
                arg.value
                for arg in [
                    *node.args[1:],
                    *(k.value for k in node.keywords if k.arg == "mode"),
                ]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
            ]
            if not modes or any(set(mode) & set("wax+") for mode in modes):
                lines.append(node.lineno)
    return lines


def test_the_check_sees_every_service_package() -> None:
    packages = {path.relative_to(REPO_ROOT).parts[1] for path in service_files()}

    assert {"accounts", "session"} <= packages


def test_no_service_declares_a_route_that_writes_a_scenario() -> None:
    offenders = [
        f"{path.relative_to(REPO_ROOT)}:{line}"
        for path in service_files()
        for line in scenario_write_routes(ast.parse(path.read_text(encoding="utf-8")))
    ]

    assert offenders == []


def test_the_write_check_covers_the_catalogue_and_the_prompt_loader() -> None:
    scanned = {
        path.relative_to(SCENARIOS_PACKAGE).as_posix()
        for path in SCENARIOS_PACKAGE.rglob("*.py")
    }

    assert {"catalogue.py", "prompts.py"} <= scanned


def test_the_scenarios_package_never_writes_a_file() -> None:
    offenders = [
        f"{path.relative_to(REPO_ROOT)}:{line}"
        for path in sorted(SCENARIOS_PACKAGE.rglob("*.py"))
        for line in file_writes(ast.parse(path.read_text(encoding="utf-8")))
    ]

    assert offenders == []


# The check itself: each shape it must catch, and the reads it must allow.

WRITE_ROUTE_SAMPLES = [
    '@app.post("/v1/scenarios")\ndef f(): ...',
    '@router.put("/v1/scenarios/{scenario_id}")\ndef f(): ...',
    '@app.patch("/v1/scenarios/{scenario_id}")\ndef f(): ...',
    '@app.delete("/v1/scenarios/{scenario_id}")\ndef f(): ...',
    'app.add_api_route("/v1/scenarios", f, methods=["POST"])',
    'app.add_api_route("/v1/scenarios", f)',
    '@app.api_route("/v1/scenarios", methods=["GET", "PUT"])\ndef f(): ...',
    'routes = [Route("/v1/scenarios", f, methods=["POST"])]',
    '@app.websocket("/v1/scenarios/live")\nasync def f(ws): ...',
]
READ_ROUTE_SAMPLES = [
    '@app.get("/v1/scenarios")\ndef f(): ...',
    'app.add_api_route("/v1/scenarios", f, methods=["GET"])',
    '@app.post("/v1/sessions")\ndef f(): ...',
]


def test_the_route_check_catches_every_write_shape() -> None:
    for sample in WRITE_ROUTE_SAMPLES:
        assert scenario_write_routes(ast.parse(sample)), sample


def test_the_route_check_allows_reads_and_other_routes() -> None:
    for sample in READ_ROUTE_SAMPLES:
        assert scenario_write_routes(ast.parse(sample)) == [], sample


def test_the_file_write_check_catches_writes_and_allows_reads() -> None:
    for sample in [
        'open(p, "w")',
        'open(p, mode="a")',
        'open(p, "r+")',
        "open(p, m)",
        "p.write_text(s)",
        "p.write_bytes(b)",
    ]:
        assert file_writes(ast.parse(sample)), sample
    for sample in ['open(p, "rb")', 'open(p, mode="r")', "p.read_bytes()"]:
        assert file_writes(ast.parse(sample)) == [], sample
