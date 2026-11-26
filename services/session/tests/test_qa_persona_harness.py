"""QA evidence for #67 that the implementer's suites leave implicit.

- AC1: the prompt ids, the manifest ids and the #27 catalogue ids are the same
  three, and a session on each config sends that config's own prompt.
- AC4: no service or harness route that names a prompt or a persona writes.
- FR-5: across every script, a passing, failing, blocked or stopped run never
  puts a reply, a prompt line or a script turn on stdout, stderr or a log.
- FR-5: at run time the harness opens no file for writing.
- FR-6: the default ``pytest`` run deselects every live test.
- The service image copies only ``requirements.txt`` and ``cst_session``.

Every reply here is synthetic and no test reaches the network.
"""

import ast
import asyncio
import builtins
import io
import json
import logging
import pathlib
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from cst_session.lifecycle import InvalidTurn, Started, Turned
from cst_session.persona import (
    PersonaFailure,
    PersonaMessage,
    PersonaReply,
    PersonaUnavailable,
)
from cst_session.scenarios import SCENARIO_IDS, load_catalogue
from cst_session.scenarios.prompts import load_prompts
from cst_session.state import Rejection, StateRejected
from harness.run import RunOutcome, main, run_once
from harness.script import SCRIPT_IDS, load_scripts
from tests.lifecycle_fakes import with_release
from tests.test_harness_checks import PASSING
from tests.test_scenario_write_paths import (
    ROUTE_CALLS,
    WRITE_DECORATORS,
    call_name,
    declared_methods,
    service_files,
)

SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = load_scripts()
PROJECT = "synthetic-dev-01"
MAIN_TF = (
    'locals {\n  agent_platform = {\n    location      = "us"\n'
    '    persona_model = "gemini-3.8-flash"\n  }\n}\n'
)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "infra/environments").mkdir(parents=True)
    (tmp_path / "infra/environments/development.json").write_text(
        json.dumps({"projectId": PROJECT}), encoding="utf-8"
    )
    (tmp_path / "infra/session-grading").mkdir(parents=True)
    (tmp_path / "infra/session-grading/main.tf").write_text(MAIN_TF, encoding="utf-8")
    return tmp_path


class ByScript:
    """Answers each session from ``PASSING`` (or ``overrides``), in run order.

    The two crisis scripts share their first turn, so a session can't be told
    apart by its history. The harness runs the scripts in ``order`` (each
    ``repeat`` times), and a history of one message is a new session.
    """

    def __init__(
        self,
        order: Sequence[str],
        repeat: int,
        overrides: dict[str, Sequence[str | None]] | None = None,
    ) -> None:
        self.replies = {**PASSING, **(overrides or {})}
        self.queue = [script_id for script_id in order for _ in range(repeat)]
        self.current = ""
        self.prompts: list[tuple[str, str]] = []

    async def reply(
        self, *, system_prompt: str, history: Sequence[PersonaMessage]
    ) -> PersonaReply:
        if len(history) == 1:
            self.current = self.queue.pop(0)
        self.prompts.append((self.current, system_prompt))
        reply = self.replies[self.current][len(history) // 2]
        if reply is None:
            raise PersonaUnavailable(PersonaFailure.BLOCKED)
        return PersonaReply(text=reply)


def run_harness(repo: Path, persona: object, *argv: str, **kwargs: Any) -> int:
    return main(
        list(argv),
        environ={},
        repo_root=repo,
        persona_factory=lambda pins: persona,  # type: ignore[arg-type, return-value]
        **kwargs,
    )


def secrets_in(texts: Sequence[str]) -> list[str]:
    """Every reply, script turn and prompt line, the strings that must never leave."""
    needles = [r for replies in PASSING.values() for r in replies if r]
    needles += [turn.text for script in SCRIPTS.values() for turn in script.turns]
    prompts = load_prompts()
    needles += [
        line.strip()
        for scenario_id in SCENARIO_IDS
        for line in prompts.for_scenario(scenario_id).splitlines()
        if len(line.strip()) >= 20
    ]
    return [needle for needle in needles if any(needle in text for text in texts)]


# AC1 ----------------------------------------------------------------------


def test_ac1_prompts_manifest_and_catalogue_name_the_same_three_scenarios() -> None:
    catalogue_ids = {scenario.id for scenario in load_catalogue().scenarios}
    prompts = load_prompts()

    assert catalogue_ids == set(SCENARIO_IDS) == set(prompts.texts)
    assert len(catalogue_ids) == 3
    for scenario_id in catalogue_ids:
        assert re.fullmatch(r"\d+\.\d+\.\d+", prompts.version_for(scenario_id))


@pytest.mark.parametrize(
    "scenario_id", ["routine_intake", "resistant_client", "crisis_risk"]
)
def test_ac1_a_session_on_each_config_sends_that_configs_prompt(
    repo: Path, scenario_id: str
) -> None:
    persona = ByScript([scenario_id], 1)

    code = run_harness(
        repo, persona, "--scenario", scenario_id, "--repeat", "1",
        out=io.StringIO(), err=io.StringIO(),
    )  # fmt: skip

    assert code == 0
    expected = load_prompts().for_scenario(scenario_id)
    assert persona.prompts
    assert {prompt for _, prompt in persona.prompts} == {expected}


# AC4 ----------------------------------------------------------------------

PROMPT_WORDS = ("prompt", "persona")


def names_a_prompt(node: ast.Call) -> bool:
    return any(
        isinstance(arg, ast.Constant)
        and isinstance(arg.value, str)
        and any(word in arg.value.lower() for word in PROMPT_WORDS)
        for arg in [*node.args, *(keyword.value for keyword in node.keywords)]
    )


def prompt_write_routes(tree: ast.AST) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not names_a_prompt(node):
            continue
        name = call_name(node)
        if name in WRITE_DECORATORS:
            lines.append(node.lineno)
        elif name in ROUTE_CALLS:
            methods = declared_methods(node)
            if methods is None or not methods <= {"GET", "HEAD"}:
                lines.append(node.lineno)
    return lines


def test_ac4_no_route_that_names_a_prompt_or_persona_writes() -> None:
    offenders = [
        f"{path.name}:{line}"
        for path in service_files()
        for line in prompt_write_routes(ast.parse(path.read_text(encoding="utf-8")))
    ]

    assert offenders == []


@pytest.mark.parametrize(
    "sample",
    [
        '@app.post("/v1/prompts")\ndef f(): ...',
        '@router.put("/v1/personas/{scenario_id}/prompt")\ndef f(): ...',
        'app.add_api_route("/v1/persona-prompts", f, methods=["PATCH"])',
        'app.add_api_route("/v1/prompts", f)',
    ],
)
def test_ac4_the_prompt_route_check_catches_a_write(sample: str) -> None:
    assert prompt_write_routes(ast.parse(sample))


def test_ac4_the_prompt_route_check_allows_a_read() -> None:
    sample = '@app.get("/v1/prompts")\ndef f(): ...'

    assert prompt_write_routes(ast.parse(sample)) == []


# FR-5: content-free output on every path -----------------------------------


@pytest.mark.parametrize(
    ("name", "overrides", "code"),
    [
        ("all_pass", {}, 0),
        (
            "in_character_fails",
            {"routine_intake": [*PASSING["routine_intake"][:2], "As an AI, I study.",
                                *PASSING["routine_intake"][3:]]},
            1,
        ),
        (
            "crisis_blocked",
            {"crisis_risk": [*PASSING["crisis_risk"][:4], None,
                             *PASSING["crisis_risk"][5:]]},
            1,
        ),
    ],
)  # fmt: skip
def test_fr5_no_reply_turn_or_prompt_line_leaves_any_script(
    repo: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    name: str,
    overrides: dict[str, Sequence[str | None]],
    code: int,
) -> None:
    caplog.set_level(logging.DEBUG)

    assert (
        run_harness(repo, ByScript(SCRIPT_IDS, 2, overrides), "--repeat", "2") == code
    ), name

    captured = capsys.readouterr()
    headers = [line for line in captured.out.splitlines() if line.startswith("# ")]
    assert len(headers) == len(SCRIPT_IDS)
    assert secrets_in([captured.out, captured.err, caplog.text]) == []
    assert "As an AI" not in captured.out + captured.err + caplog.text


def test_fr5_an_unreleased_scenario_run_is_content_free(
    repo: Path, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    catalogue = with_release(load_catalogue(), "crisis_risk", released=False)

    order = [s for s in SCRIPT_IDS if SCRIPTS[s].scenario_id != "crisis_risk"]
    code = run_harness(repo, ByScript(order, 1), "--repeat", "1", catalogue=catalogue)

    captured = capsys.readouterr()
    assert code == 1
    assert "FAIL start_refused(scenario_unavailable)  0/1" in captured.out.splitlines()
    assert secrets_in([captured.out, captured.err, caplog.text]) == []


def test_fr5_every_report_line_is_a_header_or_a_verdict(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_harness(repo, ByScript(SCRIPT_IDS, 1), "--repeat", "1") == 0

    verdict = re.compile(
        r"^(PASS|FAIL|INFO) [a-z0-9_()]+  \d+/\d+(  [a-z0-9_]+=\d+( [a-z0-9_]+=\d+)*)?$"
    )
    header = re.compile(r"^# (\w+=[\w.:\-]+ ?)+$")
    for line in capsys.readouterr().out.splitlines():
        assert verdict.match(line) or header.match(line), line


def test_fr5_the_harness_opens_no_file_for_writing(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writes: list[str] = []
    real_open = builtins.open

    def guarded_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if set(mode) & set("wax+"):
            writes.append(f"{file}:{mode}")
        return real_open(file, mode, *args, **kwargs)

    def refuse(self: pathlib.Path, *args: Any, **kwargs: Any) -> Any:
        writes.append(str(self))
        raise AssertionError("the harness wrote a file")

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(io, "open", guarded_open)
    for method in ("write_text", "write_bytes", "touch", "mkdir"):
        monkeypatch.setattr(pathlib.Path, method, refuse)
    before = sorted(p.as_posix() for p in repo.rglob("*"))

    code = run_harness(
        repo,
        ByScript(SCRIPT_IDS, 1),
        "--repeat",
        "1",
        out=io.StringIO(),
        err=io.StringIO(),
    )

    assert code == 0
    assert writes == []
    assert sorted(p.as_posix() for p in repo.rglob("*")) == before


# FR-6: the live tests never run by default --------------------------------


def test_fr6_the_default_pytest_run_deselects_every_live_test() -> None:
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-p", "no:cacheprovider", "tests/live"],
        cwd=SERVICE_ROOT, capture_output=True, text=True, timeout=120, check=False,
    )  # fmt: skip

    summary = collected.stdout.strip().splitlines()[-1]
    assert collected.returncode == 5, collected.stdout  # pytest: no tests ran
    assert summary.startswith("no tests collected"), summary
    assert f"({len(SCRIPT_IDS)} deselected)" in summary
    assert "::" not in collected.stdout


# The service image ships no harness ---------------------------------------


def test_the_service_image_copies_only_requirements_and_cst_session() -> None:
    dockerfile = (SERVICE_ROOT / "Dockerfile").read_text(encoding="utf-8")
    sources = [
        line.split()[1:-1]
        for line in dockerfile.splitlines()
        if line.strip().upper().startswith(("COPY", "ADD"))
    ]

    assert sources == [["requirements.txt"], ["cst_session"]]
    assert "harness" not in dockerfile


# The runner's stop paths: a rejected turn or end stops the run with a code ---


class StoppingSessions:
    """A ``Sessions`` stand-in that starts, then raises ``turn_error`` or ``end_error``."""

    def __init__(
        self, turn_error: Exception | None = None, end_error: Exception | None = None
    ) -> None:
        self.turn_error = turn_error
        self.end_error = end_error

    def start(self, **kwargs: Any) -> Started:
        return Started("s1", "state-0", 600_000, 600_000)

    async def turn(self, **kwargs: Any) -> Turned:
        if self.turn_error is not None:
            raise self.turn_error
        return Turned(PASSING["routine_intake"][0], "state-1", 500_000)

    async def end(self, **kwargs: Any) -> None:
        if self.end_error is not None:
            raise self.end_error


@pytest.mark.parametrize(
    ("sessions", "error"),
    [
        (StoppingSessions(turn_error=InvalidTurn()), "turn_rejected(invalid_turn)"),
        (
            StoppingSessions(turn_error=StateRejected(Rejection.TIME_LIMIT)),
            "turn_rejected(time_limit)",
        ),
        (
            StoppingSessions(end_error=StateRejected(Rejection.EXPIRED)),
            "end_rejected(expired)",
        ),
    ],
    ids=["invalid-turn", "turn-time-limit", "end-expired"],
)
def test_a_rejected_turn_or_end_stops_the_run_with_a_fixed_code(
    sessions: StoppingSessions, error: str
) -> None:
    outcome = asyncio.run(run_once(sessions, SCRIPTS["routine_intake"]))  # type: ignore[arg-type]

    assert outcome == RunOutcome(error=error)
    assert outcome.results == ()
